from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.core.database import get_db
from app.models.models import Notification, User
from app.schemas.schemas import NotificationRead

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
  user: Annotated[User, Depends(get_current_user)],
  unread_only: bool = False,
  db: Session = Depends(get_db),
):
  query = db.query(Notification).filter(Notification.user_id == user.id)
  if unread_only:
    query = query.filter(Notification.is_read.is_(False))
  return query.order_by(Notification.created_at.desc()).limit(50).all()


@router.get("/unread-count")
def unread_notifications_count(
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  count = (
    db.query(Notification)
    .filter(Notification.user_id == user.id, Notification.is_read.is_(False))
    .count()
  )
  return {"count": count}


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
  notification_id: int,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  notification = (
    db.query(Notification)
    .filter(Notification.id == notification_id, Notification.user_id == user.id)
    .first()
  )
  if not notification:
    raise HTTPException(status_code=404, detail="Уведомление не найдено")
  if notification and not notification.is_read:
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.commit()
    db.refresh(notification)
  return notification


@router.post("/mark-all-read")
def mark_all_notifications_read(
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  now = datetime.utcnow()
  updated = (
    db.query(Notification)
    .filter(Notification.user_id == user.id, Notification.is_read.is_(False))
    .update({Notification.is_read: True, Notification.read_at: now})
  )
  db.commit()
  return {"updated": updated}
