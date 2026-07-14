from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.auth import can_manage_all, get_current_user, require_roles
from app.core.database import get_db
from app.models.models import Department, User, UserRole
from app.schemas.schemas import UserRead, UserUpdate
from app.services.remarks import user_to_read

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
  user: Annotated[User, Depends(get_current_user)],
  department_id: int | None = Query(default=None),
  db: Session = Depends(get_db),
):
  query = db.query(User).options(joinedload(User.department)).filter(User.is_active.is_(True))
  if department_id:
    query = query.filter(User.department_id == department_id)
  elif user.role == UserRole.DEPARTMENT_HEAD.value and user.department_id:
    query = query.filter(User.department_id == user.department_id)
  elif not can_manage_all(user) and user.role != UserRole.ADMIN.value:
    raise HTTPException(status_code=403, detail="Недостаточно прав")

  users = query.order_by(User.display_name).all()
  return [user_to_read(item) for item in users]


@router.put("/{user_id}", response_model=UserRead)
def update_user(
  user_id: int,
  payload: UserUpdate,
  current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value))],
  db: Session = Depends(get_db),
):
  target = (
    db.query(User)
    .options(joinedload(User.department))
    .filter(User.id == user_id)
    .first()
  )
  if not target:
    raise HTTPException(status_code=404, detail="Пользователь не найден")

  updates = payload.model_dump(exclude_unset=True)
  if "department_id" in updates and updates["department_id"] is not None:
    department = db.query(Department).filter(Department.id == updates["department_id"]).first()
    if not department:
      raise HTTPException(status_code=404, detail="Отдел не найден")

  for key, value in updates.items():
    setattr(target, key, value)
  db.commit()
  db.refresh(target)
  return user_to_read(target)
