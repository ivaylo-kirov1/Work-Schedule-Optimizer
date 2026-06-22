from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StaffingRequirement(Base):
    __tablename__ = "staffing_requirements"
    __table_args__ = (
        UniqueConstraint(
            "schedule_id", "shift_type_id", name="uq_staffing_schedule_shift"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE")
    )
    shift_type_id: Mapped[int] = mapped_column(ForeignKey("shift_types.id"))
    min_staff: Mapped[int] = mapped_column(Integer, nullable=False)

    schedule: Mapped["Schedule"] = relationship(back_populates="staffing_requirements")
    shift_type: Mapped["ShiftType"] = relationship()


from app.models.schedule import Schedule
from app.models.shift_type import ShiftType
