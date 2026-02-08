# knowledge_project/signals.py
"""
Django信号处理器
用于处理各种事件的回调
"""
import logging
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache

logger = logging.getLogger(__name__)


def reset_vault_fail_count_for_user(user_id):
    """
    重置用户的保密柜验证失败计数（设备级 + 用户级）
    当用户重置密码后调用此函数解除锁定
    """
    # 用户级
    for prefix in ['vault_fail', 'vault_lock', 'vault_user_fail', 'vault_user_lock']:
        cache.delete(f'{prefix}:{user_id}')

    # 设备级：通过 Redis 模式匹配清除 session-based 的 vault key
    try:
        from django_redis import get_redis_connection
        conn = get_redis_connection('default')
        for pattern in ['*vault_fail*', '*vault_lock*']:
            for k in conn.keys(pattern):
                conn.delete(k)
    except Exception:
        pass

    logger.info(f"用户 {user_id} 的保密柜锁定已通过密码重置解除")


def on_password_reset(user):
    """
    密码重置后的回调函数
    解除保密柜所有级别锁定（设备级 + 用户级 + IP级）

    Args:
        user: 重置密码的用户对象
    """
    # 清除设备级和用户级
    reset_vault_fail_count_for_user(user.id)

    # 清除IP级
    try:
        from .models import AccessLog

        # 查找该用户关联的所有IP
        user_ips = AccessLog.objects.filter(
            user_identifier=user.username,
            action='vault_fail'
        ).values_list('ip_address', flat=True).distinct()

        # 清除所有关联IP的封禁
        for ip in user_ips:
            if ip:
                cache.delete(f'banned_ip:{ip}')

        # 清除该用户的AccessLog失败记录
        AccessLog.objects.filter(
            user_identifier=user.username,
            action__in=['vault_fail', 'ip_banned']
        ).delete()

        logger.info(f"用户 {user.id} 密码重置: 已清除IP级限制, IPs: {set(user_ips)}")
    except Exception as e:
        logger.error(f"密码重置: 清除IP级限制失败: {e}")

    logger.info(f"用户 {user.id} 密码重置成功，所有级别保密柜锁定已解除")
