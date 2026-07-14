from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import User, UserRole
from app.schemas.schemas import ImportJobRead, ImportResult
from app.services.import_jobs import get_import_job, import_sync, start_import_job
from app.services.stats import compute_stats

router = APIRouter(tags=["import", "stats"])


@router.get("/api/stats")
def get_stats(
  user: Annotated[User, Depends(get_current_user)],
  db: Session = Depends(get_db),
):
  cache_key = f"stats:{user.role}:{user.department_id}:{user.id}"
  cached = cache_get(cache_key)
  if cached is not None:
    return cached

  result = compute_stats(db, user)
  cache_set(cache_key, result)
  return result


@router.post("/api/import/excel", response_model=ImportResult)
async def import_excel_sync(
  file: UploadFile = File(...),
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))] = ...,
):
  if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
    raise HTTPException(status_code=400, detail="Поддерживаются только файлы .xlsx")

  content = await file.read()
  result = import_sync(file.filename, content)
  return ImportResult(**result)


@router.post("/api/import/excel/async", response_model=ImportJobRead)
async def import_excel_async(
  file: UploadFile = File(...),
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))] = ...,
):
  if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
    raise HTTPException(status_code=400, detail="Поддерживаются только файлы .xlsx")

  content = await file.read()
  job = start_import_job(file.filename, content)
  return ImportJobRead(**job)


@router.get("/api/import/jobs/{job_id}", response_model=ImportJobRead)
def get_job_status(
  job_id: str,
  user: Annotated[User, Depends(require_roles(UserRole.ADMIN.value, UserRole.GIP.value))],
):
  job = get_import_job(job_id)
  if not job:
    raise HTTPException(status_code=404, detail="Задача импорта не найдена")
  return ImportJobRead(**job)
