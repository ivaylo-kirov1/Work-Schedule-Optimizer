from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str
    hours_per_week: int
    deactivated_at: datetime.datetime | None
    is_active: bool


class EmployeeCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=50)
    hours_per_week: int = Field(gt=0, le=40)
    email: str = Field(
        min_length=5,
        max_length=150,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )


class EmployeeUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=50)
    hours_per_week: int = Field(gt=0, le=40)


class CredentialResponse(BaseModel):

    model_config = ConfigDict(frozen=True)

    employee_id: int | None = None
    user_id: int
    email: str
    temp_password: str
