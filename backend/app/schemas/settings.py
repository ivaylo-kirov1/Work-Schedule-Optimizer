from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_WEEKDAY = 0
MAX_WEEKDAY = 6


class SettingsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    off_weekdays: list[int]
    regime: str


class SettingsUpdateRequest(BaseModel):
    off_weekdays: list[int] = Field(
        description="Recurring non-working weekdays, as ints 0 (Mon) - 6 (Sun)"
    )

    @field_validator("off_weekdays")
    @classmethod
    def validate_off_weekdays(cls, value: list[int]) -> list[int]:
        for day in value:
            if not (MIN_WEEKDAY <= day <= MAX_WEEKDAY):
                raise ValueError(
                    f"off_weekdays values must be between {MIN_WEEKDAY} and {MAX_WEEKDAY}"
                )
        if len(set(value)) != len(value):
            raise ValueError("off_weekdays must not contain duplicates")
        return sorted(value)
