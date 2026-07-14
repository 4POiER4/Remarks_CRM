from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.core.cache import invalidate_remarks_cache
from app.core.database import get_db
from app.models.models import Letter, ProjectObject, Remark, User, UserRole
from app.schemas.schemas import ObjectCreate, ObjectRead, ObjectUpdate
from app.services.remarks import fetch_object, object_counts, object_to_read

router = APIRouter(prefix="/api/objects", tags=["objects"])


@router.get("", response_model=list[ObjectRead])
def list_objects(
  user: Annotated[User, Depends(get_current_user)],
  search: str | None = Query(default=None),
  db: Session = Depends(get_db),
):
  query = db.query(ProjectObject)
  if search and search.strip():
    pattern = f"%{search.strip()}%"
    query = query.filter(
      or_(
        ProjectObject.name.ilike(pattern),
        ProjectObject.subobject_name.ilike(pattern),
      )
    )
  objects = query.order_by(ProjectObject.name, ProjectObject.subobject_name).all()
  counts = object_counts(db)
  return [
    object_to_read(
      obj,
      letters_count=counts.get(obj.id, (0, 0))[0],
      remarks_count=counts.get(obj.id, (0, 0))[1],
    )
    for obj in objects
  ]


@router.post("", response_model=ObjectRead)
def create_object(
  payload: ObjectCreate,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  name = payload.name.strip()
  subobject_name = payload.subobject_name.strip() if payload.subobject_name else None
  if not name:
    raise HTTPException(status_code=400, detail="Укажите название объекта")
  existing = (
    db.query(ProjectObject)
    .filter(ProjectObject.name == name, ProjectObject.subobject_name == subobject_name)
    .first()
  )
  if existing:
    raise HTTPException(status_code=400, detail="Объект с таким названием уже существует")
  obj = ProjectObject(name=name, subobject_name=subobject_name)
  db.add(obj)
  db.commit()
  db.refresh(obj)
  invalidate_remarks_cache()
  return object_to_read(obj)


@router.get("/{object_id}", response_model=ObjectRead)
def get_object(
  object_id: int,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  obj = fetch_object(db, object_id)
  counts = object_counts(db)
  letters_count, remarks_count = counts.get(obj.id, (0, 0))
  return object_to_read(obj, letters_count=letters_count, remarks_count=remarks_count)


@router.put("/{object_id}", response_model=ObjectRead)
def update_object(
  object_id: int,
  payload: ObjectUpdate,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  obj = fetch_object(db, object_id)
  name = payload.name.strip()
  subobject_name = payload.subobject_name.strip() if payload.subobject_name else None
  if not name:
    raise HTTPException(status_code=400, detail="Укажите название объекта")
  existing = (
    db.query(ProjectObject)
    .filter(
      ProjectObject.id != object_id,
      ProjectObject.name == name,
      ProjectObject.subobject_name == subobject_name,
    )
    .first()
  )
  if existing:
    raise HTTPException(status_code=400, detail="Объект с таким названием уже существует")
  obj.name = name
  obj.subobject_name = subobject_name
  db.commit()
  db.refresh(obj)
  invalidate_remarks_cache()
  counts = object_counts(db)
  letters_count, remarks_count = counts.get(obj.id, (0, 0))
  return object_to_read(obj, letters_count=letters_count, remarks_count=remarks_count)


@router.delete("/{object_id}")
def delete_object(
  object_id: int,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  obj = fetch_object(db, object_id)
  letters_count = db.query(Letter).filter(Letter.object_id == object_id).count()
  if letters_count:
    raise HTTPException(status_code=400, detail="Нельзя удалить объект с письмами")
  db.delete(obj)
  db.commit()
  invalidate_remarks_cache()
  return {"ok": True}
