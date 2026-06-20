"""频率限制 / 客户端指纹 / 客户端 IP 辅助函数。"""

from datetime import timedelta

from ._shared import *
from accounts.models import PasswordResetAttempt
from core.utils.request_utils import get_client_ip as resolve_client_ip


def get_client_fingerprint(request):
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
    fingerprint_data = f"{user_agent}|{accept_language}|{accept_encoding}"
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]


def get_client_ip(request):
    return resolve_client_ip(request)


def check_rate_limit(email, ip_address, fingerprint, limit=3):
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    email_count = PasswordResetAttempt.objects.filter(
        email=email,
        attempted_at__gte=today_start,
    ).count()
    if email_count >= limit:
        return False, f'该邮箱今天发送重置邮件次数已达上限（{limit} 次）'

    ip_count = PasswordResetAttempt.objects.filter(
        ip_address=ip_address,
        attempted_at__gte=today_start,
    ).count()
    if ip_count >= 10:
        return False, '该 IP 今天请求次数过多，请明天再试'

    fingerprint_count = PasswordResetAttempt.objects.filter(
        fingerprint=fingerprint,
        attempted_at__gte=today_start,
    ).count()
    if fingerprint_count >= 5:
        return False, '该设备今天请求次数过多，请明天再试'

    recent_time = now - timedelta(hours=1)
    failed_attempts = PasswordResetAttempt.objects.filter(
        ip_address=ip_address,
        is_successful=False,
        attempted_at__gte=recent_time,
    ).count()

    if failed_attempts >= 5:
        unique_emails = PasswordResetAttempt.objects.filter(
            ip_address=ip_address,
            is_successful=False,
            attempted_at__gte=recent_time,
        ).values('email').distinct().count()

        if unique_emails >= 3:
            logger.warning(
                "Possible password-reset enumeration detected: ip=%s failed_attempts=%s unique_emails=%s",
                ip_address,
                failed_attempts,
                unique_emails,
            )
            return False, '请求过于频繁，请稍后再试'

    return True, None
