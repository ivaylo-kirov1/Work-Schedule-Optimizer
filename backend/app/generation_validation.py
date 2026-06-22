from __future__ import annotations

import datetime
import logging
import math

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import STATUS_APPROVED
from app.models import (
    CompanySettings,
    Employee,
    LeaveRequest,
    ShiftType,
)
from app.optimization.evaluate import is_night_shift, shift_duration_hours
from app.optimization.evaluate import ShiftType as EvalShiftType
from app.optimization.weights import C_MAX, N_MAX_NIGHT, OT_MAX, STANDARD_WEEKLY_HOURS
from app.schemas.schedules import GenerateRequest
from app.tasks import ALGORITHM_CPSAT, ALGORITHM_GA
from app.utils import load_explicit_non_working_dates

logger = logging.getLogger(__name__)

ALLOWED_ALGORITHMS = (ALGORITHM_GA, ALGORITHM_CPSAT)
MAX_MONTHS = 12
MIN_NORM = 1
MAX_NORM = 300
WEEKEND_WEEKDAYS = frozenset({5, 6})


def _parse_month(value: str) -> tuple[int, int]:
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError(f"Month '{value}' is not in YYYY-MM format")
    year_str, month_str = parts
    if len(year_str) != 4 or len(month_str) != 2:
        raise ValueError(f"Month '{value}' is not in YYYY-MM format")
    try:
        year, month = int(year_str), int(month_str)
    except ValueError:
        raise ValueError(f"Month '{value}' is not in YYYY-MM format")
    if not (1 <= month <= 12):
        raise ValueError(f"Month '{value}' has an invalid month component")
    return year, month


def _month_sequence(start: tuple[int, int], end: tuple[int, int]) -> list[str]:
    months: list[str] = []
    year, month = start
    end_year, end_month = end
    while (year, month) <= (end_year, end_month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def _period_bounds(
    start: tuple[int, int], end: tuple[int, int]
) -> tuple[datetime.date, datetime.date]:
    start_date = datetime.date(start[0], start[1], 1)
    next_month_year = end[0] + (1 if end[1] == 12 else 0)
    next_month = 1 if end[1] == 12 else end[1] + 1
    end_date = datetime.date(next_month_year, next_month, 1) - datetime.timedelta(days=1)
    return start_date, end_date


def _http_422(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _validate_months(
    payload: GenerateRequest,
) -> tuple[tuple[int, int], tuple[int, int], list[str]]:
    try:
        start = _parse_month(payload.start_month)
        end = _parse_month(payload.end_month)
    except ValueError as exc:
        raise _http_422(str(exc))

    if start > end:
        raise _http_422("start_month must not be after end_month")

    months = _month_sequence(start, end)
    if len(months) > MAX_MONTHS:
        raise _http_422(f"Planning period must not exceed {MAX_MONTHS} months")
    return start, end, months


def _validate_norms(payload: GenerateRequest, months: list[str]) -> None:
    expected = set(months)
    provided = set(payload.monthly_norms)
    if provided != expected:
        missing = sorted(expected - provided)
        extra = sorted(provided - expected)
        raise _http_422(
            f"monthly_norms must have exactly one entry per month. "
            f"Missing: {missing or 'none'}; unexpected: {extra or 'none'}"
        )
    for month, norm in payload.monthly_norms.items():
        if not (MIN_NORM <= norm <= MAX_NORM):
            raise _http_422(
                f"Norm for {month} must be between {MIN_NORM} and {MAX_NORM} hours"
            )



def _validate_staffing(
    payload: GenerateRequest, shift_types: list[ShiftType], employee_count: int
) -> None:
    try:
        provided_ids = {int(key) for key in payload.staffing}
    except ValueError:
        raise _http_422("staffing keys must be integer shift_type ids")

    active_ids = {st.id for st in shift_types}
    if provided_ids != active_ids:
        raise _http_422(
            f"staffing must cover exactly the active shift types {sorted(active_ids)}"
        )
    for key, required in payload.staffing.items():
        if required < 1:
            raise _http_422(f"Staffing for shift {key} must be at least 1")
        if required > employee_count:
            raise _http_422(
                f"Staffing for shift {key} ({required}) exceeds the "
                f"{employee_count} active employees"
            )


def _derive_non_working_dates(
    db: Session,
    off_weekdays: frozenset[int],
    period_start: datetime.date,
    period_end: datetime.date,
) -> set[datetime.date]:
    explicit = set(load_explicit_non_working_dates(db, period_start, period_end))
    span = (period_end - period_start).days
    weekday_off = {
        period_start + datetime.timedelta(days=offset)
        for offset in range(span + 1)
        if (period_start + datetime.timedelta(days=offset)).weekday() in off_weekdays
    }
    return explicit | weekday_off



def _validate_working_days(
    db: Session,
    off_weekdays: frozenset[int],
    period_start: datetime.date,
    period_end: datetime.date,
) -> None:
    non_working = _derive_non_working_dates(
        db, off_weekdays, period_start, period_end
    )
    total_days = (period_end - period_start).days + 1
    if len(non_working) >= total_days:
        raise _http_422("The planning period contains no working days")


def _validate_five_day_night_cap(
    off_weekdays: frozenset[int], shift_types: list[ShiftType]
) -> None:
    if off_weekdays != WEEKEND_WEEKDAYS:
        return
    for st in shift_types:
        eval_shift = EvalShiftType(
            id=st.id, start_time=st.start_time, end_time=st.end_time
        )
        if is_night_shift(eval_shift) and shift_duration_hours(eval_shift) > N_MAX_NIGHT:
            raise _http_422(
                f"Shift '{st.name}' is a night shift longer than {N_MAX_NIGHT}h, "
                f"which is never legal under the five-day (Mon-Fri) regime. "
                f"No feasible schedule can include it; deactivate or shorten it first."
            )



def _validate_capacity(
    off_weekdays: frozenset[int],
    n_employees: int,
    staffing: dict[str, int],
) -> None:
    sum_rs = sum(staffing.values())
    is_five_day = off_weekdays == WEEKEND_WEEKDAYS
    if is_five_day:
        min_employees = sum_rs
        feasible = n_employees >= min_employees
        regime_note = f"five-day (Mon-Fri) regime: workforce must cover all {sum_rs} position(s) simultaneously on each weekday"
    else:
        min_employees = math.ceil(sum_rs * (C_MAX + 2) / C_MAX)
        feasible = n_employees * C_MAX >= sum_rs * (C_MAX + 2)
        regime_note = (
            f"summarized regime: mandatory {C_MAX}-on-2-off rotation limits "
            f"coverage to {C_MAX}/{C_MAX + 2} of employees per day"
        )
    if not feasible:
        raise _http_422(
            f"Insufficient workforce: {n_employees} active employee(s) cannot cover "
            f"{sum_rs} position(s) per day ({regime_note}). "
            f"Need at least {min_employees} active employee(s)."
        )


def _load_overlapping_leave(
    db: Session,
    employee_ids: list[int],
    period_start: datetime.date,
    period_end: datetime.date,
) -> list[LeaveRequest]:
    if not employee_ids:
        return []
    return list(
        db.scalars(
            select(LeaveRequest).where(
                LeaveRequest.employee_id.in_(employee_ids),
                LeaveRequest.status == STATUS_APPROVED,
                LeaveRequest.start_date <= period_end,
                LeaveRequest.end_date >= period_start,
            )
        )
    )


def _leave_reduction_by_employee(
    leave_requests: list[LeaveRequest],
    explicit_non_working: set[datetime.date],
    employee_hours: dict[int, float],
    period_start: datetime.date,
    period_end: datetime.date,
) -> dict[int, float]:
    leave_days: set[tuple[int, datetime.date]] = set()
    for request in leave_requests:
        window_start = max(request.start_date, period_start)
        window_end = min(request.end_date, period_end)
        span = (window_end - window_start).days
        for offset in range(span + 1):
            leave_days.add(
                (request.employee_id, window_start + datetime.timedelta(days=offset))
            )

    reduction: dict[int, float] = {}
    for employee_id, day in leave_days:
        if day.weekday() >= 5 or day in explicit_non_working:
            continue
        hours_per_week = employee_hours.get(employee_id)
        if hours_per_week is None:
            continue
        reduction[employee_id] = reduction.get(employee_id, 0.0) + hours_per_week / 5.0
    return reduction



def _validate_hours_balance(
    db: Session,
    off_weekdays: frozenset[int],
    period_start: datetime.date,
    period_end: datetime.date,
    shift_types: list[ShiftType],
    employees: list[Employee],
    staffing: dict[str, int],
    monthly_norms: dict[str, int],
    leave_requests: list[LeaveRequest],
) -> None:
    non_working = _derive_non_working_dates(db, off_weekdays, period_start, period_end)
    working_days = (period_end - period_start).days + 1 - len(non_working)
    daily_demand = sum(
        staffing[str(st.id)]
        * shift_duration_hours(
            EvalShiftType(id=st.id, start_time=st.start_time, end_time=st.end_time)
        )
        for st in shift_types
    )
    demand_hours = working_days * daily_demand
    m_period = sum(monthly_norms.values())

    explicit_non_working = set(
        load_explicit_non_working_dates(db, period_start, period_end)
    )
    employee_hours = {emp.id: float(emp.hours_per_week) for emp in employees}
    reduction = _leave_reduction_by_employee(
        leave_requests, explicit_non_working, employee_hours, period_start, period_end
    )
    contracted_cap = (
        sum(
            max(
                0.0,
                m_period * emp.hours_per_week / STANDARD_WEEKLY_HOURS
                - reduction.get(emp.id, 0.0),
            )
            for emp in employees
        )
        + len(employees) * OT_MAX
    )
    if demand_hours > contracted_cap + 1e-9:
        extra = math.ceil((demand_hours - contracted_cap) / m_period)
        raise _http_422(
            f"Total staffed hours for the period ({demand_hours:.0f}h) exceed the "
            f"workforce's total contracted hours ({contracted_cap:.0f}h, after "
            f"approved-leave reductions). Exact staffing requires every slot to be "
            f"filled and no employee may exceed their contracted norm (no overtime), "
            f"so no feasible schedule exists. Reduce staffing or shift lengths, or "
            f"add at least {extra} more full-time employee(s)."
        )


def _validate_leave_coverage(
    db: Session,
    off_weekdays: frozenset[int],
    period_start: datetime.date,
    period_end: datetime.date,
    employees: list[Employee],
    staffing: dict[str, int],
    leave_requests: list[LeaveRequest],
) -> None:
    sum_rs = sum(staffing.values())
    n_employees = len(employees)

    if not leave_requests:
        return

    non_working = _derive_non_working_dates(db, off_weekdays, period_start, period_end)

    worst_day: datetime.date | None = None
    worst_available = n_employees
    bad_days: list[datetime.date] = []
    span = (period_end - period_start).days
    for offset in range(span + 1):
        day = period_start + datetime.timedelta(days=offset)
        if day in non_working:
            continue
        on_leave = {
            req.employee_id
            for req in leave_requests
            if req.start_date <= day <= req.end_date
        }
        available = n_employees - len(on_leave)
        if available < sum_rs:
            bad_days.append(day)
            if worst_day is None or available < worst_available:
                worst_day = day
                worst_available = available

    if worst_day is not None:
        raise _http_422(
            f"Approved leave makes {len(bad_days)} working day(s) impossible to staff: "
            f"on {worst_day.isoformat()}, only {worst_available} of {n_employees} "
            f"employee(s) are available but {sum_rs} position(s) must be filled by "
            f"distinct employees. Adjust the overlapping leave, reduce staffing, or "
            f"add employees."
        )


def validate_generation_request(
    payload: GenerateRequest, db: Session
) -> tuple[datetime.date, datetime.date]:
    if payload.algorithm not in ALLOWED_ALGORITHMS:
        raise _http_422(
            f"algorithm must be one of {list(ALLOWED_ALGORITHMS)}"
        )

    start, end, months = _validate_months(payload)
    _validate_norms(payload, months)

    employees = list(
        db.scalars(select(Employee).where(Employee.deactivated_at.is_(None)))
    )
    if not employees:
        raise _http_422("At least one active employee is required")

    shift_types = list(
        db.scalars(select(ShiftType).where(ShiftType.deactivated_at.is_(None)))
    )
    if not shift_types:
        raise _http_422("At least one active shift type is required")

    _validate_staffing(payload, shift_types, len(employees))

    period_start, period_end = _period_bounds(start, end)
    settings = db.get(CompanySettings, 1)
    if settings is None:
        logger.warning(
            "CompanySettings row (id=1) not found; defaulting to 24/7 schedule. Run seed.py."
        )
    off_weekdays = frozenset(settings.off_weekdays) if settings else frozenset()

    _validate_working_days(db, off_weekdays, period_start, period_end)
    _validate_five_day_night_cap(off_weekdays, shift_types)
    _validate_capacity(off_weekdays, len(employees), dict(payload.staffing))

    # the hours balance subtracts statutory leave reductions from the contracted cap, and the coverage check ensures each working day still has enough staff
    leave_requests = _load_overlapping_leave(
        db, [emp.id for emp in employees], period_start, period_end
    )

    _validate_hours_balance(
        db,
        off_weekdays,
        period_start,
        period_end,
        shift_types,
        employees,
        dict(payload.staffing),
        dict(payload.monthly_norms),
        leave_requests,
    )
    _validate_leave_coverage(
        db,
        off_weekdays,
        period_start,
        period_end,
        employees,
        dict(payload.staffing),
        leave_requests,
    )

    return period_start, period_end
