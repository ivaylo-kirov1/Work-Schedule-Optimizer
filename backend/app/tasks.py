from __future__ import annotations

import datetime
import logging
import random
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models 
from app.celery_app import celery_app
from app.constants import STATUS_COMPLETED, STATUS_FAILED, STATUS_RUNNING
from app.database import SessionLocal
from app.models import (
    CompanySettings,
    Employee,
    Schedule,
    ShiftAssignment,
    ShiftType,
    StaffingRequirement,
    Task,
)
from app.optimization.cpsat import CPSATConfig, run_cpsat
from app.optimization.evaluate import Assignment, EvaluationResult, ScheduleContext
from app.optimization.evaluate import Employee as EvalEmployee
from app.optimization.evaluate import ShiftType as EvalShiftType
from app.optimization.ga import GAConfig, run_ga
from app.utils import (
    load_approved_leave,
    load_explicit_non_working_dates,
    load_preferences,
)

logger = logging.getLogger(__name__)

ALGORITHM_GA = "GA"
ALGORITHM_CPSAT = "CP_SAT"

GA_SEED = 42


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _period_bounds(start_date_iso: str, end_date_iso: str) -> tuple[datetime.date, datetime.date]:
    return (
        datetime.date.fromisoformat(start_date_iso),
        datetime.date.fromisoformat(end_date_iso),
    )


def _load_active_employees(db: Session) -> list[Employee]:
    return list(
        db.scalars(
            select(Employee)
            .where(Employee.deactivated_at.is_(None))
            .order_by(Employee.id)
        )
    )


def _load_active_shift_types(db: Session) -> list[ShiftType]:
    return list(
        db.scalars(
            select(ShiftType)
            .where(ShiftType.deactivated_at.is_(None))
            .order_by(ShiftType.id)
        )
    )


def _load_off_weekdays(db: Session) -> frozenset[int]:
    settings = db.get(CompanySettings, 1)
    if settings is None:
        logger.warning(
            "CompanySettings row (id=1) not found; defaulting to 24/7 (no off weekdays). "
            "Run seed.py to populate the settings row."
        )
        return frozenset()
    return frozenset(settings.off_weekdays)


def _build_context(
    db: Session,
    period_start: datetime.date,
    period_end: datetime.date,
    monthly_norms: dict[str, int],
    staffing: dict[str, int],
) -> ScheduleContext:
    employees = _load_active_employees(db)
    shift_types = _load_active_shift_types(db)
    employee_ids = [emp.id for emp in employees]

    approved_leave = load_approved_leave(db, employee_ids, period_start, period_end)
    preferences = load_preferences(db, employee_ids)
    off_weekdays = _load_off_weekdays(db)
    explicit_non_working = load_explicit_non_working_dates(
        db, period_start, period_end
    )

    return ScheduleContext(
        employees=tuple(
            EvalEmployee(id=emp.id, hours_per_week=float(emp.hours_per_week))
            for emp in employees
        ),
        shift_types=tuple(
            EvalShiftType(
                id=st.id, start_time=st.start_time, end_time=st.end_time
            )
            for st in shift_types
        ),
        assignments=(),
        period_start=period_start,
        period_end=period_end,
        monthly_norms={month: float(norm) for month, norm in monthly_norms.items()},
        staffing_requirements={int(key): value for key, value in staffing.items()},
        approved_leave=approved_leave,
        off_weekdays=off_weekdays,
        non_working_dates=explicit_non_working,
        employee_preferences=preferences,
    )


def _run_algorithm(
    algorithm: str, ctx: ScheduleContext
) -> tuple[EvaluationResult, list[Assignment]]:
    if algorithm == ALGORITHM_GA:
        return run_ga(ctx, GAConfig(), rng=random.Random(GA_SEED), anytime_callback=None)
    if algorithm == ALGORITHM_CPSAT:
        result = run_cpsat(ctx, CPSATConfig(), anytime_callback=None)
        return result.evaluation, result.assignments
    raise ValueError(f"Unknown algorithm: {algorithm!r}")


def _build_generation_inputs(ctx: ScheduleContext) -> dict:
    return {
        "off_weekdays": sorted(ctx.off_weekdays),
        "non_working_dates": sorted(d.isoformat() for d in ctx.non_working_dates),
        "shift_types": [
            {
                "id": st.id,
                "start_time": st.start_time.isoformat(),
                "end_time": st.end_time.isoformat(),
            }
            for st in ctx.shift_types
        ],
        "employee_hours": {str(emp.id): emp.hours_per_week for emp in ctx.employees},

        "approved_leave": sorted(
            [emp_id, day.isoformat()] for emp_id, day in ctx.approved_leave
        ),
    }


def _persist_schedule(
    db: Session,
    task_id: uuid.UUID,
    algorithm: str,
    period_start: datetime.date,
    period_end: datetime.date,
    period_norm: int,
    evaluation: EvaluationResult,
    assignments: list[Assignment],
    active_shift_type_ids: list[int],
    staffing: dict[str, int],
    generation_inputs: dict,
) -> None:
    schedule = Schedule(
        task_id=task_id,
        start_date=period_start,
        end_date=period_end,
        period_norm=period_norm,
        fitness_score=evaluation.fitness,
        algorithm=algorithm,
        generation_inputs=generation_inputs,
    )
    db.add(schedule)
    db.flush()

    for shift_type_id in active_shift_type_ids:
        db.add(
            StaffingRequirement(
                schedule_id=schedule.id,
                shift_type_id=shift_type_id,
                min_staff=staffing[str(shift_type_id)],
            )
        )

    db.add_all(
        ShiftAssignment(
            schedule_id=schedule.id,
            employee_id=assignment.employee_id,
            shift_type_id=assignment.shift_type_id,
            date=assignment.date,
        )
        for assignment in assignments
    )


@celery_app.task(bind=True, name="app.tasks.generate_schedule_task")
def generate_schedule_task(
    self,  # noqa: ANN001  (celery binds the task instance here)
    task_id: str,
    algorithm: str,
    start_date_iso: str,
    end_date_iso: str,
    monthly_norms: dict[str, int],
    staffing: dict[str, int],
) -> str:
    task_uuid = uuid.UUID(task_id)
    period_start, period_end = _period_bounds(start_date_iso, end_date_iso)

    with SessionLocal() as db:
        task = db.get(Task, task_uuid)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        task.status = STATUS_RUNNING
        db.commit()

    try:
        with SessionLocal() as db:
            ctx = _build_context(
                db, period_start, period_end, monthly_norms, staffing
            )
            live_shift_ids = {st.id for st in ctx.shift_types}
            payload_shift_ids = {int(k) for k in staffing}
            if live_shift_ids != payload_shift_ids:
                raise ValueError(
                    f"Active shift types changed since the request was validated. "
                    f"Expected {sorted(payload_shift_ids)}, found {sorted(live_shift_ids)}. "
                    f"Re-submit the generation request."
                )
            active_shift_type_ids = [st.id for st in ctx.shift_types]

        evaluation, assignments = _run_algorithm(algorithm, ctx)
        period_norm = sum(monthly_norms.values())
        generation_inputs = _build_generation_inputs(ctx)

        with SessionLocal() as db:
            task = db.get(Task, task_uuid)
            if task is None:
                raise ValueError(f"Task {task_id} not found")
  
            if task.status != STATUS_RUNNING:
                logger.info(
                    "Task %s is %s (not RUNNING); discarding solver result "
                    "without persisting a schedule.",
                    task_id,
                    task.status,
                )
                return task_id

            _persist_schedule(
                db,
                task_uuid,
                algorithm,
                period_start,
                period_end,
                period_norm,
                evaluation,
                assignments,
                active_shift_type_ids,
                staffing,
                generation_inputs,
            )
            task.status = STATUS_COMPLETED
            task.completed_at = _now()
            db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            task = db.get(Task, task_uuid)
            if task is not None:
                task.status = STATUS_FAILED
                task.error = str(exc)[:500]
                task.completed_at = _now()
                db.commit()
        raise

    return task_id
