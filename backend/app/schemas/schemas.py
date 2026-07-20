from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.models import DepartmentKind, UserRole

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
  items: list[T]
  total: int
  page: int
  page_size: int
  pages: int


class DepartmentBase(BaseModel):
  name: str
  code: str
  kind: str = DepartmentKind.DEPARTMENT.value

  @field_validator("kind")
  @classmethod
  def validate_kind(cls, value: str) -> str:
    allowed = {item.value for item in DepartmentKind}
    if value not in allowed:
      raise ValueError("Тип должен быть department или subcontractor")
    return value


class DepartmentCreate(DepartmentBase):
  pass


class DepartmentUpdate(BaseModel):
  name: str | None = None
  code: str | None = None
  kind: str | None = None

  @field_validator("kind")
  @classmethod
  def validate_kind(cls, value: str | None) -> str | None:
    if value is None:
      return value
    allowed = {item.value for item in DepartmentKind}
    if value not in allowed:
      raise ValueError("Тип должен быть department или subcontractor")
    return value


class DepartmentRead(DepartmentBase):
  model_config = ConfigDict(from_attributes=True)

  id: int
  remarks_count: int = 0


class UserBrief(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: int
  username: str
  display_name: str
  role: str
  department_id: int | None = None


class UserRead(UserBrief):
  email: str | None = None
  is_active: bool
  last_login_at: datetime | None = None
  department: DepartmentRead | None = None


class UserUpdate(BaseModel):
  role: str | None = None
  department_id: int | None = None
  is_active: bool | None = None
  display_name: str | None = None

  @field_validator("role")
  @classmethod
  def validate_role(cls, value: str | None) -> str | None:
    if value is None:
      return value
    allowed = {item.value for item in UserRole}
    if value not in allowed:
      raise ValueError("Недопустимая роль")
    return value


class LoginRequest(BaseModel):
  username: str
  password: str


class TokenResponse(BaseModel):
  access_token: str
  token_type: str = "bearer"
  user: UserRead


class ObjectCreate(BaseModel):
  name: str
  subobject_name: str | None = None


class ObjectUpdate(BaseModel):
  name: str
  subobject_name: str | None = None


class ObjectRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: int
  name: str
  subobject_name: str | None = None
  letters_count: int = 0
  remarks_count: int = 0
  created_at: datetime
  updated_at: datetime


class LetterCreate(BaseModel):
  from_whom: str | None = None
  letter_number: str | None = None
  letter_date: date | None = None
  lep_accompaniment: str | None = None
  lep_accompaniment_date: date | None = None


class LetterUpdate(LetterCreate):
  pass


class LetterAttachmentRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: int
  letter_id: int
  filename: str
  content_type: str | None = None
  file_size: int
  content_hash: str | None = None
  uploaded_by: str | None = None
  created_at: datetime


class ObjectBrief(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: int
  name: str
  subobject_name: str | None = None


class LetterBrief(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: int
  object_id: int
  from_whom: str | None = None
  letter_number: str | None = None
  letter_date: date | None = None
  lep_accompaniment: str | None = None
  lep_accompaniment_date: date | None = None


class LetterRead(LetterBrief):
  remarks_count: int = 0
  attachments_count: int = 0
  attachments: list[LetterAttachmentRead] = Field(default_factory=list)
  created_at: datetime
  updated_at: datetime
  object: ObjectBrief | None = None


class RemarkCreate(BaseModel):
  document_remark: str | None = None
  document_type: str | None = None
  remark_text: str | None = None


class RemarkUpdate(RemarkCreate):
  pass


class RemarkAssignDepartment(BaseModel):
  department_id: int
  department_due_date: date


class RemarkAssignExecutor(BaseModel):
  assignee_id: int
  due_date: date


class RemarkStatusUpdate(BaseModel):
  status: str
  resolution_notes: str | None = None


class DepartmentBrief(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: int
  name: str
  code: str
  kind: str


class RemarkResultRead(BaseModel):
  id: int
  remark_id: int
  notes: str | None = None
  filename: str | None = None
  content_type: str | None = None
  file_size: int | None = None
  created_by_id: int | None = None
  created_by_name: str
  created_at: datetime
  updated_at: datetime


class RemarkFeedbackRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: int
  remark_id: int
  comment: str
  created_by_id: int
  created_by_name: str
  created_at: datetime


class RemarkRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: int
  letter_id: int | None = None
  document_remark: str | None = None
  document_type: str | None = None
  remark_text: str | None = None
  department_id: int | None = None
  assignee_id: int | None = None
  status: str
  assigned_by: str | None = None
  assigned_at: datetime | None = None
  assignee_assigned_by: str | None = None
  assignee_assigned_at: datetime | None = None
  department_due_date: date | None = None
  due_date: date | None = None
  resolution_notes: str | None = None
  results: list[RemarkResultRead] = Field(default_factory=list)
  feedback: list[RemarkFeedbackRead] = Field(default_factory=list)
  created_at: datetime
  updated_at: datetime
  department: DepartmentBrief | None = None
  assignee: UserBrief | None = None
  letter: LetterBrief | None = None
  object_name: str | None = None
  subobject_name: str | None = None
  from_whom: str | None = None
  letter_number: str | None = None
  letter_date: date | None = None
  lep_accompaniment: str | None = None
  lep_accompaniment_date: date | None = None


class ImportResult(BaseModel):
  imported: int
  skipped: int
  errors: list[str]


class ImportJobRead(BaseModel):
  id: str
  status: str
  filename: str | None = None
  imported: int = 0
  skipped: int = 0
  errors: list[str] = Field(default_factory=list)
  created_at: datetime | None = None
  finished_at: datetime | None = None


class HealthResponse(BaseModel):
  status: str
  database: str
  cache: str
  version: str


class NotificationRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: int
  user_id: int
  remark_id: int | None = None
  type: str
  message: str
  is_read: bool
  created_at: datetime
  read_at: datetime | None = None
