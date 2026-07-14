import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app.core.cache import cache_get, cache_set, invalidate_remarks_cache
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.excel_import import import_remarks_from_excel

_executor = ThreadPoolExecutor(max_workers=2)
_JOB_PREFIX = "import_job:"


def _job_key(job_id: str) -> str:
  return f"{_JOB_PREFIX}{job_id}"


def _save_job(job: dict) -> None:
  cache_set(_job_key(job["id"]), job, ttl=3600)


def get_import_job(job_id: str) -> dict | None:
  return cache_get(_job_key(job_id))


def _run_import(job_id: str, filename: str, content: bytes) -> None:
  db = SessionLocal()
  try:
    imported, skipped, errors = import_remarks_from_excel(content, db)
    job = {
      "id": job_id,
      "status": "completed",
      "filename": filename,
      "imported": imported,
      "skipped": skipped,
      "errors": errors,
      "created_at": datetime.utcnow().isoformat(),
      "finished_at": datetime.utcnow().isoformat(),
    }
    _save_job(job)
    invalidate_remarks_cache()
  except Exception as exc:
    job = {
      "id": job_id,
      "status": "failed",
      "filename": filename,
      "imported": 0,
      "skipped": 0,
      "errors": [str(exc)],
      "created_at": datetime.utcnow().isoformat(),
      "finished_at": datetime.utcnow().isoformat(),
    }
    _save_job(job)
  finally:
    db.close()


def start_import_job(filename: str, content: bytes) -> dict:
  job_id = str(uuid.uuid4())
  job = {
    "id": job_id,
    "status": "processing",
    "filename": filename,
    "imported": 0,
    "skipped": 0,
    "errors": [],
    "created_at": datetime.utcnow().isoformat(),
    "finished_at": None,
  }
  _save_job(job)
  _executor.submit(_run_import, job_id, filename, content)
  return job


def import_sync(filename: str, content: bytes) -> dict:
  db = SessionLocal()
  try:
    imported, skipped, errors = import_remarks_from_excel(content, db)
    invalidate_remarks_cache()
    return {
      "imported": imported,
      "skipped": skipped,
      "errors": errors,
    }
  finally:
    db.close()
