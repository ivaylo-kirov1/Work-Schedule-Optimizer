import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import CompanySettings, ShiftType

COMPANY_SETTINGS_ID = 1

DEFAULT_SHIFT_TYPES = (
    ("Day", datetime.time(8, 0), datetime.time(16, 0)),
    ("Evening", datetime.time(16, 0), datetime.time(0, 0)),
    ("Night", datetime.time(0, 0), datetime.time(8, 0)),
)


def seed_company_settings(session: Session) -> None:
    existing = session.get(CompanySettings, COMPANY_SETTINGS_ID)
    if existing is None:
        session.add(CompanySettings(id=COMPANY_SETTINGS_ID, off_weekdays=[]))


def seed_shift_types(session: Session) -> None:
    for name, start_time, end_time in DEFAULT_SHIFT_TYPES:
        exists = session.scalar(select(ShiftType.id).where(ShiftType.name == name))
        if exists is None:
            session.add(ShiftType(name=name, start_time=start_time, end_time=end_time))


def main() -> None:
    with SessionLocal() as session:
        seed_company_settings(session)
        seed_shift_types(session)
        session.commit()
    print("Seed complete")


if __name__ == "__main__":
    main()
