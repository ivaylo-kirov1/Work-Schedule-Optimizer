from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field


class NonWorkingDateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: datetime.date
    note: str | None


class NonWorkingDateCreateRequest(BaseModel):
    date: datetime.date
    note: str | None = Field(default=None, max_length=100)


class NonWorkingDateUpdateRequest(BaseModel):
    date: datetime.date | None = None
    note: str | None = Field(default=None, max_length=100)
