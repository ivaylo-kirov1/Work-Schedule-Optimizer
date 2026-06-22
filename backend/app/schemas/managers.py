from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field


class ManagerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime.datetime


class ManagerCreateRequest(BaseModel):
    email: str = Field(
        min_length=5,
        max_length=150,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )


class ManagerCredentialResponse(BaseModel):

    model_config = ConfigDict(frozen=True)

    user_id: int
    email: str
    temp_password: str
