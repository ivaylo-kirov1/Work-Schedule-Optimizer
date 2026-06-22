from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_manager
from app.database import get_db
from app.models import Task, User
from app.schemas.schedules import (
    GenerateRequest,
    GenerateResponse,
    TaskStatusResponse,
)
from app.celery_app import celery_app
from app.constants import STATUS_FAILED, STATUS_PENDING, STATUS_RUNNING
from app.generation_validation import validate_generation_request
from app.tasks import generate_schedule_task

router = APIRouter(tags=["schedules"])


@router.post(
    "/schedules/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_schedule(
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> GenerateResponse:
    period_start, period_end = validate_generation_request(payload, db)

    task = Task(status=STATUS_PENDING)
    db.add(task)
    db.flush()
    task_id = task.id
    db.commit()

    # pinning the celery task id to the app task id so a later delete can revoke this exact run
    generate_schedule_task.apply_async(
        kwargs={
            "task_id": str(task_id),
            "algorithm": payload.algorithm,
            "start_date_iso": period_start.isoformat(),
            "end_date_iso": period_end.isoformat(),
            "monthly_norms": dict(payload.monthly_norms),
            "staffing": dict(payload.staffing),
        },
        task_id=str(task_id),
    )
    return GenerateResponse(task_id=str(task_id))


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> None:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status not in (STATUS_PENDING, STATUS_RUNNING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is already {task.status} and cannot be cancelled",
        )
    task.status = STATUS_FAILED
    task.error = "Cancelled by manager"
    task.completed_at = datetime.datetime.now(datetime.UTC)
    db.commit()
 
    celery_app.control.revoke(str(task_id), terminate=True, signal="SIGKILL")


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
def get_task_status(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> TaskStatusResponse:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return TaskStatusResponse(
        task_id=str(task.id),
        status=task.status,
        error=task.error,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )
