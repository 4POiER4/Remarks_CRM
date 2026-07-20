from datetime import date, datetime

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.core.config import get_settings
from app.core.database import engine
from app.models.models import Department, Letter, ProjectObject, Remark, User, UserRole

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


def _table_columns(table_name: str) -> set[str]:
  if engine.dialect.name == "sqlite":
    with engine.connect() as connection:
      return {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()}
  inspector = inspect(engine)
  if table_name not in inspector.get_table_names():
    return set()
  return {column["name"] for column in inspector.get_columns(table_name)}


def migrate_schema() -> None:
  remark_columns = _table_columns("remarks")
  if not remark_columns:
    return

  with engine.begin() as connection:
    attachment_columns = _table_columns("letter_attachments")
    if attachment_columns and "content_hash" not in attachment_columns:
      connection.exec_driver_sql("ALTER TABLE letter_attachments ADD COLUMN content_hash VARCHAR(64)")

    if not _table_columns("notifications"):
      if engine.dialect.name == "sqlite":
        connection.exec_driver_sql(
          """
          CREATE TABLE notifications (
            id INTEGER NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id),
            remark_id INTEGER REFERENCES remarks(id),
            type VARCHAR(50) NOT NULL,
            message VARCHAR(500) NOT NULL,
            is_read BOOLEAN DEFAULT 0 NOT NULL,
            created_at DATETIME NOT NULL,
            read_at DATETIME,
            PRIMARY KEY (id)
          )
          """
        )
        connection.exec_driver_sql("CREATE INDEX ix_notifications_user_id ON notifications (user_id)")
        connection.exec_driver_sql("CREATE INDEX ix_notifications_remark_id ON notifications (remark_id)")
        connection.exec_driver_sql("CREATE INDEX ix_notifications_type ON notifications (type)")
        connection.exec_driver_sql("CREATE INDEX ix_notifications_is_read ON notifications (is_read)")
        connection.exec_driver_sql("CREATE INDEX ix_notifications_created_at ON notifications (created_at)")
        connection.exec_driver_sql(
          "CREATE INDEX ix_notifications_user_read_created ON notifications (user_id, is_read, created_at)"
        )
      else:
        connection.exec_driver_sql(
          """
          CREATE TABLE notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            remark_id INTEGER REFERENCES remarks(id),
            type VARCHAR(50) NOT NULL,
            message VARCHAR(500) NOT NULL,
            is_read BOOLEAN DEFAULT FALSE NOT NULL,
            created_at TIMESTAMP NOT NULL,
            read_at TIMESTAMP
          )
          """
        )

    if engine.dialect.name == "sqlite":
      object_columns = _table_columns("objects")
      if object_columns and "subobject_name" not in object_columns:
        connection.exec_driver_sql("ALTER TABLE objects ADD COLUMN subobject_name VARCHAR(255)")

      object_indexes = connection.exec_driver_sql("PRAGMA index_list(objects)").fetchall()
      has_legacy_name_unique = False
      for row in object_indexes:
        if not bool(row[2]):
          continue
        indexed_columns = [
          column[2]
          for column in connection.exec_driver_sql(f"PRAGMA index_info({row[1]})").fetchall()
        ]
        if indexed_columns == ["name"]:
          has_legacy_name_unique = True
          break
      if has_legacy_name_unique:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql(
          """
          CREATE TABLE objects_new (
            id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            subobject_name VARCHAR(255),
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_objects_name_subobject UNIQUE (name, subobject_name)
          )
          """
        )
        connection.exec_driver_sql(
          """
          INSERT INTO objects_new (id, name, subobject_name, created_at, updated_at)
          SELECT id, name, subobject_name, created_at, updated_at FROM objects
          """
        )
        connection.exec_driver_sql("DROP TABLE objects")
        connection.exec_driver_sql("ALTER TABLE objects_new RENAME TO objects")
        connection.exec_driver_sql("CREATE INDEX ix_objects_name ON objects (name)")
        connection.exec_driver_sql("CREATE INDEX ix_objects_subobject_name ON objects (subobject_name)")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")

      department_columns = _table_columns("departments")
      if "kind" not in department_columns:
        connection.exec_driver_sql(
          "ALTER TABLE departments ADD COLUMN kind VARCHAR(20) DEFAULT 'department'"
        )
        connection.exec_driver_sql(
          "UPDATE departments SET kind = 'department' WHERE kind IS NULL"
        )

      remark_migrations = {
        "assignee_id": "INTEGER REFERENCES users(id)",
        "assignee_assigned_by": "VARCHAR(255)",
        "assignee_assigned_at": "DATETIME",
        "department_due_date": "DATE",
        "due_date": "DATE",
        "letter_id": "INTEGER REFERENCES letters(id)",
      }
      for column, column_type in remark_migrations.items():
        if column not in remark_columns:
          connection.exec_driver_sql(f"ALTER TABLE remarks ADD COLUMN {column} {column_type}")
    else:
      object_columns = _table_columns("objects")
      if object_columns and "subobject_name" not in object_columns:
        connection.exec_driver_sql("ALTER TABLE objects ADD COLUMN subobject_name VARCHAR(255)")
      if "due_date" not in remark_columns:
        connection.exec_driver_sql("ALTER TABLE remarks ADD COLUMN due_date DATE")
      if "department_due_date" not in remark_columns:
        connection.exec_driver_sql("ALTER TABLE remarks ADD COLUMN department_due_date DATE")
      if "letter_id" not in remark_columns:
        connection.exec_driver_sql(
          "ALTER TABLE remarks ADD COLUMN letter_id INTEGER REFERENCES letters(id)"
        )

    result_file_migrations = {
      "result_filename": "VARCHAR(255)",
      "result_stored_name": "VARCHAR(255)",
      "result_content_hash": "VARCHAR(64)",
      "result_content_type": "VARCHAR(100)",
      "result_file_size": "INTEGER",
      "result_uploaded_by": "VARCHAR(255)",
      "result_uploaded_at": "TIMESTAMP",
    }
    for column, column_type in result_file_migrations.items():
      if column not in remark_columns:
        connection.exec_driver_sql(f"ALTER TABLE remarks ADD COLUMN {column} {column_type}")

    if _table_columns("remark_results"):
      connection.exec_driver_sql(
        """
        INSERT INTO remark_results (
          remark_id, notes, filename, stored_name, content_hash, content_type,
          file_size, created_by_id, created_by_name, created_at, updated_at
        )
        SELECT
          remarks.id,
          remarks.resolution_notes,
          remarks.result_filename,
          remarks.result_stored_name,
          remarks.result_content_hash,
          remarks.result_content_type,
          remarks.result_file_size,
          NULL,
          COALESCE(remarks.result_uploaded_by, 'Неизвестно'),
          COALESCE(remarks.result_uploaded_at, remarks.updated_at, remarks.created_at),
          COALESCE(remarks.result_uploaded_at, remarks.updated_at, remarks.created_at)
        FROM remarks
        WHERE (remarks.resolution_notes IS NOT NULL OR remarks.result_stored_name IS NOT NULL)
          AND NOT EXISTS (
            SELECT 1 FROM remark_results WHERE remark_results.remark_id = remarks.id
          )
        """
      )
      connection.exec_driver_sql(
        """
        UPDATE remark_results
        SET created_by_id = (
          SELECT users.id
          FROM users
          WHERE users.display_name = remark_results.created_by_name
          ORDER BY users.id
          LIMIT 1
        )
        WHERE created_by_id IS NULL
        """
      )


def _get_or_create_object(db: Session, name: str) -> ProjectObject:
  obj = db.query(ProjectObject).filter(ProjectObject.name == name).first()
  if obj:
    return obj
  obj = ProjectObject(name=name)
  db.add(obj)
  db.flush()
  return obj


def _letter_key(row: dict) -> tuple:
  return (
    row.get("object_name") or "Без объекта",
    row.get("from_whom") or "",
    row.get("letter_number") or "",
    str(row.get("letter_date") or ""),
    row.get("lep_accompaniment") or "",
    str(row.get("lep_accompaniment_date") or ""),
  )


def _parse_db_date(value) -> date | None:
  if value is None or value == "":
    return None
  if isinstance(value, date):
    return value
  if isinstance(value, datetime):
    return value.date()
  text_value = str(value).strip()
  for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
    try:
      return datetime.strptime(text_value, fmt).date()
    except ValueError:
      continue
  return None


def migrate_hierarchy(db: Session) -> None:
  remark_columns = _table_columns("remarks")
  if "object_name" not in remark_columns:
    return

  rows = db.execute(
    text(
      """
      SELECT id, object_name, from_whom, letter_number, letter_date,
             lep_accompaniment, lep_accompaniment_date, letter_id
      FROM remarks
      WHERE letter_id IS NULL
      """
    )
  ).mappings().all()

  if not rows:
    return

  object_cache: dict[str, ProjectObject] = {}
  letter_cache: dict[tuple, Letter] = {}

  for row in rows:
    object_name = (row["object_name"] or "").strip() or "Без объекта"
    if object_name not in object_cache:
      object_cache[object_name] = _get_or_create_object(db, object_name)
    obj = object_cache[object_name]

    key = _letter_key(dict(row))
    if key not in letter_cache:
      letter = (
        db.query(Letter)
        .filter(
          Letter.object_id == obj.id,
          Letter.from_whom == (row["from_whom"] or None),
          Letter.letter_number == (row["letter_number"] or None),
          Letter.letter_date == _parse_db_date(row["letter_date"]),
          Letter.lep_accompaniment == (row["lep_accompaniment"] or None),
          Letter.lep_accompaniment_date == _parse_db_date(row["lep_accompaniment_date"]),
        )
        .first()
      )
      if not letter:
        letter = Letter(
          object_id=obj.id,
          from_whom=row["from_whom"],
          letter_number=row["letter_number"],
          letter_date=_parse_db_date(row["letter_date"]),
          lep_accompaniment=row["lep_accompaniment"],
          lep_accompaniment_date=_parse_db_date(row["lep_accompaniment_date"]),
        )
        db.add(letter)
        db.flush()
      letter_cache[key] = letter

    db.execute(
      text("UPDATE remarks SET letter_id = :letter_id WHERE id = :id"),
      {"letter_id": letter_cache[key].id, "id": row["id"]},
    )

  db.commit()


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


def seed_test_users(db: Session) -> None:
  settings = get_settings()
  if not settings.seed_test_users or settings.ldap_enabled:
    return

  password_hash = hash_password(settings.test_user_password)
  department_by_code = {department.code: department for department in db.query(Department).all()}
  test_users = [
    ("ogip", "ОГИП тест", UserRole.GIP.value, "ОГИП"),
    ("pto_head", "Начальник ПТО", UserRole.DEPARTMENT_HEAD.value, "ПТО"),
    ("pto_emp1", "Инженер ПТО 1", UserRole.EMPLOYEE.value, "ПТО"),
    ("pto_emp2", "Инженер ПТО 2", UserRole.EMPLOYEE.value, "ПТО"),
    ("ot_head", "Начальник ОТ", UserRole.DEPARTMENT_HEAD.value, "ОТ"),
    ("ot_emp1", "Инженер ОТ 1", UserRole.EMPLOYEE.value, "ОТ"),
    ("oe_head", "Начальник ОЭ", UserRole.DEPARTMENT_HEAD.value, "ОЭ"),
    ("oe_emp1", "Инженер ОЭ 1", UserRole.EMPLOYEE.value, "ОЭ"),
  ]

  for username, display_name, role, department_code in test_users:
    department = department_by_code.get(department_code)
    user = db.query(User).filter(User.username == username).first()
    if user:
      user.display_name = display_name
      user.role = role
      user.department_id = department.id if department else None
      user.password_hash = password_hash
      user.is_active = True
    else:
      db.add(
        User(
          username=username,
          display_name=display_name,
          password_hash=password_hash,
          role=role,
          department_id=department.id if department else None,
          is_active=True,
        )
      )
  db.commit()


def migrate_statuses(db: Session) -> None:
  for old_status, new_status in STATUS_MIGRATION.items():
    db.query(Remark).filter(Remark.status == old_status).update({Remark.status: new_status})
  db.commit()
