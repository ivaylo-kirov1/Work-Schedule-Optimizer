from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict


class ScheduleListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str | None
    start_date: datetime.date
    end_date: datetime.date
    algorithm: str
    fitness_score: float | None
    created_at: datetime.datetime


class ScheduleEmployee(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    hours_per_week: int


class ScheduleShiftType(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    start_time: datetime.time
    end_time: datetime.time


class ScheduleAssignment(BaseModel):
    model_config = ConfigDict(frozen=True)

    employee_id: int
    date: datetime.date
    shift_type_id: int | None


class HardViolations(BaseModel):
    model_config = ConfigDict(frozen=True)

    H1: int
    H2: int
    H3: int
    H4: int
    H5: int
    H6: int
    H7: int
    H8: int
    H9: int


class SoftViolations(BaseModel):
    model_config = ConfigDict(frozen=True)

    S1: int
    S2: float  # total hours of undershoot below the under-utilization band
    S3: int
    S4: int
    S5: int
    S6: float  # max-min worked-hours spread across employees


class ScheduleDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    schedule_id: int
    algorithm: str
    start_date: datetime.date
    end_date: datetime.date
    fitness_score: float | None
    hard_violations: HardViolations
    soft_violations: SoftViolations
    employees: list[ScheduleEmployee]
    shift_types: list[ScheduleShiftType]
    assignments: list[ScheduleAssignment]


class EmployeeScheduleEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: datetime.date
    shift_type_id: int | None
    shift_type_name: str | None
    start_time: datetime.time | None
    end_time: datetime.time | None
