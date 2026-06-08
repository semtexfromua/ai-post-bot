from app.core.config import settings

_KEY_PREFIX = "m4:seen:"


def is_duplicate(content_hash: str, redis_client) -> bool:
    """Atomic exact-dedup via Redis SET NX EX.

    Returns True if the hash was already present (duplicate), False if this call
    recorded it for the first time. TTL = settings.DEDUP_TTL_SECONDS.
    """
    key = f"{_KEY_PREFIX}{content_hash}"
    stored = redis_client.set(key, "1", nx=True, ex=settings.DEDUP_TTL_SECONDS)
    # set() returns True when the key was newly set, None/False when it already existed.
    return not stored
