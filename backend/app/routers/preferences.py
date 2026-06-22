from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import ROLE_EMPLOYEE, ROLE_MANAGER, get_current_user
from app.database import get_db
from app.models import EmployeePreference, User
from app.schemas.preferences import PreferencesResponse, PreferencesUpdateRequest
from app.utils import get_employee_or_404

router = APIRouter(prefix="/employees", tags=["preferences"])


@router.get("/{employee_id}/preferences", response_model=PreferencesResponse)
def get_preferences(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PreferencesResponse:
    if current_user.role != ROLE_MANAGER and current_user.employee_id != employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only access your own preferences",
        )

    get_employee_or_404(employee_id, db)
    days = db.scalars(
        select(EmployeePreference.day_of_week)
        .where(EmployeePreference.employee_id == employee_id)
        .order_by(EmployeePreference.day_of_week)
    )
    return PreferencesResponse(days=list(days))


@router.put("/{employee_id}/preferences", response_model=PreferencesResponse)
def replace_preferences(
    employee_id: int,
    payload: PreferencesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PreferencesResponse:
    if current_user.role != ROLE_EMPLOYEE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employees may set preferences",
        )
    if current_user.employee_id != employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only set your own preferences",
        )

    get_employee_or_404(employee_id, db)

    db.execute(
        delete(EmployeePreference).where(
            EmployeePreference.employee_id == employee_id
        )
    )
    db.add_all(
        EmployeePreference(employee_id=employee_id, day_of_week=day)
        for day in payload.days
    )
    db.commit()

    return PreferencesResponse(days=payload.days)
