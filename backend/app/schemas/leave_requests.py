from __future__ import annotations

import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LeaveRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    start_date: datetime.date
    end_date: datetime.date
    note: str | None
    status: str


class LeaveRequestCreate(BaseModel):
    start_date: datetime.date
    end_date: datetime.date
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_date_order(self) -> Self:
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self
