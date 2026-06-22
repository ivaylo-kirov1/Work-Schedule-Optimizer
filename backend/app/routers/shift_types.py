from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_manager
from app.database import get_db
from app.models import ShiftType, User
from app.optimization.weights import MAX_SHIFT_HOURS
from app.schemas.shift_types import ShiftTypeResponse, ShiftTypeWriteRequest

router = APIRouter(prefix="/shift-types", tags=["shift-types"])

MINUTES_PER_HOUR = 60
MINUTES_PER_DAY = 24 * 60


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _shift_duration_hours(start: datetime.time, end: datetime.time) -> float:
    start_m = start.hour * MINUTES_PER_HOUR + start.minute
    end_m = end.hour * MINUTES_PER_HOUR + end.minute
    if end_m == start_m:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Shift start and end times must differ",
        )
    if end_m < start_m:  # midnight-crossing
        end_m += MINUTES_PER_DAY
    return (end_m - start_m) / MINUTES_PER_HOUR


def _validate_duration(start: datetime.time, end: datetime.time) -> None:
    duration = _shift_duration_hours(start, end)
    if duration <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Shift duration must be greater than 0 hours",
        )
    if duration > MAX_SHIFT_HOURS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Shift duration must not exceed {MAX_SHIFT_HOURS} hours",
        )


def _to_response(shift_type: ShiftType) -> ShiftTypeResponse:
    return ShiftTypeResponse(
        id=shift_type.id,
        name=shift_type.name,
        start_time=shift_type.start_time,
        end_time=shift_type.end_time,
        deactivated_at=shift_type.deactivated_at,
        is_active=shift_type.deactivated_at is None,
    )


def _get_shift_type_or_404(shift_type_id: int, db: Session) -> ShiftType:
    shift_type = db.get(ShiftType, shift_type_id)
    if shift_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shift type not found"
        )
    return shift_type


@router.get("", response_model=list[ShiftTypeResponse])
def list_shift_types(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ShiftTypeResponse]:
    shift_types = db.scalars(select(ShiftType).order_by(ShiftType.id))
    return [_to_response(shift_type) for shift_type in shift_types]


@router.post(
    "", response_model=ShiftTypeResponse, status_code=status.HTTP_201_CREATED
)
def create_shift_type(
    payload: ShiftTypeWriteRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> ShiftTypeResponse:
    _validate_duration(payload.start_time, payload.end_time)
    shift_type = ShiftType(
        name=payload.name,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(shift_type)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active shift type with this name already exists",
        )
    return _to_response(shift_type)


@router.put("/{shift_type_id}", response_model=ShiftTypeResponse)
def update_shift_type(
    shift_type_id: int,
    payload: ShiftTypeWriteRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> ShiftTypeResponse:
    _validate_duration(payload.start_time, payload.end_time)
    shift_type = _get_shift_type_or_404(shift_type_id, db)
    shift_type.name = payload.name
    shift_type.start_time = payload.start_time
    shift_type.end_time = payload.end_time
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active shift type with this name already exists",
        )
    return _to_response(shift_type)


@router.delete("/{shift_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_shift_type(
    shift_type_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> None:
    shift_type = _get_shift_type_or_404(shift_type_id, db)
    if shift_type.deactivated_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shift type is already deactivated",
        )
    shift_type.deactivated_at = _now()
    db.commit()
