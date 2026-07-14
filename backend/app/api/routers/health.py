from fastapi import APIRouter

from app.core.cache import _get_redis
from app.core.database import engine
from app.schemas.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def health_check():
  db_status = "ok"
  try:
    with engine.connect() as connection:
      connection.exec_driver_sql("SELECT 1")
  except Exception:
    db_status = "error"

  cache_status = "ok" if _get_redis() else "disabled"

  return HealthResponse(
    status="ok" if db_status == "ok" else "degraded",
    database=db_status,
    cache=cache_status,
    version="2.0.0",
  )
