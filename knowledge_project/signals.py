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
    重置用户的保密柜验证失败计数
    当用户重置密码后调用此函数解除锁定
    """
    fail_key = f'vault_fail:{user_id}'
    lock_key = f'vault_lock:{user_id}'

    cache.delete(fail_key)
    cache.delete(lock_key)

    logger.info(f"用户 {user_id} 的保密柜锁定已通过密码重置解除")


def on_password_reset(user):
    """
    密码重置后的回调函数
    解除保密柜锁定状态

    Args:
        user: 重置密码的用户对象
    """
    reset_vault_fail_count_for_user(user.id)
    logger.info(f"用户 {user.id} 密码重置成功，保密柜锁定已解除")
