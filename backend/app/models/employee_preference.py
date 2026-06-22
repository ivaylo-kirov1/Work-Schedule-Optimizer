from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EmployeePreference(Base):
    __tablename__ = "employee_preferences"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "day_of_week", name="uq_employee_preferences_emp_day"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE")
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)

    employee: Mapped["Employee"] = relationship(back_populates="preferences")


from app.models.employee import Employee 
