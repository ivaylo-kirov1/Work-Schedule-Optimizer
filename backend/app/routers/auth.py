from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import Employee, User
from app.schemas.auth import(
    LoginRequest,
    MeResponse,
    PasswordChangeRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid email or password",
    headers={"WWW-Authenticate": "Bearer"},
)


def _is_deactivated_employee(user: User, db: Session) -> bool:
    if user.employee_id is None:
        return False
    employee = db.scalar(
        select(Employee).where(Employee.id == user.employee_id)
    )
    return employee is None or employee.deactivated_at is not None



@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(
        payload.password.get_secret_value(), user.password_hash
    ):
        raise _INVALID_CREDENTIALS

    if _is_deactivated_employee(user, db):
        raise _INVALID_CREDENTIALS

    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=access_token, role=user.role)


@router.get("/me", response_model=MeResponse)
def read_current_user(
    current_user: User = Depends(get_current_user),
) -> MeResponse:
    return MeResponse.model_validate(current_user)




@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(
        payload.current_password.get_secret_value(), current_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(
        payload.new_password.get_secret_value()
    )
    db.add(current_user)
    db.commit()
