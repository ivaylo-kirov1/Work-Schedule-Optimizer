import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from sqlalchemy import select

from app import models 
from app.auth import ROLE_MANAGER, hash_password
from app.database import SessionLocal
from app.models import User
from app.routers import (
    auth,
    employees,
    leave_requests,
    managers,
    non_working_dates,
    preferences,
    schedule_views,
    schedules,
    settings,
    shift_types,
)

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

MIN_MANAGER_PASSWORD_LENGTH = 8


def _bootstrap_manager() -> None:
    email = os.getenv("INITIAL_MANAGER_EMAIL")
    password = os.getenv("INITIAL_MANAGER_PASSWORD")

    if not email or not password:
        logger.warning(
            "INITIAL_MANAGER_EMAIL/INITIAL_MANAGER_PASSWORD not set; "
            "skipping manager bootstrap"
        )
        return

    if len(password) < MIN_MANAGER_PASSWORD_LENGTH:
        logger.error(
            "INITIAL_MANAGER_PASSWORD is shorter than %d characters; "
            "bootstrap aborted. Set a stronger password.",
            MIN_MANAGER_PASSWORD_LENGTH,
        )
        return

    if len(password) > 72:
        logger.error(
            "INITIAL_MANAGER_PASSWORD exceeds 72 characters and will be "
            "truncated by bcrypt; bootstrap aborted. Shorten the password."
        )
        return

    with SessionLocal() as db:
        existing_manager = db.scalar(
            select(User.id).where(User.role == ROLE_MANAGER).limit(1)
        )
        if existing_manager is not None:
            return

        manager = User(
            email=email,
            password_hash=hash_password(password),
            role=ROLE_MANAGER,
            employee_id=None,
        )
        db.add(manager)
        db.commit()
        logger.info("Bootstrapped initial manager account: %s", email)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # tables created by alembic migrations, not on startup
    _bootstrap_manager()
    yield


app = FastAPI(title="Work Schedule Optimization API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(schedules.router, prefix="/api")
app.include_router(employees.router, prefix="/api")
app.include_router(preferences.router, prefix="/api")
app.include_router(managers.router, prefix="/api")
app.include_router(shift_types.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(non_working_dates.router, prefix="/api")
app.include_router(leave_requests.router, prefix="/api")
app.include_router(schedule_views.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
    schemes["HTTPBearer"] = {"type": "http", "scheme": "bearer"}
    schemes.pop("OAuth2PasswordBearer", None)
    # JWT insted of OAuth2PasswordBearer
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            if not isinstance(operation, dict):
                continue
            operation["security"] = [
                {"HTTPBearer": []} if "OAuth2PasswordBearer" in entry else entry
                for entry in operation.get("security", [])
            ]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi
