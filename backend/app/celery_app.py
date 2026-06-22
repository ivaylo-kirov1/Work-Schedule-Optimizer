from __future__ import annotations

import os

from celery import Celery

_DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def _broker_url() -> str:
    return os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL") or _DEFAULT_REDIS_URL


def _result_backend() -> str:
    return (
        os.getenv("CELERY_RESULT_BACKEND")
        or os.getenv("REDIS_URL")
        or _DEFAULT_REDIS_URL
    )


celery_app = Celery(
    "backend",
    broker=_broker_url(),
    backend=_result_backend(),
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)
