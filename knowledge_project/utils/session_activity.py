"""Redis-backed session presence and session-key registry helpers."""

import logging
import time
from importlib import import_module

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


logger = logging.getLogger(__name__)

ONLINE_USERS_ZSET = 'presence:online_users'
MESSAGES_USERS_ZSET = 'presence:messages_page_users'
USER_SESSIONS_KEY = 'presence:user_sessions:{user_id}'
FALLBACK_LAST_ACTIVITY_KEY = 'presence:user:{user_id}:last_activity'
FALLBACK_MESSAGES_ACTIVITY_KEY = 'presence:user:{user_id}:messages_page_active_at'


def _now_ts():
    return int(timezone.now().timestamp())


def _session_ttl():
    return int(getattr(settings, 'SESSION_COOKIE_AGE', 10800)) + 600


def _get_redis_connection():
    try:
        from django_redis import get_redis_connection

        return get_redis_connection('default')
    except Exception as exc:
        logger.debug("Redis presence helpers unavailable: %s", exc)
        return None


def _decode(value):
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='ignore')
    return str(value)


def _mark_zset(key, user_id, timestamp, ttl):
    redis = _get_redis_connection()
    if not redis:
        return False
    redis.zadd(key, {str(user_id): int(timestamp)})
    redis.expire(key, ttl)
    return True


def _has_recent_zset(key, user_id, window_seconds, now_ts=None):
    redis = _get_redis_connection()
    if not redis:
        return None
    now_ts = int(now_ts or _now_ts())
    cutoff = now_ts - int(window_seconds)
    score = redis.zscore(key, str(user_id))
    return score is not None and int(float(score)) >= cutoff


def mark_user_activity(user_id, timestamp=None):
    if not user_id:
        return
    timestamp = int(timestamp or _now_ts())
    ttl = _session_ttl()
    if not _mark_zset(ONLINE_USERS_ZSET, user_id, timestamp, ttl):
        cache.set(FALLBACK_LAST_ACTIVITY_KEY.format(user_id=user_id), timestamp, ttl)


def count_recent_users(window_seconds, now_ts=None):
    now_ts = int(now_ts or _now_ts())
    cutoff = now_ts - int(window_seconds)
    redis = _get_redis_connection()
    if not redis:
        return 0
    redis.zremrangebyscore(ONLINE_USERS_ZSET, 0, cutoff - 1)
    return int(redis.zcard(ONLINE_USERS_ZSET))


def has_recent_user_activity(user_id, window_seconds, now_ts=None):
    if not user_id:
        return False
    recent = _has_recent_zset(ONLINE_USERS_ZSET, user_id, window_seconds, now_ts)
    if recent is not None:
        return recent
    last_activity = cache.get(FALLBACK_LAST_ACTIVITY_KEY.format(user_id=user_id))
    if not last_activity:
        return False
    now_ts = int(now_ts or _now_ts())
    try:
        return int(last_activity) >= now_ts - int(window_seconds)
    except (TypeError, ValueError):
        return False


def mark_messages_page_activity(user_id, timestamp=None):
    if not user_id:
        return
    timestamp = int(timestamp or _now_ts())
    ttl = _session_ttl()
    if not _mark_zset(MESSAGES_USERS_ZSET, user_id, timestamp, ttl):
        cache.set(FALLBACK_MESSAGES_ACTIVITY_KEY.format(user_id=user_id), timestamp, ttl)


def has_recent_messages_page_activity(user_id, window_seconds, now_ts=None):
    if not user_id:
        return False
    recent = _has_recent_zset(MESSAGES_USERS_ZSET, user_id, window_seconds, now_ts)
    if recent is not None:
        return recent
    page_activity = cache.get(FALLBACK_MESSAGES_ACTIVITY_KEY.format(user_id=user_id))
    if not page_activity:
        return False
    now_ts = int(now_ts or _now_ts())
    try:
        return int(page_activity) >= now_ts - int(window_seconds)
    except (TypeError, ValueError):
        return False


def register_user_session(user_id, session_key):
    if not user_id or not session_key:
        return
    redis = _get_redis_connection()
    if not redis:
        return
    key = USER_SESSIONS_KEY.format(user_id=user_id)
    redis.sadd(key, session_key)
    redis.expire(key, _session_ttl())


def invalidate_other_user_sessions(user_id, keep_session_key=None):
    """Delete registered sessions for a user except the current one."""
    deleted = 0
    redis = _get_redis_connection()
    if redis:
        key = USER_SESSIONS_KEY.format(user_id=user_id)
        session_keys = [_decode(item) for item in redis.smembers(key)]
        try:
            engine = import_module(settings.SESSION_ENGINE)
            SessionStore = engine.SessionStore
        except Exception as exc:
            logger.warning("Unable to load session engine for invalidation: %s", exc)
            SessionStore = None

        for session_key in session_keys:
            if keep_session_key and session_key == keep_session_key:
                continue
            if SessionStore is not None:
                try:
                    SessionStore(session_key=session_key).delete()
                    deleted += 1
                except Exception as exc:
                    logger.debug("Failed deleting session %s: %s", session_key, exc)
            redis.srem(key, session_key)
        redis.expire(key, _session_ttl())
        return deleted

    if settings.SESSION_ENGINE not in {
        'django.contrib.sessions.backends.db',
        'django.contrib.sessions.backends.cached_db',
    }:
        return deleted

    from django.contrib.sessions.models import Session

    for session in Session.objects.filter(expire_date__gte=timezone.now()).iterator():
        try:
            data = session.get_decoded()
        except Exception:
            continue
        if str(data.get('_auth_user_id')) != str(user_id):
            continue
        if keep_session_key and session.session_key == keep_session_key:
            continue
        session.delete()
        deleted += 1
    return deleted
