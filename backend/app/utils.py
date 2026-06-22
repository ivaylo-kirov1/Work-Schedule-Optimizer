from __future__ import annotations

import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import STATUS_APPROVED
from app.models import Employee, EmployeePreference, LeaveRequest, NonWorkingDate


def get_employee_or_404(employee_id: int, db: Session) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        )
    return employee


def load_approved_leave(
    db: Session,
    employee_ids: list[int],
    period_start: datetime.date,
    period_end: datetime.date,
) -> frozenset[tuple[int, datetime.date]]:
    if not employee_ids:
        return frozenset()

    requests = db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.employee_id.in_(employee_ids),
            LeaveRequest.status == STATUS_APPROVED,
            LeaveRequest.start_date <= period_end,
            LeaveRequest.end_date >= period_start,
        )
    )

    leave_pairs: set[tuple[int, datetime.date]] = set()
    for request in requests:
        window_start = max(request.start_date, period_start)
        window_end = min(request.end_date, period_end)
        span = (window_end - window_start).days
        for offset in range(span + 1):
            leave_pairs.add(
                (request.employee_id, window_start + datetime.timedelta(days=offset))
            )
    return frozenset(leave_pairs)


def load_preferences(
    db: Session, employee_ids: list[int]
) -> dict[int, frozenset[int]]:
    if not employee_ids:
        return {}

    rows = db.scalars(
        select(EmployeePreference).where(
            EmployeePreference.employee_id.in_(employee_ids)
        )
    )
    
    preferences: dict[int, set[int]] = {}
    for row in rows:
        preferences.setdefault(row.employee_id, set()).add(row.day_of_week)
    return {emp_id: frozenset(days) for emp_id, days in preferences.items()}


def load_explicit_non_working_dates(
    db: Session, period_start: datetime.date, period_end: datetime.date
) -> frozenset[datetime.date]:
    return frozenset(
        db.scalars(
            select(NonWorkingDate.date).where(
                NonWorkingDate.date >= period_start,
                NonWorkingDate.date <= period_end,
            )
        )
    )
