"""
Redis-backed atomic rate limiting helpers.
"""

import logging

from django.core.cache import cache


logger = logging.getLogger(__name__)

RATE_LIMIT_SCRIPT = """
local current = redis.call('GET', KEYS[1])

if current == false then
    redis.call('SET', KEYS[1], 1)
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    return {1, 1}
end

current = tonumber(current)

if current >= tonumber(ARGV[1]) then
    return {current, 0}
end

local new_count = redis.call('INCR', KEYS[1])
return {new_count, 1}
"""


def check_redis_rate_limit(key, limit, timeout):
    try:
        if hasattr(cache, 'client'):
            redis_client = cache.client.get_client()
        elif hasattr(cache, '_client'):
            redis_client = cache._client
        else:
            logger.warning("Unable to get Redis client, falling back to cache rate limit")
            return check_fallback_rate_limit(key, limit, timeout)

        result = redis_client.eval(RATE_LIMIT_SCRIPT, 1, key, limit, timeout)

        if isinstance(result, (list, tuple)) and len(result) >= 2:
            current_count = int(result[0])
            is_allowed = bool(result[1])
            logger.debug(
                "Redis rate limit check: key=%s, count=%s, allowed=%s",
                key,
                current_count,
                is_allowed,
            )
            return is_allowed, current_count

        logger.warning("Redis rate limit script returned an unexpected result: %s", result)
        return check_fallback_rate_limit(key, limit, timeout)

    except Exception as exc:
        logger.error("Redis rate limit check failed: %s", exc)
        return check_fallback_rate_limit(key, limit, timeout)


def check_fallback_rate_limit(key, limit, timeout):
    try:
        current_count = cache.get(key, 0)
        if current_count >= limit:
            return False, current_count

        try:
            new_count = cache.incr(key)
            if new_count == 1:
                cache.expire(key, timeout)
            return new_count <= limit, new_count
        except Exception:
            cache.set(key, current_count + 1, timeout)
            return True, current_count + 1

    except Exception as exc:
        logger.error("Fallback rate limit check failed: %s", exc)
        return True, 0


def reset_rate_limit(key):
    try:
        cache.delete(key)
        logger.debug("Reset rate limit key: %s", key)
        return True
    except Exception as exc:
        logger.error("Failed to reset rate limit key: %s", exc)
        return False
