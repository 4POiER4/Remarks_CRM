import math
import os
import uuid
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session, joinedload

from app.auth import can_manage_all
from app.core.config import get_settings
from app.filters import apply_remark_filters, apply_remark_visibility
from app.models.models import (
  Department,
  Letter,
  LetterAttachment,
  ProjectObject,
  Remark,
  RemarkFeedback,
  RemarkResult,
  User,
  UserRole,
)
from app.schemas.schemas import (
  DepartmentRead,
  LetterAttachmentRead,
  LetterBrief,
  LetterRead,
  ObjectBrief,
  ObjectRead,
  RemarkResultRead,
  RemarkFeedbackRead,
  RemarkRead,
  UserRead,
)


def department_to_read(department: Department, remarks_count: int = 0) -> DepartmentRead:
  return DepartmentRead(
    id=department.id,
    name=department.name,
    code=department.code,
    kind=department.kind,
    remarks_count=remarks_count,
  )


def user_to_read(user: User) -> UserRead:
  department = None
  if user.department:
    department = DepartmentRead(
      id=user.department.id,
      name=user.department.name,
      code=user.department.code,
      kind=user.department.kind,
      remarks_count=0,
    )
  return UserRead(
    id=user.id,
    username=user.username,
    display_name=user.display_name,
    email=user.email,
    role=user.role,
    department_id=user.department_id,
    is_active=user.is_active,
    last_login_at=user.last_login_at,
    department=department,
  )


def attachment_to_read(attachment: LetterAttachment) -> LetterAttachmentRead:
  return LetterAttachmentRead.model_validate(attachment)


def remark_result_to_read(result: RemarkResult) -> RemarkResultRead:
  return RemarkResultRead.model_validate(result, from_attributes=True)


def remark_feedback_to_read(feedback: RemarkFeedback) -> RemarkFeedbackRead:
  return RemarkFeedbackRead.model_validate(feedback, from_attributes=True)


def letter_brief(letter: Letter | None) -> LetterBrief | None:
  if not letter:
    return None
  return LetterBrief.model_validate(letter)


def remark_to_read(remark: Remark) -> RemarkRead:
  letter = remark.letter
  return RemarkRead(
    id=remark.id,
    letter_id=remark.letter_id,
    document_remark=remark.document_remark,
    document_type=remark.document_type,
    remark_text=remark.remark_text,
    department_id=remark.department_id,
    assignee_id=remark.assignee_id,
    status=remark.status,
    assigned_by=remark.assigned_by,
    assigned_at=remark.assigned_at,
    assignee_assigned_by=remark.assignee_assigned_by,
    assignee_assigned_at=remark.assignee_assigned_at,
    department_due_date=remark.department_due_date,
    due_date=remark.due_date,
    resolution_notes=remark.resolution_notes,
    results=[remark_result_to_read(result) for result in remark.results],
    feedback=[remark_feedback_to_read(item) for item in remark.feedback],
    created_at=remark.created_at,
    updated_at=remark.updated_at,
    department=remark.department,
    assignee=remark.assignee,
    letter=letter_brief(letter),
    object_name=letter.object.name if letter and letter.object else None,
    subobject_name=letter.object.subobject_name if letter and letter.object else None,
    from_whom=letter.from_whom if letter else None,
    letter_number=letter.letter_number if letter else None,
    letter_date=letter.letter_date if letter else None,
    lep_accompaniment=letter.lep_accompaniment if letter else None,
    lep_accompaniment_date=letter.lep_accompaniment_date if letter else None,
  )


def letter_to_read(
  letter: Letter,
  remarks_count: int = 0,
  include_attachments: bool = False,
) -> LetterRead:
  attachments = letter.attachments if include_attachments else []
  return LetterRead(
    id=letter.id,
    object_id=letter.object_id,
    from_whom=letter.from_whom,
    letter_number=letter.letter_number,
    letter_date=letter.letter_date,
    lep_accompaniment=letter.lep_accompaniment,
    lep_accompaniment_date=letter.lep_accompaniment_date,
    remarks_count=remarks_count,
    attachments_count=len(letter.attachments) if letter.attachments else 0,
    attachments=[attachment_to_read(item) for item in attachments] if include_attachments else [],
    created_at=letter.created_at,
    updated_at=letter.updated_at,
    object=ObjectBrief.model_validate(letter.object) if letter.object else None,
  )


def object_to_read(
  obj: ProjectObject,
  letters_count: int = 0,
  remarks_count: int = 0,
) -> ObjectRead:
  return ObjectRead(
    id=obj.id,
    name=obj.name,
    subobject_name=obj.subobject_name,
    letters_count=letters_count,
    remarks_count=remarks_count,
    created_at=obj.created_at,
    updated_at=obj.updated_at,
  )


def get_remark_query(db: Session) -> Query:
  return db.query(Remark).options(
    joinedload(Remark.department),
    joinedload(Remark.assignee),
    joinedload(Remark.results),
    joinedload(Remark.feedback),
    joinedload(Remark.letter).joinedload(Letter.object),
  )


def get_letter_query(db: Session) -> Query:
  return db.query(Letter).options(
    joinedload(Letter.object),
    joinedload(Letter.attachments),
  )


def fetch_remark(db: Session, remark_id: int) -> Remark:
  remark = get_remark_query(db).filter(Remark.id == remark_id).first()
  if not remark:
    raise HTTPException(status_code=404, detail="Замечание не найдено")
  return remark


def fetch_letter(db: Session, letter_id: int) -> Letter:
  letter = get_letter_query(db).filter(Letter.id == letter_id).first()
  if not letter:
    raise HTTPException(status_code=404, detail="Письмо не найдено")
  return letter


def fetch_object(db: Session, object_id: int) -> ProjectObject:
  obj = db.query(ProjectObject).filter(ProjectObject.id == object_id).first()
  if not obj:
    raise HTTPException(status_code=404, detail="Объект не найден")
  return obj


def ensure_remark_visible(user: User, remark: Remark) -> None:
  if can_manage_all(user):
    return
  if user.role == UserRole.DEPARTMENT_HEAD.value and user.department_id == remark.department_id:
    return
  if user.role == UserRole.EMPLOYEE.value and remark.assignee_id == user.id:
    return
  raise HTTPException(status_code=403, detail="Нет доступа к этому замечанию")


def build_visible_remarks_query(db: Session, user: User, **filters) -> Query:
  query = get_remark_query(db)
  query = apply_remark_visibility(query, user)
  return apply_remark_filters(query, **filters)


def paginate_query(query: Query, page: int, page_size: int) -> tuple[list[Remark], int, int]:
  total = query.order_by(None).count()
  pages = max(1, math.ceil(total / page_size)) if total else 1
  page = min(max(page, 1), pages)
  items = (
    query.order_by(Remark.created_at.desc())
    .offset((page - 1) * page_size)
    .limit(page_size)
    .all()
  )
  return items, total, pages


def department_remarks_counts(db: Session) -> dict[int, int]:
  rows = (
    db.query(Remark.department_id, func.count(Remark.id))
    .filter(Remark.department_id.isnot(None))
    .group_by(Remark.department_id)
    .all()
  )
  return {department_id: count for department_id, count in rows}


def object_counts(db: Session) -> dict[int, tuple[int, int]]:
  letter_rows = (
    db.query(Letter.object_id, func.count(Letter.id))
    .group_by(Letter.object_id)
    .all()
  )
  remark_rows = (
    db.query(Letter.object_id, func.count(Remark.id))
    .join(Remark, Remark.letter_id == Letter.id)
    .group_by(Letter.object_id)
    .all()
  )
  letters_map = {object_id: count for object_id, count in letter_rows}
  remarks_map = {object_id: count for object_id, count in remark_rows}
  object_ids = set(letters_map) | set(remarks_map)
  return {object_id: (letters_map.get(object_id, 0), remarks_map.get(object_id, 0)) for object_id in object_ids}


def letter_remarks_counts(db: Session, object_id: int | None = None) -> dict[int, int]:
  query = db.query(Remark.letter_id, func.count(Remark.id)).filter(Remark.letter_id.isnot(None))
  if object_id:
    query = query.join(Letter).filter(Letter.object_id == object_id)
  rows = query.group_by(Remark.letter_id).all()
  return {letter_id: count for letter_id, count in rows}


def ensure_upload_dir() -> Path:
  settings = get_settings()
  path = Path(settings.upload_dir)
  path.mkdir(parents=True, exist_ok=True)
  return path


async def save_letter_attachment(
  db: Session,
  letter: Letter,
  file: UploadFile,
  uploaded_by: str,
) -> LetterAttachment:
  settings = get_settings()
  if not file.filename:
    raise HTTPException(status_code=400, detail="Имя файла не указано")

  extension = Path(file.filename).suffix.lower()
  if extension not in settings.allowed_upload_extensions:
    allowed = ", ".join(sorted(settings.allowed_upload_extensions))
    raise HTTPException(status_code=400, detail=f"Можно прикреплять только файлы: {allowed}")

  content = await file.read()
  if len(content) > settings.max_upload_size_bytes:
    raise HTTPException(
      status_code=400,
      detail=f"Файл слишком большой (макс. {settings.max_upload_size_mb} МБ)",
    )

  content_hash = sha256(content).hexdigest()
  duplicate = (
    db.query(LetterAttachment)
    .filter(
      LetterAttachment.letter_id == letter.id,
      or_(
        LetterAttachment.content_hash == content_hash,
        (
          (LetterAttachment.filename == file.filename)
          & (LetterAttachment.file_size == len(content))
        ),
      ),
    )
    .first()
  )
  if duplicate:
    raise HTTPException(status_code=400, detail="Вы прикрепляете файл, который уже прикреплен!")

  upload_root = ensure_upload_dir()
  letter_dir = upload_root / str(letter.id)
  letter_dir.mkdir(parents=True, exist_ok=True)

  stored_name = f"{uuid.uuid4().hex}_{file.filename}"
  stored_path = letter_dir / stored_name
  stored_path.write_bytes(content)

  attachment = LetterAttachment(
    letter_id=letter.id,
    filename=file.filename,
    stored_name=stored_name,
    content_hash=content_hash,
    content_type=file.content_type,
    file_size=len(content),
    uploaded_by=uploaded_by,
  )
  db.add(attachment)
  db.commit()
  db.refresh(attachment)
  return attachment


def get_attachment_path(attachment: LetterAttachment) -> Path:
  settings = get_settings()
  return Path(settings.upload_dir) / str(attachment.letter_id) / attachment.stored_name


def delete_attachment_file(attachment: LetterAttachment) -> None:
  path = get_attachment_path(attachment)
  if path.exists():
    path.unlink()


def get_result_attachment_path(remark: Remark) -> Path | None:
  if not remark.result_stored_name:
    return None
  settings = get_settings()
  return Path(settings.upload_dir) / "results" / str(remark.id) / remark.result_stored_name


def delete_result_attachment_file(remark: Remark) -> None:
  path = get_result_attachment_path(remark)
  if path and path.exists():
    path.unlink()


def clear_result_attachment(remark: Remark) -> None:
  delete_result_attachment_file(remark)
  remark.result_filename = None
  remark.result_stored_name = None
  remark.result_content_hash = None
  remark.result_content_type = None
  remark.result_file_size = None
  remark.result_uploaded_by = None
  remark.result_uploaded_at = None


async def save_result_attachment(
  remark: Remark,
  file: UploadFile,
  uploaded_by: str,
) -> None:
  settings = get_settings()
  if not file.filename:
    raise HTTPException(status_code=400, detail="Имя файла не указано")

  filename = Path(file.filename).name
  extension = Path(filename).suffix.lower()
  if extension not in settings.allowed_upload_extensions:
    allowed = ", ".join(sorted(settings.allowed_upload_extensions))
    raise HTTPException(status_code=400, detail=f"Можно прикреплять только файлы: {allowed}")

  content = await file.read()
  if len(content) > settings.max_upload_size_bytes:
    raise HTTPException(
      status_code=400,
      detail=f"Файл слишком большой (макс. {settings.max_upload_size_mb} МБ)",
    )

  content_hash = sha256(content).hexdigest()
  current_path = get_result_attachment_path(remark)
  if remark.result_content_hash == content_hash and current_path and current_path.exists():
    remark.result_filename = filename
    remark.result_content_type = file.content_type
    remark.result_file_size = len(content)
    remark.result_uploaded_by = uploaded_by
    remark.result_uploaded_at = datetime.utcnow()
    return

  old_path = get_result_attachment_path(remark)
  result_dir = ensure_upload_dir() / "results" / str(remark.id)
  result_dir.mkdir(parents=True, exist_ok=True)
  stored_name = f"{uuid.uuid4().hex}_{filename}"
  stored_path = result_dir / stored_name
  stored_path.write_bytes(content)

  if old_path and old_path.exists() and old_path != stored_path:
    old_path.unlink()

  remark.result_filename = filename
  remark.result_stored_name = stored_name
  remark.result_content_hash = content_hash
  remark.result_content_type = file.content_type
  remark.result_file_size = len(content)
  remark.result_uploaded_by = uploaded_by
  remark.result_uploaded_at = datetime.utcnow()


def get_remark_result_file_path(result: RemarkResult) -> Path | None:
  if not result.stored_name:
    return None
  settings = get_settings()
  return Path(settings.upload_dir) / "results" / str(result.remark_id) / result.stored_name


def delete_remark_result_file(result: RemarkResult) -> None:
  path = get_remark_result_file_path(result)
  if path and path.exists():
    path.unlink()


async def save_remark_result_file(result: RemarkResult, file: UploadFile) -> None:
  settings = get_settings()
  if not file.filename:
    raise HTTPException(status_code=400, detail="Имя файла не указано")

  filename = Path(file.filename).name
  extension = Path(filename).suffix.lower()
  if extension not in settings.allowed_upload_extensions:
    allowed = ", ".join(sorted(settings.allowed_upload_extensions))
    raise HTTPException(status_code=400, detail=f"Можно прикреплять только файлы: {allowed}")

  content = await file.read()
  if len(content) > settings.max_upload_size_bytes:
    raise HTTPException(
      status_code=400,
      detail=f"Файл слишком большой (макс. {settings.max_upload_size_mb} МБ)",
    )

  old_path = get_remark_result_file_path(result)
  result_dir = ensure_upload_dir() / "results" / str(result.remark_id)
  result_dir.mkdir(parents=True, exist_ok=True)
  stored_name = f"{uuid.uuid4().hex}_{filename}"
  stored_path = result_dir / stored_name
  stored_path.write_bytes(content)

  if old_path and old_path.exists() and old_path != stored_path:
    old_path.unlink()

  result.filename = filename
  result.stored_name = stored_name
  result.content_hash = sha256(content).hexdigest()
  result.content_type = file.content_type
  result.file_size = len(content)
