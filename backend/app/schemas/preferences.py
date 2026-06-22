from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_WEEKDAY = 0
MAX_WEEKDAY = 6


class PreferencesResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    days: list[int]


class PreferencesUpdateRequest(BaseModel):
    days: list[int] = Field(
        description="Preferred days off, as weekday ints 0 (Mon) - 6 (Sun)"
    )

    @field_validator("days")
    @classmethod
    def validate_days(cls, value: list[int]) -> list[int]:
        for day in value:
            if not (MIN_WEEKDAY <= day <= MAX_WEEKDAY):
                raise ValueError(
                    f"day_of_week must be between {MIN_WEEKDAY} and {MAX_WEEKDAY}"
                )
        unique = sorted(set(value))
        return unique
