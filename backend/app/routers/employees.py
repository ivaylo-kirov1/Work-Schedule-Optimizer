from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ROLE_EMPLOYEE, hash_password, require_manager
from app.database import get_db
from app.models import Employee, User
from app.schemas.employees import (
    CredentialResponse,
    EmployeeCreateRequest,
    EmployeeResponse,
    EmployeeUpdateRequest,
)
from app.security import generate_temp_password
from app.utils import get_employee_or_404

router = APIRouter(prefix="/employees", tags=["employees"])


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _to_response(employee: Employee) -> EmployeeResponse:
    return EmployeeResponse(
        id=employee.id,
        name=employee.name,
        role=employee.role,
        hours_per_week=employee.hours_per_week,
        deactivated_at=employee.deactivated_at,
        is_active=employee.deactivated_at is None,
    )



@router.get("", response_model=list[EmployeeResponse])
def list_employees(
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> list[EmployeeResponse]:
    employees = db.scalars(select(Employee).order_by(Employee.id))
    return [_to_response(employee) for employee in employees]


@router.post(
    "", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED
)
def create_employee(
    payload: EmployeeCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> CredentialResponse:
    email = payload.email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    temp_password = generate_temp_password()
    employee = Employee(
        name=payload.name,
        role=payload.role,
        hours_per_week=payload.hours_per_week,
    )
    db.add(employee)
    db.flush()

    user = User(
        email=email,
        password_hash=hash_password(temp_password),
        role=ROLE_EMPLOYEE,
        employee_id=employee.id,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    return CredentialResponse(
        employee_id=employee.id,
        user_id=user.id,
        email=user.email,
        temp_password=temp_password,
    )


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> EmployeeResponse:
    employee = get_employee_or_404(employee_id, db)
    employee.name = payload.name
    employee.role = payload.role
    employee.hours_per_week = payload.hours_per_week
    db.commit()
    return _to_response(employee)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> None:
    employee = get_employee_or_404(employee_id, db)
    if employee.deactivated_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee is already deactivated",
        )
    employee.deactivated_at = _now()
    db.commit()


@router.post("/{employee_id}/reset-password", response_model=CredentialResponse)
def reset_employee_password(
    employee_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> CredentialResponse:
    employee = get_employee_or_404(employee_id, db)
    if employee.deactivated_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot reset password for a deactivated employee",
        )

    user = db.scalar(select(User).where(User.employee_id == employee_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user account linked to this employee",
        )

    temp_password = generate_temp_password()
    user.password_hash = hash_password(temp_password)
    db.commit()

    return CredentialResponse(
        employee_id=employee.id,
        user_id=user.id,
        email=user.email,
        temp_password=temp_password,
    )
