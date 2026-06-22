import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    hours_per_week: Mapped[int] = mapped_column(
        Integer, nullable=False, default=40, server_default="40"
    )
    deactivated_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

    user: Mapped["User | None"] = relationship(
        back_populates="employee", cascade="all, delete-orphan", uselist=False
    )
    preferences: Mapped[list["EmployeePreference"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    leave_requests: Mapped[list["LeaveRequest"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["ShiftAssignment"]] = relationship(
        back_populates="employee",
        passive_deletes=True,
    )


from app.models.employee_preference import EmployeePreference 
from app.models.leave_request import LeaveRequest  
from app.models.shift_assignment import ShiftAssignment  
from app.models.user import User  
