from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field


class ShiftTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_time: datetime.time
    end_time: datetime.time
    deactivated_at: datetime.datetime | None
    is_active: bool


class ShiftTypeWriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    start_time: datetime.time
    end_time: datetime.time
