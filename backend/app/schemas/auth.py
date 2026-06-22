from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class TokenResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str
    token_type: str = "bearer"
    role: str


class MeResponse(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    email: str
    role: str
    employee_id: int | None


class PasswordChangeRequest(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=72)
    new_password: SecretStr = Field(min_length=8, max_length=72)
