from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, departments, health, import_stats, letters, notifications, objects, remarks, users
from app.core.config import get_settings
from app.core.database import Base, engine, get_db
from app.seed import (
  migrate_hierarchy,
  migrate_schema,
  migrate_statuses,
  seed_admin_user,
  seed_default_departments,
  seed_test_users,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
  Base.metadata.create_all(bind=engine)
  migrate_schema()
  db = next(get_db())
  try:
    seed_default_departments(db)
    seed_admin_user(db)
    seed_test_users(db)
    migrate_statuses(db)
    migrate_hierarchy(db)
  finally:
    db.close()
  yield


def create_app() -> FastAPI:
  settings = get_settings()
  app = FastAPI(
    title="Учёт замечаний",
    version="2.0.0",
    lifespan=lifespan,
  )

  app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if not settings.debug else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
  )

  app.include_router(health.router)
  app.include_router(auth.router)
  app.include_router(users.router)
  app.include_router(departments.router)
  app.include_router(objects.router)
  app.include_router(letters.router)
  app.include_router(remarks.router)
  app.include_router(notifications.router)
  app.include_router(import_stats.router)

  return app


app = create_app()
