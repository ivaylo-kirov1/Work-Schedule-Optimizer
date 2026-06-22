from __future__ import annotations

import datetime
import io

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_employee, require_manager
from app.database import get_db
from app.models import (
    CompanySettings,
    Employee,
    NonWorkingDate,
    Schedule,
    ShiftAssignment,
    ShiftType,
    Task,
    User,
)
from app.optimization.evaluate import Assignment, ScheduleContext, evaluate_schedule
from app.optimization.evaluate import Employee as EvalEmployee
from app.optimization.evaluate import ShiftType as EvalShiftType
from app.routers.schedule_excel import render_schedule_xlsx
from app.utils import load_approved_leave, load_preferences
from app.schemas.schedule_views import (
    EmployeeScheduleEntry,
    HardViolations,
    ScheduleAssignment,
    ScheduleDetail,
    ScheduleEmployee,
    ScheduleListItem,
    ScheduleShiftType,
    SoftViolations,
)

router = APIRouter(tags=["schedule-views"])


def _get_schedule_or_404(schedule_id: int, db: Session) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )
    return schedule


def _latest_schedule(db: Session) -> Schedule | None:
    return db.scalar(select(Schedule).order_by(Schedule.id.desc()).limit(1))


def _reconstruct_monthly_norms(schedule: Schedule) -> dict[str, float]:
    months: list[str] = []
    year, month = schedule.start_date.year, schedule.start_date.month
    end_year, end_month = schedule.end_date.year, schedule.end_date.month
    while (year, month) <= (end_year, end_month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1

    total = float(schedule.period_norm or 0)
    if not months:
        return {}
    per_month = total / len(months)
    return {key: per_month for key in months}


def _load_eval_context(
    schedule: Schedule, db: Session
) -> tuple[ScheduleContext, list[Employee], list[ShiftType]]:
    employees = list(
        db.scalars(
            select(Employee)
            .where(
                Employee.id.in_(
                    select(ShiftAssignment.employee_id)
                    .where(ShiftAssignment.schedule_id == schedule.id)
                    .distinct()
                )
            )
            .order_by(Employee.id)
        )
    )
    shift_types = list(db.scalars(select(ShiftType).order_by(ShiftType.id)))
    employee_ids = [emp.id for emp in employees]

    assignments = list(
        db.scalars(
            select(ShiftAssignment).where(
                ShiftAssignment.schedule_id == schedule.id
            )
        )
    )

    staffing = {
        req.shift_type_id: req.min_staff for req in schedule.staffing_requirements
    }

    preferences = load_preferences(db, employee_ids)

    snap = schedule.generation_inputs
    if snap is not None:
        # frozen snapshot
        off_weekdays = frozenset(int(x) for x in snap["off_weekdays"])
        explicit_non_working = frozenset(
            datetime.date.fromisoformat(d) for d in snap["non_working_dates"]
        )
        snap_hours: dict[int, float] = {
            int(k): float(v) for k, v in snap["employee_hours"].items()
        }

        if "approved_leave" in snap:
            approved_leave = frozenset(
                (int(emp_id), datetime.date.fromisoformat(d))
                for emp_id, d in snap["approved_leave"]
            )
        else:
            approved_leave = load_approved_leave(
                db, employee_ids, schedule.start_date, schedule.end_date
            )
        eval_employees = tuple(
            EvalEmployee(
                id=emp.id,
                hours_per_week=snap_hours.get(emp.id, float(emp.hours_per_week)),
            )
            for emp in employees
        )
        eval_shift_types = tuple(
            EvalShiftType(
                id=st["id"],
                start_time=datetime.time.fromisoformat(st["start_time"]),
                end_time=datetime.time.fromisoformat(st["end_time"]),
            )
            for st in snap["shift_types"]
        )
    else:

        settings = db.get(CompanySettings, 1)
        off_weekdays = frozenset(settings.off_weekdays) if settings else frozenset()
        explicit_non_working = frozenset(
            db.scalars(
                select(NonWorkingDate.date).where(
                    NonWorkingDate.date >= schedule.start_date,
                    NonWorkingDate.date <= schedule.end_date,
                )
            )
        )
        approved_leave = load_approved_leave(
            db, employee_ids, schedule.start_date, schedule.end_date
        )
        eval_employees = tuple(
            EvalEmployee(id=emp.id, hours_per_week=float(emp.hours_per_week))
            for emp in employees
        )
        eval_shift_types = tuple(
            EvalShiftType(id=st.id, start_time=st.start_time, end_time=st.end_time)
            for st in shift_types
        )

    ctx = ScheduleContext(
        employees=eval_employees,
        shift_types=eval_shift_types,
        assignments=tuple(
            Assignment(
                employee_id=a.employee_id,
                date=a.date,
                shift_type_id=a.shift_type_id,
            )
            for a in assignments
        ),
        period_start=schedule.start_date,
        period_end=schedule.end_date,
        monthly_norms=_reconstruct_monthly_norms(schedule),
        staffing_requirements=staffing,
        approved_leave=approved_leave,
        off_weekdays=off_weekdays,
        non_working_dates=explicit_non_working,
        employee_preferences=preferences,
    )
    return ctx, employees, shift_types


def _build_detail(schedule: Schedule, db: Session) -> ScheduleDetail:
    ctx, employees, shift_types = _load_eval_context(schedule, db)
    result = evaluate_schedule(ctx)

    return ScheduleDetail(
        schedule_id=schedule.id,
        algorithm=schedule.algorithm,
        start_date=schedule.start_date,
        end_date=schedule.end_date,
        fitness_score=schedule.fitness_score,
        hard_violations=HardViolations(
            H1=result.h1,
            H2=result.h2,
            H3=result.h3,
            H4=result.h4,
            H5=result.h5,
            H6=result.h6,
            H7=result.h7,
            H8=result.h8,
            H9=result.h9,
        ),
        soft_violations=SoftViolations(
            S1=result.s1,
            S2=result.s2,
            S3=result.s3,
            S4=result.s4,
            S5=result.s5,
            S6=result.s6,
        ),
        employees=[
            ScheduleEmployee(
                id=emp.id, name=emp.name, hours_per_week=emp.hours_per_week
            )
            for emp in employees
        ],
        shift_types=[
            ScheduleShiftType(
                id=st.id,
                name=st.name,
                start_time=st.start_time,
                end_time=st.end_time,
            )
            for st in shift_types
        ],
        assignments=[
            ScheduleAssignment(
                employee_id=a.employee_id,
                date=a.date,
                shift_type_id=a.shift_type_id,
            )
            for a in ctx.assignments
        ],
    )


def _employee_entries(
    schedule: Schedule, employee_id: int, db: Session
) -> list[EmployeeScheduleEntry]:
    rows = db.scalars(
        select(ShiftAssignment)
        .where(
            ShiftAssignment.schedule_id == schedule.id,
            ShiftAssignment.employee_id == employee_id,
        )
        .order_by(ShiftAssignment.date)
    )
    shift_index = {
        st.id: st for st in db.scalars(select(ShiftType))
    }

    entries: list[EmployeeScheduleEntry] = []
    for row in rows:
        shift = shift_index.get(row.shift_type_id) if row.shift_type_id else None
        entries.append(
            EmployeeScheduleEntry(
                date=row.date,
                shift_type_id=row.shift_type_id,
                shift_type_name=shift.name if shift else None,
                start_time=shift.start_time if shift else None,
                end_time=shift.end_time if shift else None,
            )
        )
    return entries


def _current_employee_id(current_user: User) -> int:
    if current_user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not linked to an employee",
        )
    return current_user.employee_id


@router.get("/schedules/latest/me", response_model=list[EmployeeScheduleEntry])
def get_my_latest_schedule(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_employee),
) -> list[EmployeeScheduleEntry]:
    schedule = _latest_schedule(db)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No schedule exists"
        )
    return _employee_entries(schedule, _current_employee_id(current_user), db)


@router.get("/schedules/latest", response_model=ScheduleDetail)
def get_latest_schedule(
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> ScheduleDetail:
    schedule = _latest_schedule(db)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No schedule exists"
        )
    return _build_detail(schedule, db)


@router.get("/schedules", response_model=list[ScheduleListItem])
def list_schedules(
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> list[ScheduleListItem]:
    schedules = db.scalars(select(Schedule).order_by(Schedule.id.desc()))
    return [
        ScheduleListItem(
            id=schedule.id,
            task_id=str(schedule.task_id) if schedule.task_id else None,
            start_date=schedule.start_date,
            end_date=schedule.end_date,
            algorithm=schedule.algorithm,
            fitness_score=schedule.fitness_score,
            created_at=schedule.created_at,
        )
        for schedule in schedules
    ]


@router.get(
    "/schedules/{schedule_id}/me", response_model=list[EmployeeScheduleEntry]
)
def get_my_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_employee),
) -> list[EmployeeScheduleEntry]:
    schedule = _get_schedule_or_404(schedule_id, db)
    return _employee_entries(schedule, _current_employee_id(current_user), db)


@router.get("/schedules/{schedule_id}/export")
def export_schedule_excel(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> StreamingResponse:
    schedule = _get_schedule_or_404(schedule_id, db)
    xlsx_bytes = render_schedule_xlsx(schedule, db)
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="schedule_{schedule.id}.xlsx"'
            )
        },
    )


@router.get("/schedules/{schedule_id}", response_model=ScheduleDetail)
def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> ScheduleDetail:
    schedule = _get_schedule_or_404(schedule_id, db)
    return _build_detail(schedule, db)


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> None:
    schedule = _get_schedule_or_404(schedule_id, db)
    task_id = schedule.task_id
    db.delete(schedule)
    if task_id is not None:
        task = db.get(Task, task_id)
        if task:
            db.delete(task)
    db.commit()
