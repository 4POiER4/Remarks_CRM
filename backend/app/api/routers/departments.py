from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.core.cache import cache_get, cache_set, invalidate_remarks_cache
from app.core.database import get_db
from app.models.models import Department, Remark, User, UserRole
from app.schemas.schemas import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.services.remarks import department_remarks_counts, department_to_read

router = APIRouter(prefix="/api/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentRead])
def list_departments(
  user: Annotated[User, Depends(get_current_user)],
  kind: str | None = Query(default=None),
  db: Session = Depends(get_db),
):
  cache_key = f"departments:{kind or 'all'}:{user.role}:{user.department_id}"
  cached = cache_get(cache_key)
  if cached is not None:
    return cached

  query = db.query(Department)
  if kind:
    query = query.filter(Department.kind == kind)
  departments = query.order_by(Department.kind, Department.code).all()
  counts = department_remarks_counts(db)
  result = [department_to_read(department, counts.get(department.id, 0)) for department in departments]
  cache_set(cache_key, [item.model_dump() for item in result])
  return result


@router.post("", response_model=DepartmentRead)
def create_department(
  payload: DepartmentCreate,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  existing = (
    db.query(Department)
    .filter((Department.code == payload.code) | (Department.name == payload.name))
    .first()
  )
  if existing:
    raise HTTPException(status_code=400, detail="Запись с таким кодом или названием уже существует")
  department = Department(**payload.model_dump())
  db.add(department)
  db.commit()
  db.refresh(department)
  invalidate_remarks_cache()
  return department_to_read(department, 0)


@router.put("/{department_id}", response_model=DepartmentRead)
def update_department(
  department_id: int,
  payload: DepartmentUpdate,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  department = db.query(Department).filter(Department.id == department_id).first()
  if not department:
    raise HTTPException(status_code=404, detail="Запись не найдена")

  updates = payload.model_dump(exclude_unset=True)
  if "code" in updates:
    existing = (
      db.query(Department)
      .filter(Department.id != department_id, Department.code == updates["code"])
      .first()
    )
    if existing:
      raise HTTPException(status_code=400, detail="Запись с таким кодом уже существует")
  if "name" in updates:
    existing = (
      db.query(Department)
      .filter(Department.id != department_id, Department.name == updates["name"])
      .first()
    )
    if existing:
      raise HTTPException(status_code=400, detail="Запись с таким названием уже существует")

  for key, value in updates.items():
    setattr(department, key, value)
  db.commit()
  db.refresh(department)
  invalidate_remarks_cache()
  return department_to_read(department, 0)


@router.delete("/{department_id}")
def delete_department(
  department_id: int,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  department = db.query(Department).filter(Department.id == department_id).first()
  if not department:
    raise HTTPException(status_code=404, detail="Запись не найдена")

  remarks_count = db.query(Remark).filter(Remark.department_id == department_id).count()
  if remarks_count:
    raise HTTPException(
      status_code=400,
      detail=f"Нельзя удалить: есть {remarks_count} назначенных замечаний",
    )

  db.delete(department)
  db.commit()
  invalidate_remarks_cache()
  return {"ok": True}
