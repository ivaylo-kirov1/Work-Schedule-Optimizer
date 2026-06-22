from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_manager
from app.database import get_db
from app.models import NonWorkingDate, User
from app.schemas.non_working_dates import (
    NonWorkingDateCreateRequest,
    NonWorkingDateResponse,
    NonWorkingDateUpdateRequest,
)

router = APIRouter(prefix="/non-working-dates", tags=["non-working-dates"])


def _get_or_404(date_id: int, db: Session) -> NonWorkingDate:
    entry = db.get(NonWorkingDate, date_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Non-working date not found",
        )
    return entry


def _date_taken(
    db: Session, target: datetime.date, exclude_id: int | None = None
) -> bool:
    stmt = select(NonWorkingDate.id).where(NonWorkingDate.date == target)
    if exclude_id is not None:
        stmt = stmt.where(NonWorkingDate.id != exclude_id)
    return db.scalar(stmt) is not None


@router.get("", response_model=list[NonWorkingDateResponse])
def list_non_working_dates(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[NonWorkingDateResponse]:
    entries = db.scalars(select(NonWorkingDate).order_by(NonWorkingDate.date))
    return [NonWorkingDateResponse.model_validate(entry) for entry in entries]


@router.post(
    "", response_model=NonWorkingDateResponse, status_code=status.HTTP_201_CREATED
)
def create_non_working_date(
    payload: NonWorkingDateCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> NonWorkingDateResponse:
    if _date_taken(db, payload.date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This date is already marked non-working",
        )
    entry = NonWorkingDate(date=payload.date, note=payload.note)
    db.add(entry)
    db.commit()
    return NonWorkingDateResponse.model_validate(entry)



@router.put("/{date_id}", response_model=NonWorkingDateResponse)
def update_non_working_date(
    date_id: int,
    payload: NonWorkingDateUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> NonWorkingDateResponse:
    entry = _get_or_404(date_id, db)
    if payload.date is not None:
        if _date_taken(db, payload.date, exclude_id=date_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another entry already uses this date",
            )
        entry.date = payload.date
    if payload.note is not None:
        entry.note = payload.note
    db.commit()
    return NonWorkingDateResponse.model_validate(entry)


@router.delete("/{date_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_non_working_date(
    date_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> None:
    entry = _get_or_404(date_id, db)
    db.delete(entry)
    db.commit()
