from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.core.cache import invalidate_remarks_cache
from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import Letter, LetterAttachment, Remark, User, UserRole
from app.schemas.schemas import (
  LetterAttachmentRead,
  LetterCreate,
  LetterRead,
  LetterUpdate,
  PaginatedResponse,
  RemarkCreate,
  RemarkRead,
)
from app.services.remarks import (
  attachment_to_read,
  build_visible_remarks_query,
  delete_attachment_file,
  fetch_letter,
  fetch_object,
  fetch_remark,
  get_attachment_path,
  letter_remarks_counts,
  letter_to_read,
  paginate_query,
  remark_to_read,
  save_letter_attachment,
)

router = APIRouter(tags=["letters"])


@router.get("/api/objects/{object_id}/letters", response_model=list[LetterRead])
def list_letters(
  object_id: int,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  fetch_object(db, object_id)
  letters = (
    db.query(Letter)
    .filter(Letter.object_id == object_id)
    .order_by(Letter.letter_date.desc(), Letter.created_at.desc())
    .all()
  )
  counts = letter_remarks_counts(db, object_id)
  return [letter_to_read(letter, remarks_count=counts.get(letter.id, 0)) for letter in letters]


@router.post("/api/objects/{object_id}/letters", response_model=LetterRead)
def create_letter(
  object_id: int,
  payload: LetterCreate,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  fetch_object(db, object_id)
  letter = Letter(object_id=object_id, **payload.model_dump())
  db.add(letter)
  db.commit()
  db.refresh(letter)
  invalidate_remarks_cache()
  return letter_to_read(letter)


@router.get("/api/letters/{letter_id}", response_model=LetterRead)
def get_letter(
  letter_id: int,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  letter = fetch_letter(db, letter_id)
  counts = letter_remarks_counts(db)
  return letter_to_read(
    letter,
    remarks_count=counts.get(letter.id, 0),
    include_attachments=True,
  )


@router.put("/api/letters/{letter_id}", response_model=LetterRead)
def update_letter(
  letter_id: int,
  payload: LetterUpdate,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  letter = fetch_letter(db, letter_id)
  for key, value in payload.model_dump(exclude_unset=True).items():
    setattr(letter, key, value)
  db.commit()
  db.refresh(letter)
  invalidate_remarks_cache()
  counts = letter_remarks_counts(db)
  return letter_to_read(letter, remarks_count=counts.get(letter.id, 0), include_attachments=True)


@router.delete("/api/letters/{letter_id}")
def delete_letter(
  letter_id: int,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  letter = fetch_letter(db, letter_id)
  for attachment in letter.attachments:
    delete_attachment_file(attachment)
  db.delete(letter)
  db.commit()
  invalidate_remarks_cache()
  return {"ok": True}


@router.get("/api/letters/{letter_id}/remarks", response_model=PaginatedResponse[RemarkRead])
def list_letter_remarks(
  letter_id: int,
  user: Annotated[User, Depends(get_current_user)],
  status: str | None = Query(default=None),
  department_id: int | None = Query(default=None),
  search: str | None = Query(default=None),
  page: int = Query(default=1, ge=1),
  page_size: int | None = Query(default=None, ge=1),
  db: Session = Depends(get_db),
):
  fetch_letter(db, letter_id)
  settings = get_settings()
  size = min(page_size or settings.default_page_size, settings.max_page_size)
  query = build_visible_remarks_query(
    db,
    user,
    letter_id=letter_id,
    status=status,
    department_id=department_id,
    search=search,
  )
  items, total, pages = paginate_query(query, page, size)
  return PaginatedResponse(
    items=[remark_to_read(item) for item in items],
    total=total,
    page=page,
    page_size=size,
    pages=pages,
  )


@router.post("/api/letters/{letter_id}/remarks", response_model=RemarkRead)
def create_letter_remark(
  letter_id: int,
  payload: RemarkCreate,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  fetch_letter(db, letter_id)
  remark = Remark(letter_id=letter_id, **payload.model_dump())
  db.add(remark)
  db.commit()
  invalidate_remarks_cache()
  return remark_to_read(fetch_remark(db, remark.id))


@router.post("/api/letters/{letter_id}/attachments", response_model=LetterAttachmentRead)
async def upload_attachment(
  letter_id: int,
  file: UploadFile = File(...),
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))] = ...,
  db: Session = Depends(get_db),
):
  letter = fetch_letter(db, letter_id)
  attachment = await save_letter_attachment(db, letter, file, user.display_name)
  return attachment_to_read(attachment)


@router.get("/api/letters/{letter_id}/attachments", response_model=list[LetterAttachmentRead])
def list_attachments(
  letter_id: int,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  letter = fetch_letter(db, letter_id)
  return [attachment_to_read(item) for item in letter.attachments]


@router.get("/api/attachments/{attachment_id}/download")
def download_attachment(
  attachment_id: int,
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  attachment = db.query(LetterAttachment).filter(LetterAttachment.id == attachment_id).first()
  if not attachment:
    raise HTTPException(status_code=404, detail="Файл не найден")
  path = get_attachment_path(attachment)
  if not path.exists():
    raise HTTPException(status_code=404, detail="Файл не найден на диске")
  return FileResponse(
    path,
    filename=attachment.filename,
    media_type=attachment.content_type or "application/octet-stream",
  )


@router.delete("/api/attachments/{attachment_id}")
def delete_attachment(
  attachment_id: int,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
  db: Session = Depends(get_db),
):
  attachment = db.query(LetterAttachment).filter(LetterAttachment.id == attachment_id).first()
  if not attachment:
    raise HTTPException(status_code=404, detail="Файл не найден")
  delete_attachment_file(attachment)
  db.delete(attachment)
  db.commit()
  return {"ok": True}
