from sqlalchemy.orm import Session

from auth import hash_password
from config import get_settings
from database import engine
from models import Department, User, UserRole

DEFAULT_DEPARTMENTS = [
  "ОГИП",
  "ПТО",
  "ОТ",
  "ОЭ",
  "ОСУ",
  "АСО",
  "ОТС",
  "ОГПиТ",
  "ОГВ",
  "ОСД",
  "ОПОС",
  "ОЭК",
  "ОАТП",
  "ОРАЭС",
]

STATUS_MIGRATION = {
  "new": "in_progress",
  "assigned": "in_progress",
  "verified": "resolved",
}


def _table_columns(connection, table_name: str) -> set[str]:
  return {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()}


def migrate_schema() -> None:
  with engine.begin() as connection:
    department_columns = _table_columns(connection, "departments")
    if "kind" not in department_columns:
      connection.exec_driver_sql(
        "ALTER TABLE departments ADD COLUMN kind VARCHAR(20) DEFAULT 'department'"
      )
      connection.exec_driver_sql(
        "UPDATE departments SET kind = 'department' WHERE kind IS NULL"
      )

    remark_columns = _table_columns(connection, "remarks")
    remark_migrations = {
      "assignee_id": "INTEGER REFERENCES users(id)",
      "assignee_assigned_by": "VARCHAR(255)",
      "assignee_assigned_at": "DATETIME",
    }
    for column, column_type in remark_migrations.items():
      if column not in remark_columns:
        connection.exec_driver_sql(f"ALTER TABLE remarks ADD COLUMN {column} {column_type}")


def seed_default_departments(db: Session) -> None:
  existing_codes = {department.code for department in db.query(Department).all()}
  for code in DEFAULT_DEPARTMENTS:
    if code not in existing_codes:
      db.add(Department(name=code, code=code, kind="department"))
  db.commit()


def seed_admin_user(db: Session) -> None:
  settings = get_settings()
  if settings.ldap_enabled:
    return

  admin = db.query(User).filter(User.username == settings.dev_admin_username).first()
  password_hash = hash_password(settings.dev_admin_password)
  if admin:
    admin.password_hash = password_hash
    admin.role = UserRole.ADMIN.value
    admin.is_active = True
    if not admin.display_name:
      admin.display_name = "Администратор"
  else:
    db.add(
      User(
        username=settings.dev_admin_username,
        display_name="Администратор",
        password_hash=password_hash,
        role=UserRole.ADMIN.value,
        is_active=True,
      )
    )
  db.commit()


def migrate_statuses(db: Session) -> None:
  from models import Remark

  for old_status, new_status in STATUS_MIGRATION.items():
    db.query(Remark).filter(Remark.status == old_status).update({Remark.status: new_status})
  db.commit()
