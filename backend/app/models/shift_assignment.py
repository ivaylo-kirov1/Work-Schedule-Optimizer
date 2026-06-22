import datetime

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"
    __table_args__ = (
        UniqueConstraint(
            "schedule_id", "employee_id", "date", name="uq_assignment_sched_emp_date"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE")
    )
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    shift_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("shift_types.id"), nullable=True
    )
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    schedule: Mapped["Schedule"] = relationship(back_populates="assignments")
    employee: Mapped["Employee"] = relationship(back_populates="assignments")
    shift_type: Mapped["ShiftType | None"] = relationship()


from app.models.employee import Employee
from app.models.schedule import Schedule
from app.models.shift_type import ShiftType  
