"""频率限制 / 客户端指纹 / 客户端 IP 辅助函数。"""
from ._shared import *


# ==================== 验证码 API ====================
def get_client_fingerprint(request):
    """获取客户端指纹"""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')

    # 组合多个请求头信息生成指纹
    fingerprint_data = f"{user_agent}|{accept_language}|{accept_encoding}"
    fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]

    return fingerprint




def get_client_ip(request):
    """获取客户端真实IP地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def check_rate_limit(email, ip_address, fingerprint, limit=3):
    """
    检查频率限制（增强版）
    - 每个邮箱每天最多3封重置邮件
    - 每个IP每天最多10次请求
    - 每个客户端指纹每天最多5次请求
    - 检测对不存在邮箱的暴力枚举攻击
    """
    from ...models import PasswordResetAttempt
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 检查邮箱频率限制
    email_count = PasswordResetAttempt.objects.filter(
        email=email,
        attempted_at__gte=today_start
    ).count()
    if email_count >= limit:
        return False, f'该邮箱今天发送重置密码链接次数已达上限（{limit}次）'

    # 检查IP频率限制
    ip_count = PasswordResetAttempt.objects.filter(
        ip_address=ip_address,
        attempted_at__gte=today_start
    ).count()
    if ip_count >= 10:  # IP限制更宽松
        return False, '该IP今天请求次数过多，请明天再试'

    # 检查客户端指纹限制
    fingerprint_count = PasswordResetAttempt.objects.filter(
        fingerprint=fingerprint,
        attempted_at__gte=today_start
    ).count()
    if fingerprint_count >= 5:  # 客户端限制适中
        return False, '该设备今天请求次数过多，请明天再试'

    # 检测暴力枚举攻击：如果该IP最近有大量失败的邮箱尝试
    recent_time = now - timedelta(hours=1)  # 最近1小时
    failed_attempts = PasswordResetAttempt.objects.filter(
        ip_address=ip_address,
        is_successful=False,
        attempted_at__gte=recent_time
    ).count()

    # 如果1小时内有超过5次失败尝试，可能是枚举攻击
    if failed_attempts >= 5:
        unique_emails = PasswordResetAttempt.objects.filter(
            ip_address=ip_address,
            is_successful=False,
            attempted_at__gte=recent_time
        ).values('email').distinct().count()

        # 如果尝试了多个不同的邮箱，更可能是枚举攻击
        if unique_emails >= 3:
            logger.warning(f"检测到可能的邮箱枚举攻击: IP={ip_address}, 1小时内{failed_attempts}次失败尝试, {unique_emails}个不同邮箱")
            return False, '请求过于频繁，请稍后再试'

    return True, None
