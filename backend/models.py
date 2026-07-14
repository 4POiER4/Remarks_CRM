from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RemarkStatus(str, Enum):
  IN_PROGRESS = "in_progress"
  PENDING_REVIEW = "pending_review"
  RESOLVED = "resolved"


class DepartmentKind(str, Enum):
  DEPARTMENT = "department"
  SUBCONTRACTOR = "subcontractor"


class UserRole(str, Enum):
  ADMIN = "admin"
  GIP = "gip"
  DEPARTMENT_HEAD = "department_head"
  EMPLOYEE = "employee"


class Department(Base):
  __tablename__ = "departments"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)
  name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
  code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
  kind: Mapped[str] = mapped_column(String(20), default=DepartmentKind.DEPARTMENT.value)

  remarks: Mapped[list["Remark"]] = relationship(back_populates="department")
  users: Mapped[list["User"]] = relationship(back_populates="department")


class User(Base):
  __tablename__ = "users"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)
  username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
  display_name: Mapped[str] = mapped_column(String(255), nullable=False)
  email: Mapped[str | None] = mapped_column(String(255))
  password_hash: Mapped[str | None] = mapped_column(String(255))
  role: Mapped[str] = mapped_column(String(30), default=UserRole.EMPLOYEE.value)
  department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
  is_active: Mapped[bool] = mapped_column(Boolean, default=True)
  last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  department: Mapped[Department | None] = relationship(back_populates="users")
  assigned_remarks: Mapped[list["Remark"]] = relationship(
    back_populates="assignee",
    foreign_keys="Remark.assignee_id",
  )


class Remark(Base):
  __tablename__ = "remarks"

  id: Mapped[int] = mapped_column(primary_key=True, index=True)
  from_whom: Mapped[str | None] = mapped_column(String(255))
  letter_number: Mapped[str | None] = mapped_column(String(100))
  letter_date: Mapped[date | None] = mapped_column(Date)
  lep_accompaniment: Mapped[str | None] = mapped_column(String(255))
  lep_accompaniment_date: Mapped[date | None] = mapped_column(Date)
  object_name: Mapped[str | None] = mapped_column(String(255))
  document_remark: Mapped[str | None] = mapped_column(Text)
  document_type: Mapped[str | None] = mapped_column(String(255))
  remark_text: Mapped[str | None] = mapped_column(Text)

  department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
  assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
  status: Mapped[str] = mapped_column(String(30), default=RemarkStatus.IN_PROGRESS.value)
  assigned_by: Mapped[str | None] = mapped_column(String(255))
  assigned_at: Mapped[datetime | None] = mapped_column(DateTime)
  assignee_assigned_by: Mapped[str | None] = mapped_column(String(255))
  assignee_assigned_at: Mapped[datetime | None] = mapped_column(DateTime)
  resolution_notes: Mapped[str | None] = mapped_column(Text)

  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(
    DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
  )

  department: Mapped[Department | None] = relationship(back_populates="remarks")
  assignee: Mapped[User | None] = relationship(
    back_populates="assigned_remarks",
    foreign_keys=[assignee_id],
  )
