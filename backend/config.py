import os
from functools import lru_cache


@lru_cache
def get_settings():
    return Settings()


class Settings:
  def __init__(self) -> None:
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
