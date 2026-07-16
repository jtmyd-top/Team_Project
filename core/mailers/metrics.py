"""Durable, privacy-preserving email delivery metrics."""

from __future__ import annotations

import logging
import re


logger = logging.getLogger(__name__)
_EMAIL_PATTERN = re.compile(r'(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
_IP_PATTERN = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')


def classify_email_category(subject: str) -> str:
    """Map a message subject to a dashboard-safe delivery category."""
    text = (subject or '').lower()
    if '管理后台登录验证码' in text:
        return 'admin_login_2fa'
    if '登录验证码' in text:
        return 'login_2fa'
    if '保密柜' in text and '验证码' in text:
        return 'vault_code'
    if '注册验证码' in text:
        return 'registration_code'
    if '邮箱修改验证码' in text:
        return 'email_change_code'
    if '密码修改验证码' in text:
        return 'password_change_code'
    if '密码重置' in text:
        return 'password_reset'
    if '验证码' in text:
        return 'verification_code'
    if '登录' in text and ('提醒' in text or '通知' in text):
        return 'login_alert'
    if '安全' in text:
        return 'security_alert'
    if '通知' in text or '消息' in text:
        return 'notification'
    return 'other'


def record_email_delivery(
    *,
    subject: str,
    recipient_count: int,
    success: bool,
    provider: str,
    error_message: str = '',
) -> None:
    """Record a send result without persisting any recipient address or content."""
    try:
        from accounts.models import EmailDeliveryLog

        safe_error = _EMAIL_PATTERN.sub('[redacted-email]', error_message or '')
        safe_error = _IP_PATTERN.sub('[redacted-ip]', safe_error)
        EmailDeliveryLog.objects.create(
            category=classify_email_category(subject),
            status=EmailDeliveryLog.STATUS_SUCCEEDED if success else EmailDeliveryLog.STATUS_FAILED,
            subject=(subject or '')[:255],
            recipient_count=max(0, int(recipient_count or 0)),
            provider=(provider or '')[:64],
            error_message=safe_error[:500],
        )
    except Exception:
        # Observability must never affect the actual delivery path.
        logger.exception('Unable to record email delivery metric')
