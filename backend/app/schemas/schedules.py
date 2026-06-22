from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateRequest(BaseModel):
    algorithm: str = Field(default="GA", pattern=r"^(GA|CP_SAT)$")
    start_month: str = Field(
        description="Inclusive first month, formatted YYYY-MM",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    )
    end_month: str = Field(
        description="Inclusive last month, formatted YYYY-MM",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    )
    monthly_norms: dict[str, int] = Field(
        min_length=1,
        description="Per-month standard hours, keyed by YYYY-MM",
    )
    staffing: dict[str, int] = Field(
        min_length=1,
        description="Required headcount per shift, keyed by shift_type_id",
    )


class GenerateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    status: str
    error: str | None
    created_at: datetime.datetime
    completed_at: datetime.datetime | None
