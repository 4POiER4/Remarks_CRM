from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import (
  can_assign_department,
  can_assign_executor,
  get_current_user,
  require_roles,
)
from app.core.cache import cache_get, cache_set, invalidate_remarks_cache
from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import (
  Department,
  Letter,
  Notification,
  ProjectObject,
  Remark,
  RemarkFeedback,
  RemarkResult,
  RemarkStatus,
  User,
  UserRole,
)
from app.schemas.schemas import (
  PaginatedResponse,
  RemarkAssignDepartment,
  RemarkAssignExecutor,
  RemarkCreate,
  RemarkRead,
  RemarkStatusUpdate,
  RemarkUpdate,
)
from app.services.remarks import (
  build_visible_remarks_query,
  delete_remark_result_file,
  ensure_remark_visible,
  delete_result_attachment_file,
  fetch_letter,
  fetch_remark,
  get_remark_result_file_path,
  paginate_query,
  remark_to_read,
  save_remark_result_file,
)

router = APIRouter(prefix="/api/remarks", tags=["remarks"])


def notify_pending_review(db: Session, remark: Remark, user: User) -> None:
  reviewers = (
    db.query(User)
    .filter(
      User.is_active.is_(True),
      User.role == UserRole.GIP.value,
    )
    .all()
  )
  for reviewer in reviewers:
    if reviewer.id == user.id:
      continue
    db.add(
      Notification(
        user_id=reviewer.id,
        remark_id=remark.id,
        type="remark_pending_review",
        message=f"Замечание #{remark.id} отправлено на рассмотрение",
      )
    )


def notify_assigned_department(db: Session, remark: Remark, notification_type: str, message: str) -> None:
  recipient_ids: set[int] = set()
  if remark.department_id:
    department_heads = (
      db.query(User)
      .filter(
        User.department_id == remark.department_id,
        User.role == UserRole.DEPARTMENT_HEAD.value,
        User.is_active.is_(True),
      )
      .all()
    )
    recipient_ids.update(item.id for item in department_heads)
  if remark.assignee_id:
    assignee = (
      db.query(User)
      .filter(User.id == remark.assignee_id, User.is_active.is_(True))
      .first()
    )
    if assignee:
      recipient_ids.add(assignee.id)

  for recipient_id in recipient_ids:
    db.add(
      Notification(
        user_id=recipient_id,
        remark_id=remark.id,
        type=notification_type,
        message=message[:500],
      )
    )


def fetch_result(db: Session, remark_id: int, result_id: int) -> RemarkResult:
  result = (
    db.query(RemarkResult)
    .filter(RemarkResult.id == result_id, RemarkResult.remark_id == remark_id)
    .first()
  )
  if not result:
    raise HTTPException(status_code=404, detail="Результат выполнения не найден")
  return result


def ensure_result_editable(user: User, remark: Remark, result: RemarkResult) -> None:
  if remark.status == RemarkStatus.RESOLVED.value:
    raise HTTPException(status_code=400, detail="Устранённое замечание нельзя редактировать")
  if user.role == UserRole.EMPLOYEE.value and result.created_by_id == user.id:
    return
  if user.role == UserRole.DEPARTMENT_HEAD.value and user.department_id == remark.department_id:
    return
  raise HTTPException(status_code=403, detail="Недостаточно прав для редактирования результата")


@router.get("", response_model=PaginatedResponse[RemarkRead])
def list_remarks(
  user: Annotated[User, Depends(get_current_user)],
  status: str | None = Query(default=None),
  department_id: int | None = Query(default=None),
  assignee_id: int | None = Query(default=None),
  unassigned: bool | None = Query(default=None),
  no_executor: bool | None = Query(default=None),
  search: str | None = Query(default=None),
  letter_date_from: date | None = Query(default=None),
  letter_date_to: date | None = Query(default=None),
  object_id: int | None = Query(default=None),
  letter_id: int | None = Query(default=None),
  page: int = Query(default=1, ge=1),
  page_size: int | None = Query(default=None, ge=1),
  db: Session = Depends(get_db),
):
  settings = get_settings()
  size = min(page_size or settings.default_page_size, settings.max_page_size)
  query = build_visible_remarks_query(
    db,
    user,
    status=status,
    department_id=department_id,
    assignee_id=assignee_id,
    unassigned=unassigned,
    no_executor=no_executor,
    search=search,
    letter_date_from=letter_date_from,
    letter_date_to=letter_date_to,
    object_id=object_id,
    letter_id=letter_id,
  )
  items, total, pages = paginate_query(query, page, size)
  return PaginatedResponse(
    items=[remark_to_read(item) for item in items],
    total=total,
    page=page,
    page_size=size,
    pages=pages,
  )


@router.get("/meta")
def remarks_meta(
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  cache_key = f"meta:{user.role}:{user.department_id}:{user.id}"
  cached = cache_get(cache_key)
  if cached is not None:
    return cached

  query = build_visible_remarks_query(db, user).join(Remark.letter)

  def distinct_remark_values(column):
    rows = (
      query.with_entities(column)
      .filter(column.isnot(None), column != "")
      .distinct()
      .order_by(column)
      .limit(500)
      .all()
    )
    return [row[0] for row in rows]

  def distinct_letter_values(column):
    rows = (
      query.with_entities(column)
      .filter(column.isnot(None), column != "")
      .distinct()
      .order_by(column)
      .limit(500)
      .all()
    )
    return [row[0] for row in rows]

  object_rows = (
    query.with_entities(ProjectObject.name, ProjectObject.subobject_name)
    .join(Letter.object)
    .filter(ProjectObject.name.isnot(None), ProjectObject.name != "")
    .distinct()
    .order_by(ProjectObject.name, ProjectObject.subobject_name)
    .limit(500)
    .all()
  )

  result = {
    "document_types": distinct_remark_values(Remark.document_type),
    "from_whom": distinct_letter_values(Letter.from_whom),
    "objects": [f"{row[0]}/{row[1]}" if row[1] else row[0] for row in object_rows],
    "lep_accompaniments": distinct_letter_values(Letter.lep_accompaniment),
  }
  cache_set(cache_key, result)
  return result


@router.get("/{remark_id}", response_model=RemarkRead)
def get_remark(
  remark_id: int,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  remark = fetch_remark(db, remark_id)
  ensure_remark_visible(user, remark)
  return remark_to_read(remark)


@router.post("", response_model=RemarkRead)
def create_remark(
  payload: RemarkCreate,
  letter_id: int = Query(...),
  user: Annotated[User, Depends(require_roles(UserRole.GIP.value))] = ...,
  db: Session = Depends(get_db),
):
  fetch_letter(db, letter_id)
  remark = Remark(letter_id=letter_id, **payload.model_dump())
  db.add(remark)
  db.commit()
  invalidate_remarks_cache()
  return remark_to_read(fetch_remark(db, remark.id))


@router.put("/{remark_id}", response_model=RemarkRead)
def update_remark(
  remark_id: int,
  payload: RemarkUpdate,
  user: Annotated[User, Depends(require_roles(UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  remark = db.query(Remark).filter(Remark.id == remark_id).first()
  if not remark:
    raise HTTPException(status_code=404, detail="Замечание не найдено")
  for key, value in payload.model_dump(exclude_unset=True).items():
    setattr(remark, key, value)
  db.commit()
  invalidate_remarks_cache()
  return remark_to_read(fetch_remark(db, remark_id))


@router.post("/{remark_id}/assign-department", response_model=RemarkRead)
def assign_department(
  remark_id: int,
  payload: RemarkAssignDepartment,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  if not can_assign_department(user):
    raise HTTPException(status_code=403, detail="Только ГИП может назначать отдел")

  remark = db.query(Remark).filter(Remark.id == remark_id).first()
  if not remark:
    raise HTTPException(status_code=404, detail="Замечание не найдено")
  department = db.query(Department).filter(Department.id == payload.department_id).first()
  if not department:
    raise HTTPException(status_code=404, detail="Отдел не найден")

  remark.department_id = payload.department_id
  remark.assigned_by = user.display_name
  remark.assigned_at = datetime.utcnow()
  if payload.department_due_date < date.today():
    raise HTTPException(status_code=400, detail="Финальный срок не может быть в прошлом")
  remark.department_due_date = payload.department_due_date
  remark.status = RemarkStatus.IN_PROGRESS.value
  remark.assignee_id = None
  remark.assignee_assigned_by = None
  remark.assignee_assigned_at = None
  remark.due_date = None
  department_heads = (
    db.query(User)
    .filter(
      User.department_id == payload.department_id,
      User.role == UserRole.DEPARTMENT_HEAD.value,
      User.is_active.is_(True),
    )
    .all()
  )
  for department_head in department_heads:
    db.add(
      Notification(
        user_id=department_head.id,
        remark_id=remark.id,
        type="department_assigned",
        message=f"На отдел {department.code} назначено замечание #{remark.id}",
      )
    )
  db.commit()
  invalidate_remarks_cache()
  return remark_to_read(fetch_remark(db, remark_id))


@router.post("/{remark_id}/assign-executor", response_model=RemarkRead)
def assign_executor(
  remark_id: int,
  payload: RemarkAssignExecutor,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  remark = db.query(Remark).filter(Remark.id == remark_id).first()
  if not remark:
    raise HTTPException(status_code=404, detail="Замечание не найдено")
  if not remark.department_id:
    raise HTTPException(status_code=400, detail="Сначала ГИП должен назначить отдел")
  if not can_assign_executor(user, remark.department_id):
    raise HTTPException(status_code=403, detail="Недостаточно прав для назначения исполнителя")
  if remark.status not in {RemarkStatus.IN_PROGRESS.value, RemarkStatus.NEEDS_REVISION.value}:
    raise HTTPException(status_code=400, detail="Исполнителя можно назначить только для замечания в работе или на доработке")
  if payload.due_date < date.today():
    raise HTTPException(status_code=400, detail="Срок исполнителя не может быть в прошлом")
  if remark.department_due_date and payload.due_date > remark.department_due_date:
    raise HTTPException(status_code=400, detail="Срок исполнителя не может быть позже финального срока")

  assignee = (
    db.query(User)
    .filter(
      User.id == payload.assignee_id,
      User.role == UserRole.EMPLOYEE.value,
      User.is_active.is_(True),
    )
    .first()
  )
  if not assignee:
    raise HTTPException(status_code=404, detail="Исполнитель не найден")
  if assignee.department_id != remark.department_id:
    raise HTTPException(status_code=400, detail="Исполнитель должен быть из назначенного отдела")

  remark.assignee_id = payload.assignee_id
  remark.assignee_assigned_by = user.display_name
  remark.assignee_assigned_at = datetime.utcnow()
  remark.due_date = payload.due_date
  db.add(
    Notification(
      user_id=assignee.id,
      remark_id=remark.id,
      type="executor_assigned",
      message=f"Вам назначено замечание #{remark.id}",
    )
  )
  db.commit()
  invalidate_remarks_cache()
  return remark_to_read(fetch_remark(db, remark_id))


@router.patch("/{remark_id}/status", response_model=RemarkRead)
def update_remark_status(
  remark_id: int,
  payload: RemarkStatusUpdate,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  remark = db.query(Remark).filter(Remark.id == remark_id).first()
  if not remark:
    raise HTTPException(status_code=404, detail="Замечание не найдено")
  ensure_remark_visible(user, remark)

  if user.role != UserRole.GIP.value:
    raise HTTPException(status_code=403, detail="Только ОГИП может вручную менять статус")

  valid_statuses = {item.value for item in RemarkStatus}
  if payload.status not in valid_statuses:
    raise HTTPException(status_code=400, detail="Недопустимый статус")

  if payload.status == RemarkStatus.RESOLVED.value and not remark.results:
    raise HTTPException(status_code=400, detail="Нельзя устранить замечание без результата выполнения")

  comment = payload.resolution_notes.strip() if payload.resolution_notes else ""
  if payload.status == RemarkStatus.NEEDS_REVISION.value:
    if not comment:
      raise HTTPException(status_code=400, detail="Укажите, что необходимо доработать")
    db.add(
      RemarkFeedback(
        remark_id=remark.id,
        comment=comment,
        created_by_id=user.id,
        created_by_name=user.display_name,
      )
    )
    notify_assigned_department(
      db,
      remark,
      "remark_needs_revision",
      f"Замечание #{remark.id} возвращено на доработку: {comment}",
    )
  elif payload.status == RemarkStatus.RESOLVED.value:
    notify_assigned_department(
      db,
      remark,
      "remark_resolved",
      f"Замечание #{remark.id} успешно устранено",
    )

  remark.status = payload.status
  if payload.status == RemarkStatus.PENDING_REVIEW.value:
    notify_pending_review(db, remark, user)
  db.commit()
  invalidate_remarks_cache()
  return remark_to_read(fetch_remark(db, remark_id))


@router.post("/{remark_id}/result", response_model=RemarkRead)
async def submit_remark_result(
  remark_id: int,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
  resolution_notes: str | None = Form(default=None),
  file: UploadFile | None = File(default=None),
):
  remark = db.query(Remark).filter(Remark.id == remark_id).first()
  if not remark:
    raise HTTPException(status_code=404, detail="Замечание не найдено")
  ensure_remark_visible(user, remark)

  if remark.status == RemarkStatus.RESOLVED.value:
    raise HTTPException(status_code=400, detail="Замечание уже устранено")
  if user.role == UserRole.EMPLOYEE.value:
    if remark.assignee_id != user.id:
      raise HTTPException(status_code=403, detail="Недостаточно прав")
  elif user.role == UserRole.DEPARTMENT_HEAD.value:
    if user.department_id != remark.department_id:
      raise HTTPException(status_code=403, detail="Замечание назначено другому отделу")
  else:
    raise HTTPException(status_code=403, detail="Результат может добавить только назначенный отдел")

  notes = resolution_notes.strip() if resolution_notes else None
  if not notes and not file:
    raise HTTPException(status_code=400, detail="Опишите результат или прикрепите документ")

  result = RemarkResult(
    remark_id=remark.id,
    notes=notes,
    created_by_id=user.id,
    created_by_name=user.display_name,
  )
  db.add(result)
  db.flush()
  if file:
    await save_remark_result_file(result, file)

  remark.status = RemarkStatus.PENDING_REVIEW.value
  notify_pending_review(db, remark, user)
  db.commit()
  invalidate_remarks_cache()
  return remark_to_read(fetch_remark(db, remark_id))


@router.put("/{remark_id}/results/{result_id}", response_model=RemarkRead)
async def update_remark_result(
  remark_id: int,
  result_id: int,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
  notes: str = Form(default=""),
  file: UploadFile | None = File(default=None),
  remove_file: bool = Form(default=False),
):
  remark = fetch_remark(db, remark_id)
  ensure_remark_visible(user, remark)
  result = fetch_result(db, remark_id, result_id)
  ensure_result_editable(user, remark, result)

  result.notes = notes.strip() or None
  if remove_file:
    delete_remark_result_file(result)
    result.filename = None
    result.stored_name = None
    result.content_hash = None
    result.content_type = None
    result.file_size = None
  if file:
    await save_remark_result_file(result, file)
  if not result.notes and not result.stored_name:
    raise HTTPException(status_code=400, detail="Опишите результат или прикрепите документ")

  remark.status = RemarkStatus.PENDING_REVIEW.value
  notify_pending_review(db, remark, user)
  db.commit()
  invalidate_remarks_cache()
  return remark_to_read(fetch_remark(db, remark_id))


@router.delete("/{remark_id}/results/{result_id}", response_model=RemarkRead)
def delete_remark_result(
  remark_id: int,
  result_id: int,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  remark = fetch_remark(db, remark_id)
  ensure_remark_visible(user, remark)
  result = fetch_result(db, remark_id, result_id)
  ensure_result_editable(user, remark, result)
  delete_remark_result_file(result)
  db.delete(result)
  db.flush()
  if (
    remark.status == RemarkStatus.PENDING_REVIEW.value
    and not db.query(RemarkResult).filter(RemarkResult.remark_id == remark_id).first()
  ):
    remark.status = RemarkStatus.IN_PROGRESS.value
  db.commit()
  invalidate_remarks_cache()
  return remark_to_read(fetch_remark(db, remark_id))


@router.get("/{remark_id}/results/{result_id}/download")
def download_remark_result(
  remark_id: int,
  result_id: int,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  remark = fetch_remark(db, remark_id)
  ensure_remark_visible(user, remark)
  result = fetch_result(db, remark_id, result_id)
  path = get_remark_result_file_path(result)
  if not path or not path.exists() or not result.filename:
    raise HTTPException(status_code=404, detail="Файл результата не найден")
  return FileResponse(
    path,
    filename=result.filename,
    media_type=result.content_type or "application/octet-stream",
  )


@router.delete("/{remark_id}")
def delete_remark(
  remark_id: int,
  user: Annotated[User, Depends(require_roles(UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  remark = db.query(Remark).filter(Remark.id == remark_id).first()
  if not remark:
    raise HTTPException(status_code=404, detail="Замечание не найдено")
  for result in remark.results:
    delete_remark_result_file(result)
  delete_result_attachment_file(remark)
  db.delete(remark)
  db.commit()
  invalidate_remarks_cache()
  return {"ok": True}
