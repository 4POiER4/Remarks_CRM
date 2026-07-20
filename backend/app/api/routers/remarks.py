from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.models.models import Department, Letter, Notification, ProjectObject, Remark, RemarkStatus, User, UserRole
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
  ensure_remark_visible,
  fetch_letter,
  fetch_remark,
  paginate_query,
  remark_to_read,
)

router = APIRouter(prefix="/api/remarks", tags=["remarks"])


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
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))] = ...,
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
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
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
  remark.status = payload.status
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
  remark.status = RemarkStatus.IN_PROGRESS.value
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

  if user.role == UserRole.EMPLOYEE.value and remark.assignee_id != user.id:
    raise HTTPException(status_code=403, detail="Недостаточно прав")

  valid_statuses = {item.value for item in RemarkStatus}
  if payload.status not in valid_statuses:
    raise HTTPException(status_code=400, detail="Недопустимый статус")

  if user.role == UserRole.EMPLOYEE.value and payload.status == RemarkStatus.RESOLVED.value:
    raise HTTPException(status_code=403, detail="Статус устранено может поставить ГИП или начальник отдела")

  remark.status = payload.status
  if payload.resolution_notes is not None:
    remark.resolution_notes = payload.resolution_notes
  if payload.status == RemarkStatus.PENDING_REVIEW.value:
    reviewers = (
      db.query(User)
      .filter(
        User.is_active.is_(True),
        (
          User.role.in_([UserRole.ADMIN.value, UserRole.GIP.value])
          | (
            (User.role == UserRole.DEPARTMENT_HEAD.value)
            & (User.department_id == remark.department_id)
          )
        ),
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
  db.commit()
  invalidate_remarks_cache()
  return remark_to_read(fetch_remark(db, remark_id))


@router.delete("/{remark_id}")
def delete_remark(
  remark_id: int,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  remark = db.query(Remark).filter(Remark.id == remark_id).first()
  if not remark:
    raise HTTPException(status_code=404, detail="Замечание не найдено")
  db.delete(remark)
  db.commit()
  invalidate_remarks_cache()
  return {"ok": True}
