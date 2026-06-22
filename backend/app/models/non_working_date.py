import datetime

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NonWorkingDate(Base):
    __tablename__ = "non_working_dates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, unique=True)
    note: Mapped[str | None] = mapped_column(String(100), nullable=True)
