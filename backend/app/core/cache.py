import json
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client = None
_redis_checked = False


def _get_redis():
  global _redis_client, _redis_checked
  if _redis_checked:
    return _redis_client

  _redis_checked = True
  settings = get_settings()
  try:
    import redis

    client = redis.from_url(settings.redis_url, decode_responses=True)
    client.ping()
    _redis_client = client
    logger.info("Redis cache connected")
  except Exception as exc:
    logger.warning("Redis unavailable, caching disabled: %s", exc)
    _redis_client = None
  return _redis_client


def cache_get(key: str) -> Any | None:
  client = _get_redis()
  if not client:
    return None
  try:
    value = client.get(key)
    return json.loads(value) if value else None
  except Exception as exc:
    logger.warning("Cache get failed for %s: %s", key, exc)
    return None


def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
  client = _get_redis()
  if not client:
    return
  settings = get_settings()
  try:
    client.setex(key, ttl or settings.cache_ttl_seconds, json.dumps(value, default=str))
  except Exception as exc:
    logger.warning("Cache set failed for %s: %s", key, exc)


def cache_delete_pattern(pattern: str) -> None:
  client = _get_redis()
  if not client:
    return
  try:
    for key in client.scan_iter(match=pattern):
      client.delete(key)
  except Exception as exc:
    logger.warning("Cache delete failed for %s: %s", pattern, exc)


def invalidate_remarks_cache() -> None:
  cache_delete_pattern("stats:*")
  cache_delete_pattern("meta:*")
  cache_delete_pattern("departments:*")
