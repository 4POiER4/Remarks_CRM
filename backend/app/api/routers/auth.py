from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.auth import create_access_token, get_current_user, login_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import LoginRequest, TokenResponse, UserRead
from app.services.remarks import user_to_read

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def auth_login(payload: LoginRequest, db: Session = Depends(get_db)):
  user = login_user(db, payload.username, payload.password)
  user = (
    db.query(User)
    .options(joinedload(User.department))
    .filter(User.id == user.id)
    .first()
  )
  token = create_access_token(user.id, user.username, user.role)
  return TokenResponse(access_token=token, user=user_to_read(user))


@router.get("/me", response_model=UserRead)
def auth_me(user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)):
  db_user = (
    db.query(User)
    .options(joinedload(User.department))
    .filter(User.id == user.id)
    .first()
  )
  return user_to_read(db_user)
