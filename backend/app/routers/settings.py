from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_manager
from app.database import get_db
from app.models import CompanySettings, User
from app.optimization.evaluate import derive_regime
from app.schemas.settings import SettingsResponse, SettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["settings"])

COMPANY_SETTINGS_ID = 1


def _to_response(off_weekdays: list[int]) -> SettingsResponse:
    return SettingsResponse(
        off_weekdays=sorted(off_weekdays),
        regime=derive_regime(set(off_weekdays)),
    )


@router.get("", response_model=SettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SettingsResponse:
    settings = db.get(CompanySettings, COMPANY_SETTINGS_ID)
    off_weekdays = list(settings.off_weekdays) if settings else []
    return _to_response(off_weekdays)


@router.put("", response_model=SettingsResponse)
def update_settings(
    payload: SettingsUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> SettingsResponse:
    settings = db.get(CompanySettings, COMPANY_SETTINGS_ID)
    if settings is None:
        settings = CompanySettings(
            id=COMPANY_SETTINGS_ID, off_weekdays=payload.off_weekdays
        )
        db.add(settings)
    else:
        settings.off_weekdays = payload.off_weekdays
    db.commit()
    return _to_response(payload.off_weekdays)
