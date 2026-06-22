from __future__ import annotations

import time as _time_module
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import NamedTuple

from ortools.sat.python import cp_model

from app.optimization.evaluate import (
    REGIME_FIVE_DAY,
    Assignment,
    EvaluationResult,
    ScheduleContext,
    ShiftType,
    compute_effective_norms,
    derive_regime,
    evaluate_schedule,
    is_night_shift,
    non_working_set,
    shift_duration_hours,
)
from app.optimization.weights import (
    BASE_SCORE,
    C_MAX,
    DELTA_PER_MONTH,
    LONG_SHIFT_THRESHOLD,
    N_MAX_NIGHT,
    OT_MAX,
    T_REST,
    W_S1,
    W_S2,
    W_S3,
    W_S4,
    W_S5,
    W_S6,
)

DAYS_PER_BLOCK = 7
HOURS_SCALE = 100
WEEKEND_WEEKDAYS = frozenset({5, 6})
LONG_RUN_REST_INTERVAL = 2

DEFAULT_TIME_LIMIT_SECONDS = 400.0
DEFAULT_NUM_WORKERS = 1


class CPSATResult(NamedTuple):
    evaluation: EvaluationResult
    assignments: list[Assignment]
    best_penalty_bound: float | None  # solver.best_objective_bound; none if no feasible solution found
    status_name: str  # CP-SAT solver status: OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN (int for any other)


@dataclass
class CPSATConfig:
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS
    num_workers: int = DEFAULT_NUM_WORKERS

    def __post_init__(self) -> None:
        if self.time_limit_seconds <= 0:
            raise ValueError("time_limit_seconds must be > 0")
        if self.num_workers < 1:
            raise ValueError("num_workers must be >= 1")


def _rest_gap_hours(
    prev_date: date,
    prev_shift: ShiftType,
    next_date: date,
    next_shift: ShiftType,
) -> float:
    prev_end = datetime.combine(prev_date, prev_shift.end_time)
    if prev_shift.end_time < prev_shift.start_time:
        prev_end += timedelta(days=1)
    next_start = datetime.combine(next_date, next_shift.start_time)
    return (next_start - prev_end).total_seconds() / 3600


@dataclass(frozen=True, slots=True)
class _Problem:

    employee_ids: tuple[int, ...]
    period_days: tuple[date, ...]
    working_day_indices: tuple[int, ...]
    working_day_set: frozenset[int]
    shift_types: tuple[ShiftType, ...]
    shift_ids: tuple[int, ...]
    durations_scaled: tuple[int, ...]
    long_shift_flags: tuple[bool, ...]
    night_shift_flags: tuple[bool, ...]
    forbidden_h8_flags: tuple[bool, ...]
    staffing_requirements: dict[int, int]
    approved_leave: frozenset[tuple[int, date]]
    full_week_blocks: tuple[tuple[int, ...], ...]
    m_e_scaled: tuple[int, ...]
    under_util_threshold_scaled: tuple[int, ...]
    preference_off_weekdays: tuple[frozenset[int], ...]


def _build_problem(ctx: ScheduleContext) -> _Problem:
    span = (ctx.period_end - ctx.period_start).days
    period_days = tuple(
        ctx.period_start + timedelta(days=offset) for offset in range(span + 1)
    )
    off_days = non_working_set(ctx)
    working_day_indices = tuple(
        d_idx for d_idx, day in enumerate(period_days) if day not in off_days
    )
    is_five_day = derive_regime(set(ctx.off_weekdays)) == REGIME_FIVE_DAY
    durations = tuple(shift_duration_hours(st) for st in ctx.shift_types)
    night_flags = tuple(is_night_shift(st) for st in ctx.shift_types)
    long_flags = tuple(dur > LONG_SHIFT_THRESHOLD for dur in durations)
    forbidden_h8 = tuple(
        is_five_day and night and dur > N_MAX_NIGHT
        for night, dur in zip(night_flags, durations)
    )
    blocks = tuple(
        tuple(range(start, start + DAYS_PER_BLOCK))
        for start in range(0, len(period_days), DAYS_PER_BLOCK)
        if start + DAYS_PER_BLOCK <= len(period_days)
    )

    delta = DELTA_PER_MONTH * len(ctx.monthly_norms)
    # leave-reduced norms from the shared evaluator so the objective matches evaluate_schedule() exactly 
    effective_norms = compute_effective_norms(ctx)
    m_e = tuple(effective_norms[emp.id] for emp in ctx.employees)
    m_e_scaled = tuple(round((value + OT_MAX) * HOURS_SCALE) for value in m_e)
    under_util_threshold_scaled = tuple(
        round((value - delta) * HOURS_SCALE) for value in m_e
    )

    return _Problem(
        employee_ids=tuple(emp.id for emp in ctx.employees),
        period_days=period_days,
        working_day_indices=working_day_indices,
        working_day_set=frozenset(working_day_indices),
        shift_types=ctx.shift_types,
        shift_ids=tuple(st.id for st in ctx.shift_types),
        durations_scaled=tuple(round(dur * HOURS_SCALE) for dur in durations),
        long_shift_flags=long_flags,
        night_shift_flags=night_flags,
        forbidden_h8_flags=forbidden_h8,
        staffing_requirements=dict(ctx.staffing_requirements),
        approved_leave=ctx.approved_leave,
        full_week_blocks=blocks,
        m_e_scaled=m_e_scaled,
        under_util_threshold_scaled=under_util_threshold_scaled,
        preference_off_weekdays=tuple(
            ctx.employee_preferences.get(emp.id, frozenset())
            for emp in ctx.employees
        ),
    )


_STATUS_NAMES = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.UNKNOWN: "UNKNOWN",
}



def _status_name(status: int) -> str:
    return _STATUS_NAMES.get(status, str(status))


def run_cpsat(
    ctx: ScheduleContext,
    config: CPSATConfig | None = None,
    anytime_callback: Callable[[float, float, bool], None] | None = None,
) -> CPSATResult:
    config = config or CPSATConfig()
    problem = _build_problem(ctx)

    model = cp_model.CpModel()
    x = _build_decision_vars(model, problem)
    is_working = _build_is_working(model, problem, x)

    _add_hard_constraints(model, problem, x, is_working)
    objective_terms = _add_soft_objective(model, problem, x, is_working)
    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config.time_limit_seconds
    solver.parameters.num_search_workers = config.num_workers
    solver.parameters.log_search_progress = False

    callback = _SolutionCallback(anytime_callback) if anytime_callback else None
    status = solver.Solve(model, callback)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignments = _extract_assignments(solver, problem, x)
        best_penalty_bound: float | None = solver.best_objective_bound / HOURS_SCALE
    else:
        assignments = _all_off_assignments(problem)
        best_penalty_bound = None

    final_ctx = replace(ctx, assignments=tuple(assignments))
    return CPSATResult(
        evaluate_schedule(final_ctx),
        assignments,
        best_penalty_bound,
        _status_name(status),
    )


def _build_decision_vars(
    model: cp_model.CpModel, problem: _Problem
) -> dict[tuple[int, int, int], cp_model.IntVar]:
    x: dict[tuple[int, int, int], cp_model.IntVar] = {}
    for e_idx in range(len(problem.employee_ids)):
        for d_idx in range(len(problem.period_days)):
            for s_idx in range(len(problem.shift_ids)):
                x[e_idx, d_idx, s_idx] = model.NewBoolVar(f"x_{e_idx}_{d_idx}_{s_idx}")
    return x


def _build_is_working(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> dict[tuple[int, int], cp_model.IntVar]:
    is_working: dict[tuple[int, int], cp_model.IntVar] = {}
    n_shifts = len(problem.shift_ids)
    for e_idx in range(len(problem.employee_ids)):
        for d_idx in range(len(problem.period_days)):
            working = model.NewBoolVar(f"work_{e_idx}_{d_idx}")
            model.Add(working == sum(x[e_idx, d_idx, s] for s in range(n_shifts)))
            is_working[e_idx, d_idx] = working
    return is_working


def _add_hard_constraints(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
    is_working: dict[tuple[int, int], cp_model.IntVar],
) -> None:
    _add_h1_one_shift_per_day(model, problem, x)
    _add_h2_no_work_on_leave(model, problem, x)
    _add_h3_minimum_rest(model, problem, x)
    _add_h4_max_consecutive_days(model, problem, is_working)
    _add_h5_period_hours_cap(model, problem, x)
    _add_h6_exact_staffing(model, problem, x)
    _add_h7_no_work_on_non_working_dates(model, problem, x)
    _add_h8_night_cap(model, problem, x)
    _add_h9_weekly_rest_window(model, problem, is_working)


def _add_h1_one_shift_per_day(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> None:
    n_shifts = len(problem.shift_ids)
    for e_idx in range(len(problem.employee_ids)):
        for d_idx in range(len(problem.period_days)):
            model.AddAtMostOne(x[e_idx, d_idx, s] for s in range(n_shifts))


def _add_h2_no_work_on_leave(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> None:
    n_shifts = len(problem.shift_ids)
    for e_idx, emp_id in enumerate(problem.employee_ids):
        for d_idx, day in enumerate(problem.period_days):
            if (emp_id, day) in problem.approved_leave:
                for s in range(n_shifts):
                    model.Add(x[e_idx, d_idx, s] == 0)


def _add_h3_minimum_rest(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> None:
    shift_types = problem.shift_types
    for e_idx in range(len(problem.employee_ids)):
        for d_idx in range(len(problem.period_days) - 1):
            for s_prev, prev_shift in enumerate(shift_types):
                for s_next, next_shift in enumerate(shift_types):
                    gap = _rest_gap_hours(
                        problem.period_days[d_idx],
                        prev_shift,
                        problem.period_days[d_idx + 1],
                        next_shift,
                    )
                    if gap < T_REST:
                        model.Add(
                            x[e_idx, d_idx, s_prev] + x[e_idx, d_idx + 1, s_next] <= 1
                        )


def _add_h4_max_consecutive_days(
    model: cp_model.CpModel,
    problem: _Problem,
    is_working: dict[tuple[int, int], cp_model.IntVar],
) -> None:
    window = C_MAX + 1
    n_days = len(problem.period_days)
    for e_idx in range(len(problem.employee_ids)):
        for start in range(n_days - window + 1):
            model.Add(
                sum(is_working[e_idx, d] for d in range(start, start + window))
                <= C_MAX
            )


def _add_h5_period_hours_cap(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> None:
    n_days = len(problem.period_days)
    for e_idx in range(len(problem.employee_ids)):
        worked = sum(
            problem.durations_scaled[s] * x[e_idx, d, s]
            for d in range(n_days)
            for s in range(len(problem.shift_ids))
        )
        model.Add(worked <= problem.m_e_scaled[e_idx])


def _add_h6_exact_staffing(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> None:
    n_employees = len(problem.employee_ids)
    for d_idx in problem.working_day_indices:
        for s_idx, shift_id in enumerate(problem.shift_ids):
            required = problem.staffing_requirements.get(shift_id, 0)
            if required <= 0:
                continue
            model.Add(
                sum(x[e, d_idx, s_idx] for e in range(n_employees)) == required
            )


def _add_h7_no_work_on_non_working_dates(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> None:
    n_shifts = len(problem.shift_ids)
    for d_idx in range(len(problem.period_days)):
        if d_idx in problem.working_day_set:
            continue
        for e_idx in range(len(problem.employee_ids)):
            for s in range(n_shifts):
                model.Add(x[e_idx, d_idx, s] == 0)


def _add_h8_night_cap(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> None:
    for s_idx, forbidden in enumerate(problem.forbidden_h8_flags):
        if not forbidden:
            continue
        for e_idx in range(len(problem.employee_ids)):
            for d_idx in range(len(problem.period_days)):
                model.Add(x[e_idx, d_idx, s_idx] == 0)


def _add_h9_weekly_rest_window(
    model: cp_model.CpModel,
    problem: _Problem,
    is_working: dict[tuple[int, int], cp_model.IntVar],
) -> None:
    for e_idx in range(len(problem.employee_ids)):
        for block in problem.full_week_blocks:
            pair_off_vars: list[cp_model.IntVar] = []
            for offset in range(len(block) - 1):
                first, second = block[offset], block[offset + 1]
                first_off = is_working[e_idx, first].Not()
                second_off = is_working[e_idx, second].Not()
                both_off = model.NewBoolVar(f"h9_{e_idx}_{first}")
                model.AddBoolAnd([first_off, second_off]).OnlyEnforceIf(both_off)
                model.AddBoolOr([is_working[e_idx, first], is_working[e_idx, second]]).OnlyEnforceIf(
                    both_off.Not()
                )
                pair_off_vars.append(both_off)
            model.Add(sum(pair_off_vars) >= 1)


def _add_soft_objective(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
    is_working: dict[tuple[int, int], cp_model.IntVar],
) -> list[cp_model.LinearExpr]:
    # scaling count weights (S1/S3/S4/S5) by HOURS_SCALE to match the hours-valued S2/S6 terms, so the objective stays proportional to evaluate_schedule()
    w_s1 = round(W_S1 * HOURS_SCALE)
    w_s2 = round(W_S2)
    w_s3 = round(W_S3 * HOURS_SCALE)
    w_s4 = round(W_S4 * HOURS_SCALE)
    w_s5 = round(W_S5 * HOURS_SCALE)
    w_s6 = round(W_S6)
    terms: list[cp_model.LinearExpr] = []
    terms.append(w_s1 * _build_s1_preference_term(model, problem, is_working))
    terms.append(w_s2 * _build_s2_under_util_term(model, problem, x))
    terms.append(w_s3 * _build_s3_long_run_term(model, problem, x))
    terms.append(w_s4 * _build_s4_weekend_spread_term(model, problem, x))
    terms.append(w_s5 * _build_s5_night_spread_term(model, problem, x))
    terms.append(w_s6 * _build_s6_hours_spread_term(model, problem, x))
    return terms


def _build_s1_preference_term(
    model: cp_model.CpModel,
    problem: _Problem,
    is_working: dict[tuple[int, int], cp_model.IntVar],
) -> cp_model.LinearExpr:
    violations: list[cp_model.IntVar] = []
    for e_idx in range(len(problem.employee_ids)):
        prefers_off = problem.preference_off_weekdays[e_idx]
        if not prefers_off:
            continue
        for d_idx, day in enumerate(problem.period_days):
            if day.weekday() in prefers_off:
                violations.append(is_working[e_idx, d_idx])
    return sum(violations) if violations else 0


def _build_s2_under_util_term(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> cp_model.LinearExpr:
    # proportional undershoot per employee: sum of max(0, threshold - worked), in scaled hours (×HOURS_SCALE)
    assert OT_MAX == 0, (
        "S2 CP-SAT term assumes OT_MAX == 0; update _build_s2_under_util_term for OT_MAX >0"
    )
    n_days = len(problem.period_days)
    n_shifts = len(problem.shift_ids)
    undershoot_terms: list[cp_model.IntVar] = []
    for e_idx in range(len(problem.employee_ids)):
        worked = sum(
            problem.durations_scaled[s] * x[e_idx, d, s]
            for d in range(n_days)
            for s in range(n_shifts)
        )
        threshold = problem.under_util_threshold_scaled[e_idx]
        max_undershoot = max(threshold, 0)
        undershoot = model.NewIntVar(0, max_undershoot, f"s2_undershoot_{e_idx}")
        model.AddMaxEquality(undershoot, [threshold - worked, 0])
        undershoot_terms.append(undershoot)
    return sum(undershoot_terms) if undershoot_terms else 0


def _build_s3_long_run_term(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> cp_model.LinearExpr:
    long_shift_indices = [
        s_idx for s_idx, is_long in enumerate(problem.long_shift_flags) if is_long
    ]
    if not long_shift_indices:
        return 0

    n_days = len(problem.period_days)
    excess_terms: list[cp_model.IntVar] = []
    for e_idx in range(len(problem.employee_ids)):
        # is_long[d_idx] == 1  iff the employee works a long shift on that day
        is_long: list[cp_model.IntVar] = []
        for d_idx in range(n_days):
            long_day = model.NewBoolVar(f"long_{e_idx}_{d_idx}")
            model.Add(long_day == sum(x[e_idx, d_idx, s] for s in long_shift_indices))
            is_long.append(long_day)

        # run[d_idx] = length of the long-shift run ending at d_idx; resets to 0 on a non-long day
        run_vars: list[cp_model.IntVar] = []
        prev_run: cp_model.IntVar | None = None
        for d_idx in range(n_days):
            run = model.NewIntVar(0, n_days, f"run_{e_idx}_{d_idx}")
            if prev_run is None:
                model.Add(run == is_long[d_idx])
            else:
                model.Add(run == prev_run + 1).OnlyEnforceIf(is_long[d_idx])
                model.Add(run == 0).OnlyEnforceIf(is_long[d_idx].Not())
            run_vars.append(run)
            prev_run = run

        # charge each run's excess exactly once, at the day it ends, a run ends at d_idx if (a) d_idx is the last day, or (b) is_long[d_idx]==1 and
        # is_long[d_idx+1]==0; there run_vars[d_idx] holds L (full length), and the contribution is max(0, L - LONG_RUN_REST_INTERVAL)
        for d_idx in range(n_days):
            # run_end_here == 1 iff a long-shift run finishes on this day
            run_end = model.NewBoolVar(f"run_end_{e_idx}_{d_idx}")
            if d_idx < n_days - 1:
                model.AddBoolAnd([is_long[d_idx], is_long[d_idx + 1].Not()]).OnlyEnforceIf(run_end)
                model.AddBoolOr([is_long[d_idx].Not(), is_long[d_idx + 1]]).OnlyEnforceIf(run_end.Not())
            else:
                model.Add(run_end == is_long[d_idx])

            # excess = max(0, run_length - LONG_RUN_REST_INTERVAL) at end-of-run days, 0 everywhere else
            excess = model.NewIntVar(0, n_days, f"s3_excess_{e_idx}_{d_idx}")
            run_excess = model.NewIntVar(0, n_days, f"s3_run_excess_{e_idx}_{d_idx}")
            model.AddMaxEquality(run_excess, [run_vars[d_idx] - LONG_RUN_REST_INTERVAL, 0])
            # charge only when this is a run-end day
            model.Add(excess == run_excess).OnlyEnforceIf(run_end)
            model.Add(excess == 0).OnlyEnforceIf(run_end.Not())
            excess_terms.append(excess)

    return sum(excess_terms) if excess_terms else 0


def _build_s4_weekend_spread_term(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> cp_model.LinearExpr:
    weekend_day_indices = [
        d_idx
        for d_idx, day in enumerate(problem.period_days)
        if day.weekday() in WEEKEND_WEEKDAYS
    ]
    if not weekend_day_indices:
        return 0
    counts = [
        sum(
            x[e_idx, d_idx, s]
            for d_idx in weekend_day_indices
            for s in range(len(problem.shift_ids))
        )
        for e_idx in range(len(problem.employee_ids))
    ]
    return _spread_term(model, problem, counts, "s4")


def _build_s5_night_spread_term(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> cp_model.LinearExpr:
    night_shift_indices = [
        s_idx for s_idx, is_night in enumerate(problem.night_shift_flags) if is_night
    ]
    if not night_shift_indices:
        return 0
    n_days = len(problem.period_days)
    counts = [
        sum(
            x[e_idx, d_idx, s]
            for d_idx in range(n_days)
            for s in night_shift_indices
        )
        for e_idx in range(len(problem.employee_ids))
    ]
    return _spread_term(model, problem, counts, "s5")


def _build_s6_hours_spread_term(
    model: cp_model.CpModel,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> cp_model.LinearExpr:
    assert OT_MAX == 0, (
        "S6 CP-SAT term reads m_e_scaled which includes the OT_MAX cap; "
        "add a pure m_e_scaled field to _Problem before enabling OT_MAX > 0"
    )
    if len(problem.employee_ids) <= 1:
        return 0
    n_days = len(problem.period_days)
    n_shifts = len(problem.shift_ids)
    max_m_e = max(problem.m_e_scaled) if problem.m_e_scaled else 0

    deviation_vars: list[cp_model.IntVar] = []
    for e_idx, m_e in enumerate(problem.m_e_scaled):
        worked = sum(
            problem.durations_scaled[s] * x[e_idx, d, s]
            for d in range(n_days)
            for s in range(n_shifts)
        )
        dev = model.NewIntVar(-max_m_e, max_m_e, f"s6_dev_{e_idx}")
        model.Add(dev == worked - m_e)
        deviation_vars.append(dev)

    dev_max = model.NewIntVar(-max_m_e, max_m_e, "s6_dev_max")
    dev_min = model.NewIntVar(-max_m_e, max_m_e, "s6_dev_min")
    model.AddMaxEquality(dev_max, deviation_vars)
    model.AddMinEquality(dev_min, deviation_vars)
    spread = model.NewIntVar(0, 2 * max_m_e, "s6_spread")
    model.Add(spread == dev_max - dev_min)
    return spread


def _spread_term(
    model: cp_model.CpModel,
    problem: _Problem,
    counts: list[cp_model.LinearExpr],
    label: str,
) -> cp_model.LinearExpr:
    if len(counts) <= 1:
        return 0
    upper = len(problem.period_days)
    max_count = model.NewIntVar(0, upper, f"{label}_max")
    min_count = model.NewIntVar(0, upper, f"{label}_min")
    model.AddMaxEquality(max_count, counts)
    model.AddMinEquality(min_count, counts)
    spread = model.NewIntVar(0, upper, f"{label}_spread")
    model.Add(spread == max_count - min_count)
    return spread


def _extract_assignments(
    solver: cp_model.CpSolver,
    problem: _Problem,
    x: dict[tuple[int, int, int], cp_model.IntVar],
) -> list[Assignment]:
    assignments: list[Assignment] = []
    n_shifts = len(problem.shift_ids)
    for e_idx, emp_id in enumerate(problem.employee_ids):
        for d_idx, day in enumerate(problem.period_days):
            chosen: int | None = None
            for s_idx in range(n_shifts):
                if solver.Value(x[e_idx, d_idx, s_idx]) == 1:
                    chosen = problem.shift_ids[s_idx]
                    break
            assignments.append(
                Assignment(employee_id=emp_id, date=day, shift_type_id=chosen)
            )
    return assignments


def _all_off_assignments(problem: _Problem) -> list[Assignment]:
    return [
        Assignment(employee_id=emp_id, date=day, shift_type_id=None)
        for emp_id in problem.employee_ids
        for day in problem.period_days
    ]


class _SolutionCallback(cp_model.CpSolverSolutionCallback):

    def __init__(
        self, user_callback: Callable[[float, float, bool], None]
    ) -> None:
        super().__init__()
        self._user_callback = user_callback
        self._start = _time_module.perf_counter()

    def on_solution_callback(self) -> None:
        elapsed = _time_module.perf_counter() - self._start
        # ObjectiveValue() is in HOURS_SCALE units; normalise exactly like best_penalty_bound in run_cpsat so GA and CP-SAT traces share a unit
        soft_penalty = self.ObjectiveValue() / HOURS_SCALE
        fitness = BASE_SCORE - soft_penalty
        self._user_callback(elapsed, fitness, True)
