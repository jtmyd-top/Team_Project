def get_client_ip(request):
    """
    获取客户端真实IP地址

    Args:
        request: Django请求对象

    Returns:
        str: 客户端IP地址
    """
    # 优先检查代理头部
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # X-Forwarded-For可能包含多个IP，取第一个（客户端真实IP）
        ip = x_forwarded_for.split(',')[0].strip()
        return ip

    # 检查其他代理头部
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip

    # 最后使用REMOTE_ADDR（直连情况）
    remote_addr = request.META.get('REMOTE_ADDR')
    if remote_addr:
        return remote_addr

    # 如果都获取不到，返回默认值
    return '0.0.0.0'


def check_rate_limit_atomic(key, limit, timeout):
    """
    原子操作的限流检查
    使用Redis Lua脚本确保真正的原子性

    Args:
        key: 缓存键
        limit: 限制次数
        timeout: 过期时间（秒）

    Returns:
        tuple: (is_allowed: bool, current_attempts: int)
    """
    try:
        from knowledge_project.utils.redis_rate_limiter import check_redis_rate_limit
        return check_redis_rate_limit(key, limit, timeout)
    except ImportError:
        # 如果无法导入Redis限流器，回退到基本方法
        from django.core.cache import cache
        import logging
        logger = logging.getLogger(__name__)

        logger.warning("Redis限流器不可用，使用回退方法")

        try:
            current_count = cache.get(key, 0)
            if current_count >= limit:
                return False, current_count

            new_count = cache.incr(key)
            if new_count == 1:
                cache.expire(key, timeout)
            return new_count <= limit, new_count
        except Exception as e:
            logger.error(f"回退限流方法失败: {e}")
            return True, 0