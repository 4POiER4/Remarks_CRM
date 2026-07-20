import os
from functools import lru_cache


@lru_cache
def get_settings() -> "Settings":
  return Settings()


class Settings:
  def __init__(self) -> None:
    self.app_env = os.getenv("APP_ENV", "development")
    self.debug = self.app_env != "production"

    self.database_url = os.getenv(
      "DATABASE_URL",
      "sqlite:///./zamechaniya.db",
    )
    self.db_pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
    self.db_max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    self.db_pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "1800"))

    self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    self.cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "60"))

    self.upload_dir = os.getenv("UPLOAD_DIR", "uploads")
    self.max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))

    self.cors_origins = [
      origin.strip()
      for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
      if origin.strip()
    ]

    self.ldap_enabled = os.getenv("LDAP_ENABLED", "false").lower() in {"1", "true", "yes"}
    self.ldap_server = os.getenv("LDAP_SERVER", "ldap://localhost")
    self.ldap_base_dn = os.getenv("LDAP_BASE_DN", "DC=example,DC=local")
    self.ldap_bind_dn = os.getenv("LDAP_BIND_DN", "")
    self.ldap_bind_password = os.getenv("LDAP_BIND_PASSWORD", "")
    self.ldap_user_filter = os.getenv(
      "LDAP_USER_FILTER",
      "(&(objectClass=user)(sAMAccountName={username}))",
    )
    self.ldap_group_gip = os.getenv("LDAP_GROUP_GIP", "")
    self.ldap_group_department_head = os.getenv("LDAP_GROUP_DEPARTMENT_HEAD", "")
    self.ldap_group_admin = os.getenv("LDAP_GROUP_ADMIN", "")

    self.jwt_secret = os.getenv("JWT_SECRET", "change-me-in-production")
    self.jwt_algorithm = "HS256"
    self.jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

    self.dev_admin_username = os.getenv("DEV_ADMIN_USERNAME", "admin")
    self.dev_admin_password = os.getenv("DEV_ADMIN_PASSWORD", "admin")
    self.seed_test_users = os.getenv("SEED_TEST_USERS", "false").lower() in {"1", "true", "yes"}
    self.test_user_password = os.getenv("TEST_USER_PASSWORD", "test123")

    self.default_page_size = int(os.getenv("DEFAULT_PAGE_SIZE", "50"))
    self.max_page_size = int(os.getenv("MAX_PAGE_SIZE", "200"))

    self.workers = int(os.getenv("WEB_CONCURRENCY", "4"))

  @property
  def is_sqlite(self) -> bool:
    return self.database_url.startswith("sqlite")

  @property
  def max_upload_size_bytes(self) -> int:
    return self.max_upload_size_mb * 1024 * 1024
