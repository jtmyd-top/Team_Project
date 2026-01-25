"""
基于Redis的真正原子限流器
使用Lua脚本确保操作的原子性
"""

from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

# Redis Lua脚本：原子性限流检查和计数
RATE_LIMIT_SCRIPT = """
-- KEYS[1]: 限流键
-- ARGV[1]: 限制次数
-- ARGV[2]: 过期时间（秒）

local current = redis.call('GET', KEYS[1])

if current == false then
    -- 键不存在，设置为1并设置过期时间
    redis.call('SET', KEYS[1], 1)
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    return {1, 1}  -- {当前次数, 是否允许}
end

current = tonumber(current)

if current >= tonumber(ARGV[1]) then
    -- 已经达到限制
    return {current, 0}  -- {当前次数, 是否允许}
end

-- 增加计数
local new_count = redis.call('INCR', KEYS[1])
return {new_count, 1}  -- {当前次数, 是否允许}
"""

def check_redis_rate_limit(key, limit, timeout):
    """
    使用Redis Lua脚本进行原子限流检查

    Args:
        key: 限流键
        limit: 限制次数
        timeout: 过期时间（秒）

    Returns:
        tuple: (is_allowed: bool, current_count: int)
    """
    try:
        # 获取Redis客户端
        if hasattr(cache, 'client'):
            redis_client = cache.client.get_client()
        elif hasattr(cache, '_client'):
            redis_client = cache._client
        else:
            # 如果无法获取Redis客户端，回退到普通方法
            logger.warning("无法获取Redis客户端，回退到普通限流方法")
            return check_fallback_rate_limit(key, limit, timeout)

        # 执行Lua脚本
        result = redis_client.eval(RATE_LIMIT_SCRIPT, 1, key, limit, timeout)

        if isinstance(result, (list, tuple)) and len(result) >= 2:
            current_count = int(result[0])
            is_allowed = bool(result[1])
            logger.debug(f"Redis rate limit check: key={key}, count={current_count}, allowed={is_allowed}")
            return is_allowed, current_count
        else:
            # 结果格式异常，回退到普通方法
            logger.warning(f"Redis脚本返回异常结果: {result}")
            return check_fallback_rate_limit(key, limit, timeout)

    except Exception as e:
        logger.error(f"Redis限流检查失败: {e}")
        return check_fallback_rate_limit(key, limit, timeout)


def check_fallback_rate_limit(key, limit, timeout):
    """
    回退的限流方法（非原子性，仅当Redis方法失败时使用）
    """
    try:
        current_count = cache.get(key, 0)
        if current_count >= limit:
            return False, current_count

        # 尝试原子递增
        try:
            new_count = cache.incr(key)
            if new_count == 1:
                cache.expire(key, timeout)
            return new_count <= limit, new_count
        except:
            # 如果递增失败，使用set
            cache.set(key, current_count + 1, timeout)
            return True, current_count + 1

    except Exception as e:
        logger.error(f"回退限流方法也失败: {e}")
        # 最后的安全措施：总是允许，但记录错误
        return True, 0


def reset_rate_limit(key):
    """
    重置指定键的限流计数
    """
    try:
        cache.delete(key)
        logger.debug(f"重置限流键: {key}")
        return True
    except Exception as e:
        logger.error(f"重置限流键失败: {e}")
        return False