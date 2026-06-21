"""群组安全模块：频率限制、PoW 防护、防滥用"""

import hashlib
import json
import logging
from django.core.cache import cache
from django.http import JsonResponse
from functools import wraps

logger = logging.getLogger(__name__)


# ========================
# PoW (Proof of Work) 防护
# ========================

def verify_pow_challenge(token, nonce, difficulty=4):
    """
    验证工作量证明

    Args:
        token: 邀请令牌或其他标识符
        nonce: 客户端提交的随机数
        difficulty: 难度级别（前导零的数量）

    Returns:
        bool: 验证是否通过
    """
    try:
        challenge = f"{token}:{nonce}"
        hash_result = hashlib.sha256(challenge.encode()).hexdigest()
        return hash_result.startswith('0' * difficulty)
    except Exception as e:
        logger.error(f"PoW verification error: {e}")
        return False


def require_pow_for_invite(difficulty=4):
    """
    装饰器：要求邀请链接操作提供 PoW 证明

    用于防止脚本批量滥用邀请链接
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # 获取邀请令牌（从 URL 或请求体）
            token = kwargs.get('token') or request.GET.get('token')
            if not token:
                return JsonResponse({'error': 'Missing token'}, status=400)

            # 检查是否需要 PoW（可以根据 IP 频率动态调整）
            ip_key = f"invite_attempts:{request.META.get('REMOTE_ADDR')}:{token}"
            attempts = cache.get(ip_key, 0)

            # 如果 1 小时内同一 IP 对同一邀请链接尝试超过 3 次，要求 PoW
            if attempts >= 3:
                nonce = request.GET.get('pow_nonce') or request.POST.get('pow_nonce')
                if not nonce:
                    return JsonResponse({
                        'error': 'PoW required',
                        'code': 'pow_required',
                        'message': '检测到频繁请求，请完成验证',
                        'challenge': {
                            'token': token,
                            'difficulty': difficulty,
                        }
                    }, status=429)

                if not verify_pow_challenge(token, nonce, difficulty):
                    return JsonResponse({
                        'error': 'Invalid PoW',
                        'message': '验证失败，请重试'
                    }, status=403)

            # 记录尝试次数
            cache.set(ip_key, attempts + 1, timeout=3600)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ========================
# 令牌桶算法 - 群消息频率限制
# ========================

class TokenBucket:
    """令牌桶算法实现"""

    def __init__(self, capacity=5, refill_rate=2):
        """
        Args:
            capacity: 桶的最大容量（允许的突发消息数）
            refill_rate: 每秒补充的令牌数
        """
        self.capacity = capacity
        self.refill_rate = refill_rate

    def consume(self, user_id, group_id, tokens=1):
        """
        尝试消费令牌

        Returns:
            tuple: (success: bool, remaining: int, retry_after: float)
        """
        key = f"token_bucket:{group_id}:{user_id}"
        bucket_data = cache.get(key)

        import time
        now = time.time()

        if bucket_data is None:
            # 初始化桶
            bucket_data = {
                'tokens': self.capacity,
                'last_refill': now
            }
        else:
            # 补充令牌
            elapsed = now - bucket_data['last_refill']
            refill_tokens = elapsed * self.refill_rate
            bucket_data['tokens'] = min(
                self.capacity,
                bucket_data['tokens'] + refill_tokens
            )
            bucket_data['last_refill'] = now

        # 尝试消费
        if bucket_data['tokens'] >= tokens:
            bucket_data['tokens'] -= tokens
            cache.set(key, bucket_data, timeout=60)
            return True, int(bucket_data['tokens']), 0
        else:
            # 计算需要等待的时间
            needed_tokens = tokens - bucket_data['tokens']
            retry_after = needed_tokens / self.refill_rate
            cache.set(key, bucket_data, timeout=60)
            return False, 0, retry_after


# 全局令牌桶实例
message_rate_limiter = TokenBucket(capacity=5, refill_rate=2)


def check_message_rate_limit(user_id, group_id):
    """
    检查消息发送频率

    Returns:
        tuple: (allowed: bool, error_response: JsonResponse or None)
    """
    success, remaining, retry_after = message_rate_limiter.consume(user_id, group_id)

    if not success:
        logger.warning(f"Rate limit hit for user {user_id} in group {group_id}")
        return False, JsonResponse({
            'error': '发送频率过快',
            'code': 'rate_limit',
            'retry_after': int(retry_after) + 1,
            'message': f'请等待 {int(retry_after) + 1} 秒后再发送'
        }, status=429)

    return True, None


# ========================
# 滑动窗口算法 - 精确限流
# ========================

def check_sliding_window_limit(user_id, group_id, window_seconds=5, max_messages=10):
    """
    滑动窗口限流：在指定时间窗口内限制消息数量

    Args:
        user_id: 用户 ID
        group_id: 群组 ID
        window_seconds: 时间窗口（秒）
        max_messages: 窗口内最大消息数

    Returns:
        tuple: (allowed: bool, current_count: int)
    """
    import time
    now = time.time()
    key = f"sliding_window:{group_id}:{user_id}"

    # 使用 Redis ZSET 存储时间戳
    # 这里用 cache，实际生产环境建议直接用 Redis
    timestamps = cache.get(key, [])

    # 移除窗口外的时间戳
    cutoff = now - window_seconds
    timestamps = [ts for ts in timestamps if ts > cutoff]

    if len(timestamps) >= max_messages:
        cache.set(key, timestamps, timeout=window_seconds + 5)
        return False, len(timestamps)

    # 添加当前时间戳
    timestamps.append(now)
    cache.set(key, timestamps, timeout=window_seconds + 5)

    return True, len(timestamps)


# ========================
# 熔断与惩罚机制
# ========================

def check_and_apply_circuit_breaker(user_id, group_id):
    """
    熔断机制：连续触发限流后临时封禁

    Returns:
        tuple: (blocked: bool, block_remaining_seconds: int)
    """
    block_key = f"circuit_breaker:{group_id}:{user_id}"
    block_until = cache.get(block_key)

    if block_until:
        import time
        remaining = max(0, int(block_until - time.time()))
        if remaining > 0:
            return True, remaining
        else:
            cache.delete(block_key)

    # 检查触发次数
    trigger_key = f"rate_limit_triggers:{group_id}:{user_id}"
    triggers = cache.get(trigger_key, 0)

    if triggers >= 3:
        # 触发熔断：封禁 5 分钟
        import time
        block_until = time.time() + 300
        cache.set(block_key, block_until, timeout=300)
        cache.delete(trigger_key)

        logger.warning(f"Circuit breaker activated for user {user_id} in group {group_id}")
        return True, 300

    return False, 0


def increment_rate_limit_trigger(user_id, group_id):
    """增加限流触发计数"""
    trigger_key = f"rate_limit_triggers:{group_id}:{user_id}"
    triggers = cache.get(trigger_key, 0)
    cache.set(trigger_key, triggers + 1, timeout=600)  # 10 分钟内有效


# ========================
# 综合检查函数
# ========================

def check_group_message_security(user_id, group_id):
    """
    综合安全检查：熔断 -> 令牌桶 -> 滑动窗口

    Returns:
        tuple: (allowed: bool, error_response: JsonResponse or None)
    """
    # 1. 检查熔断状态
    blocked, block_time = check_and_apply_circuit_breaker(user_id, group_id)
    if blocked:
        return False, JsonResponse({
            'error': '发送被暂时限制',
            'code': 'circuit_breaker',
            'retry_after': block_time,
            'message': f'检测到异常行为，请在 {block_time} 秒后重试'
        }, status=429)

    # 2. 令牌桶检查（允许突发）
    allowed, error_response = check_message_rate_limit(user_id, group_id)
    if not allowed:
        increment_rate_limit_trigger(user_id, group_id)
        return False, error_response

    # 3. 滑动窗口检查（严格限制）
    allowed, count = check_sliding_window_limit(user_id, group_id)
    if not allowed:
        increment_rate_limit_trigger(user_id, group_id)
        return False, JsonResponse({
            'error': '发送过于频繁',
            'code': 'sliding_window_limit',
            'message': '5 秒内最多发送 10 条消息',
            'current_count': count
        }, status=429)

    return True, None
