import datetime

from sqlalchemy import Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ShiftType(Base):
    __tablename__ = "shift_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    start_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    deactivated_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
