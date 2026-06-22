import datetime
import uuid

from sqlalchemy import Date, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True
    )
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    period_norm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fitness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    algorithm: Mapped[str] = mapped_column(
        String(10), nullable=False, default="GA", server_default="GA"
    )
    generation_inputs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    task: Mapped["Task | None"] = relationship(back_populates="schedules")
    staffing_requirements: Mapped[list["StaffingRequirement"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["ShiftAssignment"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan"
    )


from app.models.shift_assignment import ShiftAssignment 
from app.models.staffing_requirement import StaffingRequirement
from app.models.task import Task
