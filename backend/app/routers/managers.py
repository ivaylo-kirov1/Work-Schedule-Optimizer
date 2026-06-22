from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ROLE_MANAGER, hash_password, require_manager
from app.database import get_db
from app.models import User
from app.schemas.managers import (
    ManagerCreateRequest,
    ManagerCredentialResponse,
    ManagerResponse,
)
from app.security import generate_temp_password

router = APIRouter(prefix="/managers", tags=["managers"])


def _get_manager_or_404(manager_id: int, db: Session) -> User:
    user = db.get(User, manager_id)
    if user is None or user.role != ROLE_MANAGER or user.employee_id is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Manager not found"
        )
    return user


def _count_managers(db: Session) -> int:
    return db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == ROLE_MANAGER, User.employee_id.is_(None))
    ) or 0


@router.get("", response_model=list[ManagerResponse])
def list_managers(
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> list[ManagerResponse]:
    managers = db.scalars(
        select(User)
        .where(User.role == ROLE_MANAGER, User.employee_id.is_(None))
        .order_by(User.id)
    )
    return [ManagerResponse.model_validate(manager) for manager in managers]


@router.post(
    "", response_model=ManagerCredentialResponse, status_code=status.HTTP_201_CREATED
)
def create_manager(
    payload: ManagerCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> ManagerCredentialResponse:
    email = payload.email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    temp_password = generate_temp_password()
    manager = User(
        email=email,
        password_hash=hash_password(temp_password),
        role=ROLE_MANAGER,
        employee_id=None,
    )
    db.add(manager)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    return ManagerCredentialResponse(
        user_id=manager.id,
        email=manager.email,
        temp_password=temp_password,
    )



@router.post(
    "/{manager_id}/reset-password", response_model=ManagerCredentialResponse
)
def reset_manager_password(
    manager_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> ManagerCredentialResponse:
    manager = _get_manager_or_404(manager_id, db)
    temp_password = generate_temp_password()
    manager.password_hash = hash_password(temp_password)
    db.commit()

    return ManagerCredentialResponse(
        user_id=manager.id,
        email=manager.email,
        temp_password=temp_password,
    )



@router.delete("/{manager_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_manager(
    manager_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> None:
    manager = _get_manager_or_404(manager_id, db)
    if _count_managers(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete the last remaining manager",
        )
    db.delete(manager)
    db.commit()
