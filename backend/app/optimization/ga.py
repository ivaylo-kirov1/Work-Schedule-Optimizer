from __future__ import annotations

import time as _time_module
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from random import Random

from app.optimization.evaluate import (
    Assignment,
    EvaluationResult,
    ScheduleContext,
    ShiftType,
    evaluate_schedule,
    non_working_set,
)
from app.optimization.weights import C_MAX, T_REST

DAYS_PER_BLOCK = 7

Chromosome = list[list[int | None]]

DEFAULT_POPULATION_SIZE = 100
DEFAULT_CROSSOVER_RATE = 0.8
DEFAULT_MUTATION_RATE = 0.05
DEFAULT_ELITISM = 1
DEFAULT_TOURNAMENT_K = 5
DEFAULT_MAX_GENERATIONS = 500
DEFAULT_CONVERGENCE_PATIENCE = 50


@dataclass
class GAConfig:
    population_size: int = DEFAULT_POPULATION_SIZE
    crossover_rate: float = DEFAULT_CROSSOVER_RATE
    mutation_rate: float = DEFAULT_MUTATION_RATE
    elitism: int = DEFAULT_ELITISM
    tournament_k: int = DEFAULT_TOURNAMENT_K
    max_generations: int = DEFAULT_MAX_GENERATIONS
    convergence_patience: int = DEFAULT_CONVERGENCE_PATIENCE
    wall_clock_limit: float | None = None

    def __post_init__(self) -> None:
        if self.population_size < 2:
            raise ValueError("population_size must be >= 2")
        if not (0.0 <= self.crossover_rate <= 1.0):
            raise ValueError("crossover_rate must be in [0, 1]")
        if not (0.0 <= self.mutation_rate <= 1.0):
            raise ValueError("mutation_rate must be in [0, 1]")
        if self.elitism < 0:
            raise ValueError("elitism must be >= 0")
        if self.tournament_k < 2:
            raise ValueError("tournament_k must be >= 2")


@dataclass(frozen=True, slots=True)
class _Problem:

    employee_ids: tuple[int, ...]
    period_days: tuple[date, ...]
    working_day_indices: tuple[int, ...]
    working_day_set: frozenset[int]
    shift_types: tuple[ShiftType, ...]
    shift_by_id: dict[int, ShiftType]
    shift_type_ids: tuple[int, ...]
    choices: tuple[int | None, ...]
    staffing_requirements: dict[int, int]
    approved_leave: frozenset[tuple[int, date]]
    full_week_blocks: tuple[tuple[int, ...], ...]


def _build_problem(ctx: ScheduleContext) -> _Problem:
    span = (ctx.period_end - ctx.period_start).days
    period_days = tuple(
        ctx.period_start + timedelta(days=offset) for offset in range(span + 1)
    )
    off_days = non_working_set(ctx)
    working_day_indices = tuple(
        d_idx for d_idx, day in enumerate(period_days) if day not in off_days
    )
    shift_type_ids = tuple(st.id for st in ctx.shift_types)
    blocks = tuple(
        tuple(range(start, start + DAYS_PER_BLOCK))
        for start in range(0, len(period_days), DAYS_PER_BLOCK)
        if start + DAYS_PER_BLOCK <= len(period_days)
    )
    return _Problem(
        employee_ids=tuple(emp.id for emp in ctx.employees),
        period_days=period_days,
        working_day_indices=working_day_indices,
        working_day_set=frozenset(working_day_indices),
        shift_types=ctx.shift_types,
        shift_by_id={st.id: st for st in ctx.shift_types},
        shift_type_ids=shift_type_ids,
        choices=(*shift_type_ids, None),
        staffing_requirements=dict(ctx.staffing_requirements),
        approved_leave=ctx.approved_leave,
        full_week_blocks=blocks,
    )


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


def _empty_chromosome(n_employees: int, n_days: int) -> Chromosome:
    return [[None] * n_days for _ in range(n_employees)]


def initialize_individual(
    ctx: ScheduleContext, problem: _Problem, rng: Random
) -> Chromosome:
    n_employees = len(ctx.employees)
    chromosome = _empty_chromosome(n_employees, len(problem.period_days))
    leave = ctx.approved_leave
    employee_ids = [emp.id for emp in ctx.employees]

    for d_idx in problem.working_day_indices:
        day = problem.period_days[d_idx]
        for shift in ctx.shift_types:
            required = ctx.staffing_requirements.get(shift.id, 0)
            if required <= 0:
                continue
            eligible = [
                e_idx
                for e_idx in range(n_employees)
                if chromosome[e_idx][d_idx] is None
                and (employee_ids[e_idx], day) not in leave
                and _has_sufficient_rest(chromosome, problem, e_idx, d_idx, shift)
            ]
            rng.shuffle(eligible)
            for e_idx in eligible[:required]:
                chromosome[e_idx][d_idx] = shift.id
    return chromosome


def _has_sufficient_rest(
    chromosome: Chromosome,
    problem: _Problem,
    e_idx: int,
    d_idx: int,
    shift: ShiftType,
) -> bool:
    if d_idx == 0:
        return True
    prev_shift_id = chromosome[e_idx][d_idx - 1]
    if prev_shift_id is None:
        return True
    gap = _rest_gap_hours(
        problem.period_days[d_idx - 1],
        problem.shift_by_id[prev_shift_id],
        problem.period_days[d_idx],
        shift,
    )
    return gap >= T_REST


REPAIR_PASSES = 3


def _repair(chromosome: Chromosome, problem: _Problem, rng: Random) -> Chromosome:
    repaired = [list(row) for row in chromosome]
    for _ in range(REPAIR_PASSES):
        _clear_illegal_cells(repaired, problem)
        _trim_overstaffed_slots(repaired, problem, rng)
        _enforce_weekly_rest_windows(repaired, problem, rng)
        _fill_understaffed_slots(repaired, problem, rng)
    return repaired


def _clear_illegal_cells(chromosome: Chromosome, problem: _Problem) -> None:
    for e_idx, emp_id in enumerate(problem.employee_ids):
        for d_idx in range(len(problem.period_days)):
            shift_id = chromosome[e_idx][d_idx]
            if shift_id is None:
                continue
            if d_idx not in problem.working_day_set:
                chromosome[e_idx][d_idx] = None  # H7
                continue
            if (emp_id, problem.period_days[d_idx]) in problem.approved_leave:
                chromosome[e_idx][d_idx] = None  # H2
                continue
            if not _has_sufficient_rest(
                chromosome, problem, e_idx, d_idx, problem.shift_by_id[shift_id]
            ):
                chromosome[e_idx][d_idx] = None  # H3
        _trim_long_runs(chromosome[e_idx])


def _trim_long_runs(row: list[int | None]) -> None:
    run = 0
    for d_idx, cell in enumerate(row):
        if cell is None:
            run = 0
            continue
        run += 1
        if run > C_MAX:  # H4
            row[d_idx] = None
            run = 0


def _enforce_weekly_rest_windows(
    chromosome: Chromosome, problem: _Problem, rng: Random
) -> None:
    for e_idx in range(len(problem.employee_ids)):
        row = chromosome[e_idx]
        for block in problem.full_week_blocks:
            if _has_two_day_off_window(row, block):
                continue
            offset = rng.randrange(len(block) - 1)
            row[block[offset]] = None  # H9
            row[block[offset + 1]] = None


def _has_two_day_off_window(row: list[int | None], block: tuple[int, ...]) -> bool:
    return any(
        row[block[i]] is None and row[block[i + 1]] is None
        for i in range(len(block) - 1)
    )


def _trim_overstaffed_slots(
    chromosome: Chromosome, problem: _Problem, rng: Random
) -> None:
    for d_idx in problem.working_day_indices:
        for shift in problem.shift_types:
            required = problem.staffing_requirements.get(shift.id, 0)
            assigned = [
                e_idx
                for e_idx in range(len(problem.employee_ids))
                if chromosome[e_idx][d_idx] == shift.id
            ]
            excess = len(assigned) - required
            if excess <= 0:
                continue
            rng.shuffle(assigned)
            for e_idx in assigned[:excess]:
                chromosome[e_idx][d_idx] = None


def _fill_understaffed_slots(
    chromosome: Chromosome, problem: _Problem, rng: Random
) -> None:
    day_order = list(problem.working_day_indices)
    rng.shuffle(day_order)
    for d_idx in day_order:
        for shift in problem.shift_types:
            required = problem.staffing_requirements.get(shift.id, 0)
            staffed = sum(
                1
                for e_idx in range(len(problem.employee_ids))
                if chromosome[e_idx][d_idx] == shift.id
            )
            shortfall = required - staffed
            if shortfall <= 0:
                continue
            _staff_slot(chromosome, problem, d_idx, shift, shortfall, rng)


def _staff_slot(
    chromosome: Chromosome,
    problem: _Problem,
    d_idx: int,
    shift: ShiftType,
    shortfall: int,
    rng: Random,
) -> None:
    # prefering candidates that keep every H9 window intact; only when none exist we get rest-window day
    protective = [
        e_idx
        for e_idx in range(len(problem.employee_ids))
        if _can_take_slot(chromosome, problem, e_idx, d_idx, shift)
    ]
    rng.shuffle(protective)
    chosen = protective[:shortfall]

    if len(chosen) < shortfall:
        protective_set = set(protective)
        fallback = [
            e_idx
            for e_idx in range(len(problem.employee_ids))
            if e_idx not in protective_set
            and _can_take_slot(chromosome, problem, e_idx, d_idx, shift, allow_window=True)
        ]
        rng.shuffle(fallback)
        chosen = [*chosen, *fallback[: shortfall - len(chosen)]]

    for e_idx in chosen:
        chromosome[e_idx][d_idx] = shift.id


def _can_take_slot(
    chromosome: Chromosome,
    problem: _Problem,
    e_idx: int,
    d_idx: int,
    shift: ShiftType,
    allow_window: bool = False,
) -> bool:
    if chromosome[e_idx][d_idx] is not None:
        return False
    if (problem.employee_ids[e_idx], problem.period_days[d_idx]) in problem.approved_leave:
        return False
    if not _has_sufficient_rest(chromosome, problem, e_idx, d_idx, shift):
        return False
    if not _next_day_rest_preserved(chromosome, problem, e_idx, d_idx, shift):
        return False
    if _run_length_with(chromosome[e_idx], d_idx) > C_MAX:
        return False
    if allow_window:
        return True
    return not _consumes_only_rest_window(chromosome[e_idx], problem, d_idx)


def _next_day_rest_preserved(
    chromosome: Chromosome,
    problem: _Problem,
    e_idx: int,
    d_idx: int,
    shift: ShiftType,
) -> bool:
    next_idx = d_idx + 1
    if next_idx >= len(problem.period_days):
        return True
    next_shift_id = chromosome[e_idx][next_idx]
    if next_shift_id is None:
        return True
    gap = _rest_gap_hours(
        problem.period_days[d_idx],
        shift,
        problem.period_days[next_idx],
        problem.shift_by_id[next_shift_id],
    )
    return gap >= T_REST


def _run_length_with(row: list[int | None], d_idx: int) -> int:
    length = 1
    cursor = d_idx - 1
    while cursor >= 0 and row[cursor] is not None:
        length += 1
        cursor -= 1
    cursor = d_idx + 1
    while cursor < len(row) and row[cursor] is not None:
        length += 1
        cursor += 1
    return length


def _consumes_only_rest_window(
    row: list[int | None], problem: _Problem, d_idx: int
) -> bool:
    for block in problem.full_week_blocks:
        if d_idx not in block:
            continue
        windows = [
            (block[i], block[i + 1])
            for i in range(len(block) - 1)
            if row[block[i]] is None and row[block[i + 1]] is None
        ]
        if len(windows) == 1 and d_idx in windows[0]:
            return True
    return False


def _random_individual(
    ctx: ScheduleContext, problem: _Problem, rng: Random
) -> Chromosome:
    n_days = len(problem.period_days)
    return [
        [rng.choice(problem.choices) for _ in range(n_days)]
        for _ in ctx.employees
    ]


def _chromosome_to_assignments(
    ctx: ScheduleContext, problem: _Problem, chromosome: Chromosome
) -> tuple[Assignment, ...]:
    assignments: list[Assignment] = []
    for e_idx, employee in enumerate(ctx.employees):
        row = chromosome[e_idx]
        for d_idx, day in enumerate(problem.period_days):
            assignments.append(
                Assignment(
                    employee_id=employee.id,
                    date=day,
                    shift_type_id=row[d_idx],
                )
            )
    return tuple(assignments)


def evaluate_individual(
    ctx: ScheduleContext, problem: _Problem, chromosome: Chromosome
) -> EvaluationResult:
    candidate_ctx = replace(
        ctx, assignments=_chromosome_to_assignments(ctx, problem, chromosome)
    )
    return evaluate_schedule(candidate_ctx)


def tournament_select(fitnesses: list[float], k: int, rng: Random) -> int:
    contenders = [rng.randrange(len(fitnesses)) for _ in range(k)]
    return max(contenders, key=lambda idx: fitnesses[idx])


def crossover(
    parent_a: Chromosome, parent_b: Chromosome, rng: Random
) -> tuple[Chromosome, Chromosome]:
    n_employees = len(parent_a)
    if n_employees <= 1:
        return [list(row) for row in parent_a], [list(row) for row in parent_b]
    split = rng.randrange(n_employees - 1)
    child_one: Chromosome = []
    child_two: Chromosome = []
    for e_idx in range(n_employees):
        if e_idx <= split:
            child_one.append(list(parent_a[e_idx]))
            child_two.append(list(parent_b[e_idx]))
        else:
            child_one.append(list(parent_b[e_idx]))
            child_two.append(list(parent_a[e_idx]))
    return child_one, child_two


def mutate(chromosome: Chromosome, problem: _Problem, rng: Random) -> Chromosome:
    mutated = [list(row) for row in chromosome]
    e_idx = rng.randrange(len(mutated))
    d_idx = rng.randrange(len(mutated[e_idx]))
    mutated[e_idx][d_idx] = rng.choice(problem.choices)
    return mutated


def _clone(chromosome: Chromosome) -> Chromosome:
    return [list(row) for row in chromosome]


def run_ga(
    ctx: ScheduleContext,
    config: GAConfig | None = None,
    rng: Random | None = None,
    anytime_callback: Callable[[float, float, bool], None] | None = None,
) -> tuple[EvaluationResult, list[Assignment]]:
    config = config or GAConfig()
    rng = rng or Random()
    problem = _build_problem(ctx)
    start = _time_module.perf_counter()

    population = _seed_population(ctx, problem, config, rng)
    results = [evaluate_individual(ctx, problem, ind) for ind in population]
    fitnesses = [r.fitness for r in results]

    best_idx = max(range(len(fitnesses)), key=lambda i: fitnesses[i])
    best = _clone(population[best_idx])
    best_result = results[best_idx]
    _emit(anytime_callback, start, best_result)

    generations_without_improvement = 0
    for _ in range(config.max_generations):
        if _wall_clock_exceeded(config, start):
            break

        population = _next_generation(
            ctx, problem, config, rng, population, results, fitnesses
        )
        results = [evaluate_individual(ctx, problem, ind) for ind in population]
        fitnesses = [r.fitness for r in results]

        gen_best_idx = max(range(len(fitnesses)), key=lambda i: fitnesses[i])
        if fitnesses[gen_best_idx] > best_result.fitness:
            best = _clone(population[gen_best_idx])
            best_result = results[gen_best_idx]
            generations_without_improvement = 0
            _emit(anytime_callback, start, best_result)
        else:
            generations_without_improvement += 1
            if generations_without_improvement >= config.convergence_patience:
                break

    best_assignments = list(_chromosome_to_assignments(ctx, problem, best))
    return best_result, best_assignments


def _seed_population(
    ctx: ScheduleContext, problem: _Problem, config: GAConfig, rng: Random
) -> list[Chromosome]:
    return [
        _repair(initialize_individual(ctx, problem, rng), problem, rng)
        for _ in range(config.population_size)
    ]


def _next_generation(
    ctx: ScheduleContext,
    problem: _Problem,
    config: GAConfig,
    rng: Random,
    population: list[Chromosome],
    results: list[EvaluationResult],
    fitnesses: list[float],
) -> list[Chromosome]:
    next_population: list[Chromosome] = []

    if config.elitism > 0:
        ranked = sorted(
            range(len(fitnesses)), key=lambda i: fitnesses[i], reverse=True
        )
        for elite_idx in ranked[: config.elitism]:
            next_population.append(_clone(population[elite_idx]))

    while len(next_population) < config.population_size:
        parent_a = population[tournament_select(fitnesses, config.tournament_k, rng)]
        parent_b = population[tournament_select(fitnesses, config.tournament_k, rng)]

        if rng.random() < config.crossover_rate:
            child_one, child_two = crossover(parent_a, parent_b, rng)
        else:
            child_one, child_two = _clone(parent_a), _clone(parent_b)

        for child in (child_one, child_two):
            if rng.random() < config.mutation_rate:
                child = mutate(child, problem, rng)
            child = _repair(child, problem, rng)
            if len(next_population) < config.population_size:
                next_population.append(child)

    return next_population


def _wall_clock_exceeded(config: GAConfig, start: float) -> bool:
    return (
        config.wall_clock_limit is not None
        and _time_module.perf_counter() - start >= config.wall_clock_limit
    )


def _emit(
    callback: Callable[[float, float, bool], None] | None,
    start: float,
    result: EvaluationResult,
) -> None:
    if callback is not None:
        elapsed = _time_module.perf_counter() - start
        callback(elapsed, result.fitness, result.is_feasible)
