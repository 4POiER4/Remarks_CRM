from datetime import date

from sqlalchemy import func, or_
from sqlalchemy.orm import Query

from auth import can_manage_all
from models import Remark, User, UserRole


SEARCHABLE_COLUMNS = (
  Remark.from_whom,
  Remark.letter_number,
  Remark.object_name,
  Remark.lep_accompaniment,
  Remark.document_remark,
  Remark.document_type,
  Remark.remark_text,
)


def _ilike(column, value: str):
  needle = f"%{value.strip().lower()}%"
  return func.coalesce(func.lower(column), "").like(needle)


def apply_remark_visibility(query: Query, user: User) -> Query:
  if can_manage_all(user):
    return query
  if user.role == UserRole.DEPARTMENT_HEAD.value and user.department_id:
    return query.filter(Remark.department_id == user.department_id)
  if user.role == UserRole.EMPLOYEE.value:
    return query.filter(Remark.assignee_id == user.id)
  return query.filter(False)


def apply_remark_filters(
  query: Query,
  *,
  status: str | None = None,
  department_id: int | None = None,
  assignee_id: int | None = None,
  unassigned: bool | None = None,
  no_executor: bool | None = None,
  search: str | None = None,
  letter_date_from: date | None = None,
  letter_date_to: date | None = None,
) -> Query:
  if status:
    query = query.filter(Remark.status == status)

  if unassigned is True:
    query = query.filter(Remark.department_id.is_(None))
  elif unassigned is False:
    query = query.filter(Remark.department_id.isnot(None))
  elif department_id:
    query = query.filter(Remark.department_id == department_id)

  if no_executor is True:
    query = query.filter(Remark.assignee_id.is_(None), Remark.department_id.isnot(None))
  elif no_executor is False:
    query = query.filter(Remark.assignee_id.isnot(None))
  elif assignee_id:
    query = query.filter(Remark.assignee_id == assignee_id)

  if search and search.strip():
    term = search.strip()
    query = query.filter(or_(*(_ilike(column, term) for column in SEARCHABLE_COLUMNS)))

  if letter_date_from:
    query = query.filter(Remark.letter_date >= letter_date_from)

  if letter_date_to:
    query = query.filter(Remark.letter_date <= letter_date_to)

  return query
