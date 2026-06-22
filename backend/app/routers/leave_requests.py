from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_employee, require_manager
from app.constants import STATUS_APPROVED, STATUS_PENDING, STATUS_REJECTED
from app.database import get_db
from app.models import LeaveRequest, User
from app.schemas.leave_requests import LeaveRequestCreate, LeaveRequestResponse

router = APIRouter(prefix="/leave-requests", tags=["leave-requests"])

ALLOWED_FILTER_STATUSES = frozenset(
    {STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED}
)


def _current_employee_id(current_user: User) -> int:
    if current_user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not linked to an employee",
        )
    return current_user.employee_id


def _get_or_404(request_id: int, db: Session) -> LeaveRequest:
    leave = db.get(LeaveRequest, request_id)
    if leave is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found"
        )
    return leave


def _require_decidable(leave: LeaveRequest) -> None:
    if leave.status != STATUS_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Leave request is already {leave.status}",
        )


@router.post(
    "", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED
)
def create_leave_request(
    payload: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_employee),
) -> LeaveRequestResponse:
    employee_id = _current_employee_id(current_user)
    leave = LeaveRequest(
        employee_id=employee_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        note=payload.note,
        status=STATUS_PENDING,
    )
    db.add(leave)
    db.commit()
    return LeaveRequestResponse.model_validate(leave)


@router.get("", response_model=list[LeaveRequestResponse])
def list_leave_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> list[LeaveRequestResponse]:
    stmt = select(LeaveRequest).order_by(LeaveRequest.start_date)
    if status_filter is not None:
        if status_filter not in ALLOWED_FILTER_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"status must be one of {sorted(ALLOWED_FILTER_STATUSES)}",
            )
        stmt = stmt.where(LeaveRequest.status == status_filter)
    requests = db.scalars(stmt)
    return [LeaveRequestResponse.model_validate(leave) for leave in requests]


@router.get("/mine", response_model=list[LeaveRequestResponse])
def list_my_leave_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_employee),
) -> list[LeaveRequestResponse]:
    employee_id = _current_employee_id(current_user)
    requests = db.scalars(
        select(LeaveRequest)
        .where(LeaveRequest.employee_id == employee_id)
        .order_by(LeaveRequest.start_date)
    )
    return [LeaveRequestResponse.model_validate(leave) for leave in requests]


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_leave_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_employee),
) -> None:
    employee_id = _current_employee_id(current_user)
    leave = _get_or_404(request_id, db)
    if leave.employee_id != employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only cancel your own leave requests",
        )
    if leave.status != STATUS_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel a leave request that is already {leave.status}",
        )
    db.delete(leave)
    db.commit()


@router.patch("/{request_id}/approve", response_model=LeaveRequestResponse)
def approve_leave_request(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> LeaveRequestResponse:
    leave = _get_or_404(request_id, db)
    _require_decidable(leave)
    leave.status = STATUS_APPROVED
    db.commit()
    return LeaveRequestResponse.model_validate(leave)


@router.patch("/{request_id}/reject", response_model=LeaveRequestResponse)
def reject_leave_request(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> LeaveRequestResponse:
    leave = _get_or_404(request_id, db)
    _require_decidable(leave)
    leave.status = STATUS_REJECTED
    db.commit()
    return LeaveRequestResponse.model_validate(leave)
