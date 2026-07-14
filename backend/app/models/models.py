from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


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

  id: Mapped[int] = mapped_column(primary_key=True)
  name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
  code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
  kind: Mapped[str] = mapped_column(String(20), default=DepartmentKind.DEPARTMENT.value, index=True)

  remarks: Mapped[list["Remark"]] = relationship(back_populates="department")
  users: Mapped[list["User"]] = relationship(back_populates="department")


class User(Base):
  __tablename__ = "users"

  id: Mapped[int] = mapped_column(primary_key=True)
  username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
  display_name: Mapped[str] = mapped_column(String(255), nullable=False)
  email: Mapped[str | None] = mapped_column(String(255))
  password_hash: Mapped[str | None] = mapped_column(String(255))
  role: Mapped[str] = mapped_column(String(30), default=UserRole.EMPLOYEE.value, index=True)
  department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
  last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  department: Mapped[Department | None] = relationship(back_populates="users")
  assigned_remarks: Mapped[list["Remark"]] = relationship(
    back_populates="assignee",
    foreign_keys="Remark.assignee_id",
  )


class ProjectObject(Base):
  __tablename__ = "objects"
  __table_args__ = (
    UniqueConstraint("name", "subobject_name", name="uq_objects_name_subobject"),
  )

  id: Mapped[int] = mapped_column(primary_key=True)
  name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
  subobject_name: Mapped[str | None] = mapped_column(String(255), index=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(
    DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
  )

  letters: Mapped[list["Letter"]] = relationship(back_populates="object", cascade="all, delete-orphan")


class Letter(Base):
  __tablename__ = "letters"
  __table_args__ = (
    Index("ix_letters_object_date", "object_id", "letter_date"),
  )

  id: Mapped[int] = mapped_column(primary_key=True)
  object_id: Mapped[int] = mapped_column(ForeignKey("objects.id"), nullable=False, index=True)
  from_whom: Mapped[str | None] = mapped_column(String(255))
  letter_number: Mapped[str | None] = mapped_column(String(100), index=True)
  letter_date: Mapped[date | None] = mapped_column(Date, index=True)
  lep_accompaniment: Mapped[str | None] = mapped_column(String(255))
  lep_accompaniment_date: Mapped[date | None] = mapped_column(Date)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(
    DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
  )

  object: Mapped[ProjectObject] = relationship(back_populates="letters")
  remarks: Mapped[list["Remark"]] = relationship(back_populates="letter", cascade="all, delete-orphan")
  attachments: Mapped[list["LetterAttachment"]] = relationship(
    back_populates="letter",
    cascade="all, delete-orphan",
  )


class LetterAttachment(Base):
  __tablename__ = "letter_attachments"

  id: Mapped[int] = mapped_column(primary_key=True)
  letter_id: Mapped[int] = mapped_column(ForeignKey("letters.id"), nullable=False, index=True)
  filename: Mapped[str] = mapped_column(String(255), nullable=False)
  stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
  content_type: Mapped[str | None] = mapped_column(String(100))
  file_size: Mapped[int] = mapped_column(Integer, default=0)
  uploaded_by: Mapped[str | None] = mapped_column(String(255))
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  letter: Mapped[Letter] = relationship(back_populates="attachments")


class Notification(Base):
  __tablename__ = "notifications"
  __table_args__ = (
    Index("ix_notifications_user_read_created", "user_id", "is_read", "created_at"),
  )

  id: Mapped[int] = mapped_column(primary_key=True)
  user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
  remark_id: Mapped[int | None] = mapped_column(ForeignKey("remarks.id"), index=True)
  type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
  message: Mapped[str] = mapped_column(String(500), nullable=False)
  is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
  read_at: Mapped[datetime | None] = mapped_column(DateTime)

  user: Mapped[User] = relationship()
  remark: Mapped["Remark | None"] = relationship()


class Remark(Base):
  __tablename__ = "remarks"
  __table_args__ = (
    Index("ix_remarks_status_created", "status", "created_at"),
    Index("ix_remarks_department_status", "department_id", "status"),
    Index("ix_remarks_assignee_status", "assignee_id", "status"),
    Index("ix_remarks_letter_status", "letter_id", "status"),
  )

  id: Mapped[int] = mapped_column(primary_key=True)
  letter_id: Mapped[int | None] = mapped_column(ForeignKey("letters.id"), index=True)

  document_remark: Mapped[str | None] = mapped_column(Text)
  document_type: Mapped[str | None] = mapped_column(String(255))
  remark_text: Mapped[str | None] = mapped_column(Text)

  department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
  assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
  status: Mapped[str] = mapped_column(String(30), default=RemarkStatus.IN_PROGRESS.value, index=True)
  assigned_by: Mapped[str | None] = mapped_column(String(255))
  assigned_at: Mapped[datetime | None] = mapped_column(DateTime)
  assignee_assigned_by: Mapped[str | None] = mapped_column(String(255))
  assignee_assigned_at: Mapped[datetime | None] = mapped_column(DateTime)
  due_date: Mapped[date | None] = mapped_column(Date, index=True)
  resolution_notes: Mapped[str | None] = mapped_column(Text)

  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
  updated_at: Mapped[datetime] = mapped_column(
    DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
  )

  letter: Mapped[Letter | None] = relationship(back_populates="remarks")
  department: Mapped[Department | None] = relationship(back_populates="remarks")
  assignee: Mapped[User | None] = relationship(
    back_populates="assigned_remarks",
    foreign_keys=[assignee_id],
  )
