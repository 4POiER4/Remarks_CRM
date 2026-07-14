from sqlalchemy import func
from sqlalchemy.orm import Session

from app.filters import apply_remark_visibility
from app.models.models import Department, Remark, RemarkStatus, User


def compute_stats(db: Session, user: User) -> dict:
  base_query = apply_remark_visibility(db.query(Remark), user)

  total = base_query.count()

  status_rows = (
    apply_remark_visibility(db.query(Remark.status, func.count(Remark.id)), user)
    .group_by(Remark.status)
    .all()
  )
  by_status = {status.value: 0 for status in RemarkStatus}
  for status, count in status_rows:
    by_status[status] = count

  department_rows = (
    apply_remark_visibility(
      db.query(Department.code, Department.name, func.count(Remark.id))
      .join(Remark, Remark.department_id == Department.id),
      user,
    )
    .group_by(Department.id, Department.code, Department.name)
    .having(func.count(Remark.id) > 0)
    .order_by(Department.code)
    .all()
  )
  department_stats = [{"code": code, "name": name, "count": count} for code, name, count in department_rows]

  unassigned = base_query.filter(Remark.department_id.is_(None)).count()
  no_executor = base_query.filter(
    Remark.department_id.isnot(None),
    Remark.assignee_id.is_(None),
  ).count()

  return {
    "total": total,
    "by_status": by_status,
    "by_department": department_stats,
    "unassigned": unassigned,
    "no_executor": no_executor,
  }
