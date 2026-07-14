from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models import DepartmentKind, UserRole


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


class RemarkBase(BaseModel):
  from_whom: str | None = None
  letter_number: str | None = None
  letter_date: date | None = None
  lep_accompaniment: str | None = None
  lep_accompaniment_date: date | None = None
  object_name: str | None = None
  document_remark: str | None = None
  document_type: str | None = None
  remark_text: str | None = None


class RemarkCreate(RemarkBase):
  pass


class RemarkUpdate(RemarkBase):
  pass


class RemarkAssignDepartment(BaseModel):
  department_id: int
  status: str = "in_progress"


class RemarkAssignExecutor(BaseModel):
  assignee_id: int


class RemarkStatusUpdate(BaseModel):
  status: str
  resolution_notes: str | None = None


class DepartmentBrief(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: int
  name: str
  code: str
  kind: str


class RemarkRead(RemarkBase):
  model_config = ConfigDict(from_attributes=True)

  id: int
  department_id: int | None = None
  assignee_id: int | None = None
  status: str
  assigned_by: str | None = None
  assigned_at: datetime | None = None
  assignee_assigned_by: str | None = None
  assignee_assigned_at: datetime | None = None
  resolution_notes: str | None = None
  created_at: datetime
  updated_at: datetime
  department: DepartmentBrief | None = None
  assignee: UserBrief | None = None


class ImportResult(BaseModel):
  imported: int
  skipped: int
  errors: list[str]
