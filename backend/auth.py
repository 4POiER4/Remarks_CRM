from datetime import datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from ldap3 import ALL, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPException
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models import User, UserRole

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
  return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
  if not hashed:
    return False
  return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, username: str, role: str) -> str:
  settings = get_settings()
  expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
  payload = {
    "sub": str(user_id),
    "username": username,
    "role": role,
    "exp": expire,
  }
  return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
  settings = get_settings()
  try:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
  except jwt.PyJWTError as exc:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен") from exc


def _role_from_groups(member_of: list[str]) -> str:
  settings = get_settings()
  normalized = {value.lower() for value in member_of}
  if settings.ldap_group_admin and settings.ldap_group_admin.lower() in normalized:
    return UserRole.ADMIN.value
  if settings.ldap_group_gip and settings.ldap_group_gip.lower() in normalized:
    return UserRole.GIP.value
  if settings.ldap_group_department_head and settings.ldap_group_department_head.lower() in normalized:
    return UserRole.DEPARTMENT_HEAD.value
  return UserRole.EMPLOYEE.value


def authenticate_ldap(username: str, password: str) -> dict | None:
  settings = get_settings()
  if not settings.ldap_bind_dn:
    raise HTTPException(
      status_code=500,
      detail="LDAP_BIND_DN не настроен. Укажите сервисную учётную запись AD.",
    )

  try:
    server = Server(settings.ldap_server, get_info=ALL)
    search_conn = Connection(
      server,
      user=settings.ldap_bind_dn,
      password=settings.ldap_bind_password,
      auto_bind=True,
    )
    search_filter = settings.ldap_user_filter.format(username=username)
    search_conn.search(
      settings.ldap_base_dn,
      search_filter,
      search_scope=SUBTREE,
      attributes=["displayName", "mail", "sAMAccountName", "memberOf"],
    )
    if not search_conn.entries:
      return None

    entry = search_conn.entries[0]
    user_dn = entry.entry_dn
    auth_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
    if not auth_conn.bind():
      return None

    member_of = []
    if "memberOf" in entry:
      member_of = [str(value) for value in entry.memberOf.values]

    display_name = str(entry.displayName) if entry.displayName else username
    email = str(entry.mail) if entry.mail else None
    sam = str(entry.sAMAccountName) if entry.sAMAccountName else username

    return {
      "username": sam,
      "display_name": display_name,
      "email": email,
      "role": _role_from_groups(member_of),
    }
  except LDAPException as exc:
    raise HTTPException(status_code=503, detail=f"Ошибка подключения к AD: {exc}") from exc


def authenticate_local(db: Session, username: str, password: str) -> User | None:
  user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
  if not user or not verify_password(password, user.password_hash):
    return None
  return user


def get_or_create_user(db: Session, profile: dict) -> User:
  user = db.query(User).filter(User.username == profile["username"]).first()
  if user:
    user.display_name = profile.get("display_name") or user.display_name
    user.email = profile.get("email") or user.email
    if profile.get("role") and user.role == UserRole.EMPLOYEE.value:
      user.role = profile["role"]
    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user

  user = User(
    username=profile["username"],
    display_name=profile.get("display_name") or profile["username"],
    email=profile.get("email"),
    role=profile.get("role") or UserRole.EMPLOYEE.value,
    is_active=True,
    last_login_at=datetime.utcnow(),
  )
  db.add(user)
  db.commit()
  db.refresh(user)
  return user


def login_user(db: Session, username: str, password: str) -> User:
  settings = get_settings()
  username = username.strip()
  if not username or not password:
    raise HTTPException(status_code=400, detail="Введите логин и пароль")

  if settings.ldap_enabled:
    profile = authenticate_ldap(username, password)
    if not profile:
      raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return get_or_create_user(db, profile)

  user = authenticate_local(db, username, password)
  if not user:
    raise HTTPException(status_code=401, detail="Неверный логин или пароль")
  user.last_login_at = datetime.utcnow()
  db.commit()
  db.refresh(user)
  return user


def get_current_user(
  credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
  db: Session = Depends(get_db),
) -> User:
  if credentials is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
  payload = decode_token(credentials.credentials)
  user = db.query(User).filter(User.id == int(payload["sub"]), User.is_active.is_(True)).first()
  if not user:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
  return user


def require_roles(*roles: str):
  def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role not in roles:
      raise HTTPException(status_code=403, detail="Недостаточно прав")
    return user

  return dependency


def can_manage_all(user: User) -> bool:
  return user.role in {UserRole.ADMIN.value, UserRole.GIP.value}


def can_assign_department(user: User) -> bool:
  return user.role in {UserRole.ADMIN.value, UserRole.GIP.value}


def can_assign_executor(user: User, remark_department_id: int | None) -> bool:
  if user.role in {UserRole.ADMIN.value, UserRole.GIP.value}:
    return True
  if user.role == UserRole.DEPARTMENT_HEAD.value:
    return remark_department_id is not None and user.department_id == remark_department_id
  return False


