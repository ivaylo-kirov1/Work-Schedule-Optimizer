from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import date, time, timedelta
from random import Random

from app.optimization.evaluate import Employee, ScheduleContext, ShiftType
from app.optimization.weights import C_MAX

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)
PERIOD_KEY = "2026-06"

MONTHLY_NORM_HOURS = 176.0

HOURS_PER_WEEK = 40.0
MEAN_SHIFT_DURATION = 8.0
SHIFTS_PER_DAY = 3
WORKING_DAYS = 30


PREFERENCE_PROBABILITY = float(os.getenv("BENCH_PREF_PROB", "0.30"))
WEEKDAYS = 7
FEASIBILITY_MARGIN = 1.15

SHIFT_TYPES: tuple[ShiftType, ...] = (
    ShiftType(id=1, start_time=time(8, 0), end_time=time(16, 0)),
    ShiftType(id=2, start_time=time(16, 0), end_time=time(0, 0)),
    ShiftType(id=3, start_time=time(0, 0), end_time=time(8, 0)),
)


@dataclass(frozen=True, slots=True)
class SizeSpec:
    name: str
    n_employees: int
    staff_per_shift: int
    feasibility_margin: float = FEASIBILITY_MARGIN


SIZE_SPECS: tuple[SizeSpec, ...] = (
    SizeSpec(name="small", n_employees=5, staff_per_shift=1),
    SizeSpec(name="medium", n_employees=15, staff_per_shift=3),
    SizeSpec(name="large", n_employees=30, staff_per_shift=6),
)


TIGHT_SPEC: SizeSpec = SizeSpec(
    name="tight", n_employees=14, staff_per_shift=3, feasibility_margin=1.0
)

ALL_SPECS: tuple[SizeSpec, ...] = SIZE_SPECS + (TIGHT_SPEC,)

SIZE_BY_NAME: dict[str, SizeSpec] = {spec.name: spec for spec in ALL_SPECS}


def assert_feasible_precondition(spec: SizeSpec) -> None:
    
    full_cycles, remainder = divmod(WORKING_DAYS, C_MAX + 2)
    rotation_cap = full_cycles * C_MAX + min(remainder, C_MAX)
    per_employee_cap = min(
        rotation_cap, math.floor(MONTHLY_NORM_HOURS / MEAN_SHIFT_DURATION)
    )
    capacity = spec.n_employees * per_employee_cap
    demand = SHIFTS_PER_DAY * WORKING_DAYS * spec.staff_per_shift
    if capacity < spec.feasibility_margin * demand:
        raise ValueError(
            f"size {spec.name!r} fails feasibility precondition: "
            f"capacity={capacity} < {spec.feasibility_margin} * demand={demand}"
        )


def _generate_preferences(spec: SizeSpec, seed: int) -> dict[int, frozenset[int]]:
    rng = Random(seed)
    preferences: dict[int, frozenset[int]] = {}
    for emp_id in range(1, spec.n_employees + 1):
        preferred_off = {
            weekday
            for weekday in range(WEEKDAYS)
            if rng.random() < PREFERENCE_PROBABILITY
        }
        preferences[emp_id] = frozenset(preferred_off)
    return preferences


def build_instance(size: str, seed: int) -> ScheduleContext:
    if size == REALISTIC_NAME:
        return build_realistic_instance(seed)
    if size not in SIZE_BY_NAME:
        raise ValueError(f"unknown size {size!r}; expected one of {list(SIZE_BY_NAME)}")
    spec = SIZE_BY_NAME[size]
    assert_feasible_precondition(spec)

    employees = tuple(
        Employee(id=emp_id, hours_per_week=HOURS_PER_WEEK)
        for emp_id in range(1, spec.n_employees + 1)
    )
    staffing_requirements = {st.id: spec.staff_per_shift for st in SHIFT_TYPES}

    return ScheduleContext(
        employees=employees,
        shift_types=SHIFT_TYPES,
        assignments=(),
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        monthly_norms={PERIOD_KEY: MONTHLY_NORM_HOURS},
        staffing_requirements=staffing_requirements,
        approved_leave=frozenset(),
        off_weekdays=frozenset(),
        non_working_dates=frozenset(),
        employee_preferences=_generate_preferences(spec, seed),
    )





REALISTIC_NAME = "realistic"

REALISTIC_SHIFT_TYPES: tuple[ShiftType, ...] = (
    ShiftType(id=1, start_time=time(8, 0), end_time=time(20, 0)),   # day, 12h
    ShiftType(id=2, start_time=time(20, 0), end_time=time(8, 0)),   # night, 12h (>=4h night labor)
)
REALISTIC_STAFF_PER_SHIFT = 2


REALISTIC_TEAM: tuple[tuple[str, float], ...] = (
    ("Старша медицинска сестра", 40.0),
    ("Медицинска сестра", 40.0),
    ("Медицинска сестра", 40.0),
    ("Медицинска сестра", 40.0),
    ("Медицинска сестра", 40.0),
    ("Медицинска сестра", 40.0),
    ("Медицинска сестра", 30.0),
    ("Медицинска сестра", 30.0),
    ("Санитар", 40.0),
    ("Санитар", 40.0),
    ("Санитар", 20.0),
    ("Санитар", 20.0),
)

REALISTIC_N_ON_LEAVE = 4
REALISTIC_LEAVE_MIN_DAYS = 5
REALISTIC_LEAVE_MAX_DAYS = 9


REALISTIC_SPEC: SizeSpec = SizeSpec(
    name=REALISTIC_NAME,
    n_employees=len(REALISTIC_TEAM),
    staff_per_shift=REALISTIC_STAFF_PER_SHIFT,
    feasibility_margin=1.0,
)


def realistic_team_composition() -> tuple[tuple[int, str, float], ...]:
    return tuple(
        (emp_id, role, hours)
        for emp_id, (role, hours) in enumerate(REALISTIC_TEAM, start=1)
    )


def _generate_realistic_leave(seed: int) -> frozenset[tuple[int, date]]:
    # decorrelate the leave RNG stream from the preference RNG stream
    rng = Random(seed * 7919 + 1)
    n = len(REALISTIC_TEAM)
    total_days = (PERIOD_END - PERIOD_START).days + 1
    on_leave = rng.sample(range(1, n + 1), k=min(REALISTIC_N_ON_LEAVE, n))
    leave: set[tuple[int, date]] = set()
    for emp_id in on_leave:
        span = rng.randint(REALISTIC_LEAVE_MIN_DAYS, REALISTIC_LEAVE_MAX_DAYS)
        start_offset = rng.randint(0, total_days - span)
        for offset in range(span):
            leave.add((emp_id, PERIOD_START + timedelta(days=start_offset + offset)))
    return frozenset(leave)


def _generate_realistic_preferences(seed: int) -> dict[int, frozenset[int]]:
    rng = Random(seed)
    preferences: dict[int, frozenset[int]] = {}
    for emp_id in range(1, len(REALISTIC_TEAM) + 1):
        # each employee gets their own preferred-off density 
        density = rng.uniform(0.10, 0.50)
        preferences[emp_id] = frozenset(
            weekday for weekday in range(WEEKDAYS) if rng.random() < density
        )
    return preferences


def build_realistic_instance(seed: int) -> ScheduleContext:
    employees = tuple(
        Employee(id=emp_id, hours_per_week=hours)
        for emp_id, (_role, hours) in enumerate(REALISTIC_TEAM, start=1)
    )
    staffing_requirements = {
        st.id: REALISTIC_STAFF_PER_SHIFT for st in REALISTIC_SHIFT_TYPES
    }
    return ScheduleContext(
        employees=employees,
        shift_types=REALISTIC_SHIFT_TYPES,
        assignments=(),
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        monthly_norms={PERIOD_KEY: MONTHLY_NORM_HOURS},
        staffing_requirements=staffing_requirements,
        approved_leave=_generate_realistic_leave(seed),
        off_weekdays=frozenset(),
        non_working_dates=frozenset(),
        employee_preferences=_generate_realistic_preferences(seed),
    )
