from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.optimization.weights import (
    ALPHA,
    BASE_SCORE,
    C_MAX,
    DELTA_PER_MONTH,
    LONG_SHIFT_THRESHOLD,
    N_MAX_NIGHT,
    OT_MAX,
    STANDARD_WEEKLY_HOURS,
    T_REST,
    W_S1,
    W_S2,
    W_S3,
    W_S4,
    W_S5,
    W_S6,
)

REGIME_FIVE_DAY = "FIVE_DAY"
REGIME_SUMMARIZED = "SUMMARIZED"

NIGHT_WINDOW_START = time(22, 0)
NIGHT_WINDOW_END = time(6, 0)
NIGHT_SHIFT_MIN_HOURS = 4.0  

WEEKEND_WEEKDAYS = frozenset({5, 6})

HOURS_PER_DAY = 24
DAYS_PER_BLOCK = 7
MIN_REST_RUN_LENGTH = 2
LONG_RUN_REST_INTERVAL = 2


@dataclass(frozen=True, slots=True)
class ShiftType:
    id: int
    start_time: time
    end_time: time

    @property
    def duration_hours(self) -> float:
        return shift_duration_hours(self)


@dataclass(frozen=True, slots=True)
class Employee:
    id: int
    hours_per_week: float


@dataclass(frozen=True, slots=True)
class Assignment:
    employee_id: int
    date: date
    shift_type_id: int | None


@dataclass(frozen=True, slots=True)
class ScheduleContext:
    employees: tuple[Employee, ...]
    shift_types: tuple[ShiftType, ...]
    assignments: tuple[Assignment, ...]
    period_start: date
    period_end: date
    monthly_norms: dict[str, float]
    staffing_requirements: dict[int, int]
    approved_leave: frozenset[tuple[int, date]]
    off_weekdays: frozenset[int]
    non_working_dates: frozenset[date]
    employee_preferences: dict[int, frozenset[int]]


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    h1: int
    h2: int
    h3: int
    h4: int
    h5: int
    h6: int
    h7: int
    h8: int
    h9: int
    hard_total: int

    s1: int
    s2: float
    s3: int
    s4: int
    s5: int
    s6: float
    soft_penalty: float

    fitness: float
    is_feasible: bool


def shift_duration_hours(st: ShiftType) -> float:
    start = _time_to_hours(st.start_time)
    end = _time_to_hours(st.end_time)
    # end < start means the shift crosses midnight (22:00-06:00); 08:00-00:00 wraps end 0.0 to 24.0; end == start is a zero length shift
    if end < start:
        end += HOURS_PER_DAY
    return end - start


def is_night_shift(st: ShiftType) -> bool:
    return _night_hours(st) >= NIGHT_SHIFT_MIN_HOURS


def derive_regime(off_weekdays: set[int]) -> str:
    return REGIME_FIVE_DAY if off_weekdays == WEEKEND_WEEKDAYS else REGIME_SUMMARIZED


def non_working_set(ctx: ScheduleContext) -> set[date]:
    derived = {
        day
        for day in _period_days(ctx.period_start, ctx.period_end)
        if day.weekday() in ctx.off_weekdays
    }
    return derived | ctx.non_working_dates


def compute_m_period(monthly_norms: dict[str, float]) -> float:
    return sum(monthly_norms.values())


def compute_m_e(m_period: float, hours_per_week: float) -> float:
    return m_period * (hours_per_week / STANDARD_WEEKLY_HOURS)


def compute_delta(monthly_norms: dict[str, float]) -> float:
    return DELTA_PER_MONTH * len(monthly_norms)


def compute_effective_norms(ctx: ScheduleContext) -> dict[int, float]:
    m_period = compute_m_period(ctx.monthly_norms)
    hours_by_employee = {e.id: e.hours_per_week for e in ctx.employees}
    reduction: dict[int, float] = defaultdict(float)
    for employee_id, day in ctx.approved_leave:
        # statutory five day - only Mon-Fri, non-holiday leave reduces the norm 
        if day.weekday() >= 5 or day in ctx.non_working_dates:
            continue
        hours_per_week = hours_by_employee.get(employee_id)
        if hours_per_week is None:
            continue
        # one leave working day = one five day working day of hours
        reduction[employee_id] += hours_per_week / 5.0
    return {
        e.id: max(0.0, compute_m_e(m_period, e.hours_per_week) - reduction.get(e.id, 0.0))
        for e in ctx.employees
    }


def check_h1(ctx: ScheduleContext) -> int:
    shifts_per_day: dict[tuple[int, date], int] = defaultdict(int)
    for a in ctx.assignments:
        if a.shift_type_id is not None:
            shifts_per_day[(a.employee_id, a.date)] += 1
    return sum(1 for count in shifts_per_day.values() if count > 1)


def check_h2(ctx: ScheduleContext) -> int:
    return sum(
        1
        for a in ctx.assignments
        if a.shift_type_id is not None
        and (a.employee_id, a.date) in ctx.approved_leave
    )


def check_h3(ctx: ScheduleContext) -> int:
    shift_by_id = _shift_index(ctx)
    violations = 0
    for worked in _worked_days_by_employee(ctx).values():
        ordered = sorted(worked.items())
        for (prev_date, prev_shift), (next_date, next_shift) in zip(
            ordered, ordered[1:]
        ):
            if (next_date - prev_date).days != 1:
                continue
            gap = _rest_gap_hours(
                prev_date, shift_by_id[prev_shift], next_date, shift_by_id[next_shift]
            )
            if gap < T_REST:
                violations += 1
    return violations


def check_h4(ctx: ScheduleContext) -> int:
    violations = 0
    for worked_dates in _worked_date_sets(ctx).values():
        for run_length in _consecutive_run_lengths(worked_dates):
            if run_length > C_MAX:
                violations += 1
    return violations


def check_h5(ctx: ScheduleContext) -> int:
    effective_norms = compute_effective_norms(ctx)
    worked_hours = _worked_hours_by_employee(ctx)
    violations = 0
    for employee in ctx.employees:
        if worked_hours.get(employee.id, 0.0) > effective_norms[employee.id] + OT_MAX:
            violations += 1
    return violations


def check_h6(ctx: ScheduleContext) -> int:
    non_working = non_working_set(ctx)
    headcount: dict[tuple[date, int], int] = defaultdict(int)
    for a in ctx.assignments:
        if a.shift_type_id is not None and a.date not in non_working:
            headcount[(a.date, a.shift_type_id)] += 1

    violations = 0
    for day in _period_days(ctx.period_start, ctx.period_end):
        if day in non_working:
            continue
        for shift in ctx.shift_types:
            required = ctx.staffing_requirements.get(shift.id, 0)
            if required == 0:
                continue
            if headcount[(day, shift.id)] != required:
                violations += 1
    return violations


def check_h7(ctx: ScheduleContext) -> int:
    non_working = non_working_set(ctx)
    return sum(
        1
        for a in ctx.assignments
        if a.shift_type_id is not None and a.date in non_working
    )


def check_h8(ctx: ScheduleContext) -> int:
    if derive_regime(ctx.off_weekdays) != REGIME_FIVE_DAY:
        return 0
    violating_ids = {
        st.id
        for st in ctx.shift_types
        if is_night_shift(st) and shift_duration_hours(st) > N_MAX_NIGHT
    }
    return sum(1 for a in ctx.assignments if a.shift_type_id in violating_ids)


def check_h9(ctx: ScheduleContext) -> int:
    worked_dates = _worked_date_sets(ctx)
    violations = 0
    for block in _full_week_blocks(ctx.period_start, ctx.period_end):
        for employee in ctx.employees:
            worked = worked_dates.get(employee.id, set())
            if not _has_consecutive_two_day_off(block, worked):
                violations += 1
    return violations


def check_s1(ctx: ScheduleContext) -> int:
    return sum(
        1
        for a in ctx.assignments
        if a.shift_type_id is not None
        and a.date.weekday() in ctx.employee_preferences.get(a.employee_id, set())
    )


def check_s2(ctx: ScheduleContext) -> float:
    effective_norms = compute_effective_norms(ctx)
    delta = compute_delta(ctx.monthly_norms)
    worked_hours = _worked_hours_by_employee(ctx)
    total_undershoot = 0.0
    for employee in ctx.employees:
        eff = effective_norms[employee.id]
        worked = worked_hours.get(employee.id, 0.0)
        # OT_MAX = 0: H5 caps overtime, so S2 only penalizes under-utilization; whole-period leave gives eff == 0, so the undershoot is never positive (they owe nothing)
        deviation = (eff - worked) if OT_MAX == 0 else abs(worked - eff)
        undershoot = deviation - delta
        if undershoot > 0.0:
            total_undershoot += undershoot
    return total_undershoot


def check_s3(ctx: ScheduleContext) -> int:
    shift_by_id = _shift_index(ctx)
    long_shift_ids = {
        sid
        for sid, st in shift_by_id.items()
        if shift_duration_hours(st) > LONG_SHIFT_THRESHOLD
    }

    violations = 0
    for worked in _worked_days_by_employee(ctx).values():
        long_dates = {
            day for day, sid in worked.items() if sid in long_shift_ids
        }
        for run_length in _consecutive_run_lengths(long_dates):
            violations += max(0, run_length - LONG_RUN_REST_INTERVAL)
    return violations


def check_s4(ctx: ScheduleContext) -> int:
    if WEEKEND_WEEKDAYS <= ctx.off_weekdays:
        return 0
    counts = {employee.id: 0 for employee in ctx.employees}
    for a in ctx.assignments:
        if a.shift_type_id is not None and a.date.weekday() in WEEKEND_WEEKDAYS:
            counts[a.employee_id] += 1
    return _spread(counts)


def check_s5(ctx: ScheduleContext) -> int:
    night_shift_ids = {st.id for st in ctx.shift_types if is_night_shift(st)}
    counts = {employee.id: 0 for employee in ctx.employees}
    for a in ctx.assignments:
        if a.shift_type_id in night_shift_ids:
            counts[a.employee_id] += 1
    return _spread(counts)


def check_s6(ctx: ScheduleContext) -> float:
    if len(ctx.employees) <= 1:
        return 0.0
    effective_norms = compute_effective_norms(ctx)
    worked_hours = _worked_hours_by_employee(ctx)
    deviations = [
        worked_hours.get(e.id, 0.0) - effective_norms[e.id]
        for e in ctx.employees
    ]
    return float(max(deviations) - min(deviations))


def evaluate_schedule(ctx: ScheduleContext) -> EvaluationResult:
    h1 = check_h1(ctx)
    h2 = check_h2(ctx)
    h3 = check_h3(ctx)
    h4 = check_h4(ctx)
    h5 = check_h5(ctx)
    h6 = check_h6(ctx)
    h7 = check_h7(ctx)
    h8 = check_h8(ctx)
    h9 = check_h9(ctx)
    hard_total = h1 + h2 + h3 + h4 + h5 + h6 + h7 + h8 + h9

    s1 = check_s1(ctx)
    s2 = check_s2(ctx)
    s3 = check_s3(ctx)
    s4 = check_s4(ctx)
    s5 = check_s5(ctx)
    s6 = check_s6(ctx)
    soft_penalty = float(
        s1 * W_S1 + s2 * W_S2 + s3 * W_S3 + s4 * W_S4 + s5 * W_S5 + s6 * W_S6
    )

    fitness = BASE_SCORE - hard_total * ALPHA - soft_penalty

    return EvaluationResult(
        h1=h1,
        h2=h2,
        h3=h3,
        h4=h4,
        h5=h5,
        h6=h6,
        h7=h7,
        h8=h8,
        h9=h9,
        hard_total=hard_total,
        s1=s1,
        s2=s2,
        s3=s3,
        s4=s4,
        s5=s5,
        s6=s6,
        soft_penalty=soft_penalty,
        fitness=fitness,
        is_feasible=hard_total == 0,
    )


def _time_to_hours(t: time) -> float:
    return t.hour + t.minute / 60 + t.second / 3600


def _night_hours(st: ShiftType) -> float:
    start = _time_to_hours(st.start_time)
    end = _time_to_hours(st.end_time)
    if end < start:
        end += HOURS_PER_DAY
    total = 0.0
    for piece_start, piece_end in ((0.0, 6.0), (22.0, 24.0), (24.0, 30.0)):
        total += max(0.0, min(end, piece_end) - max(start, piece_start))
    return total


def _open_overlap(
    start_a: float, end_a: float, start_b: float, end_b: float
) -> bool:
    return start_a < end_b and start_b < end_a


def _period_days(period_start: date, period_end: date) -> list[date]:
    span = (period_end - period_start).days
    return [period_start + timedelta(days=offset) for offset in range(span + 1)]


def _shift_index(ctx: ScheduleContext) -> dict[int, ShiftType]:
    return {st.id: st for st in ctx.shift_types}


def _worked_days_by_employee(ctx: ScheduleContext) -> dict[int, dict[date, int]]:
    worked: dict[int, dict[date, int]] = defaultdict(dict)
    for a in ctx.assignments:
        if a.shift_type_id is not None:
            worked[a.employee_id][a.date] = a.shift_type_id
    return worked


def _worked_date_sets(ctx: ScheduleContext) -> dict[int, set[date]]:
    return {
        employee_id: set(days.keys())
        for employee_id, days in _worked_days_by_employee(ctx).items()
    }


def _worked_hours_by_employee(ctx: ScheduleContext) -> dict[int, float]:
    shift_by_id = _shift_index(ctx)
    hours: dict[int, float] = defaultdict(float)
    for a in ctx.assignments:
        if a.shift_type_id is not None and a.shift_type_id in shift_by_id:
            hours[a.employee_id] += shift_duration_hours(shift_by_id[a.shift_type_id])
    return hours


def _rest_gap_hours(
    prev_date: date,
    prev_shift: ShiftType,
    next_date: date,
    next_shift: ShiftType,
) -> float:
    prev_end = datetime.combine(prev_date, prev_shift.end_time)
    # end < start means the shift finishes next day; end == 00:00 stays on prev_date
    if prev_shift.end_time < prev_shift.start_time:
        prev_end += timedelta(days=1)
    next_start = datetime.combine(next_date, next_shift.start_time)
    return (next_start - prev_end).total_seconds() / 3600


def _consecutive_run_lengths(days: set[date]) -> list[int]:
    if not days:
        return []
    ordered = sorted(days)
    runs: list[int] = []
    run_length = 1
    for prev, current in zip(ordered, ordered[1:]):
        if (current - prev).days == 1:
            run_length += 1
        else:
            runs.append(run_length)
            run_length = 1
    runs.append(run_length)
    return runs


def _full_week_blocks(period_start: date, period_end: date) -> list[list[date]]:
    all_days = _period_days(period_start, period_end)
    blocks: list[list[date]] = []
    for start in range(0, len(all_days), DAYS_PER_BLOCK):
        block = all_days[start : start + DAYS_PER_BLOCK]
        
        if len(block) == DAYS_PER_BLOCK:
            blocks.append(block)
    return blocks


def _has_consecutive_two_day_off(block: list[date], worked: set[date]) -> bool:
    for first, second in zip(block, block[1:]):
        if first not in worked and second not in worked:
            return True
    return False


def _spread(counts: dict[int, int]) -> int:
    if not counts:
        return 0
    return max(counts.values()) - min(counts.values())
