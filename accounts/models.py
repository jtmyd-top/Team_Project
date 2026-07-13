import logging
import os
from datetime import timedelta
from io import BytesIO

from django.contrib.auth.models import User
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.safestring import mark_safe
from PIL import Image
from core.utils.request_utils import get_client_ip


logger = logging.getLogger(__name__)


def user_avatar_path(instance, filename):
    return f'user_{instance.user.id}/avatar/{filename}'


def default_theme_settings():
    return {
        'mode': 'light',
        'primary_color': '#409EFF',
        'font_size': 14,
        'compact_mode': False,
        'animations': True,
        'dark_mode': False,
    }


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='关联用户')
    activation_code = models.CharField(max_length=8, blank=True, null=True, unique=True, verbose_name='激活码')
    code_created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    avatar = models.ImageField(upload_to=user_avatar_path, null=True, blank=True, verbose_name='头像')
    avatar_source = models.CharField(max_length=32, blank=True, verbose_name='头像来源')
    bio = models.TextField(
        max_length=160,
        blank=True,
        validators=[MaxLengthValidator(160)],
        verbose_name='个人简介',
    )
    banner_image = models.FileField(
        upload_to=user_avatar_path,
        null=True,
        blank=True,
        verbose_name='主页横幅',
    )
    theme = models.JSONField(
        default=default_theme_settings,
        verbose_name='主题设置',
        help_text='存储用户界面主题配置',
    )
    layout_mode = models.CharField(
        max_length=20,
        choices=[('default', '默认布局'), ('compact', '紧凑布局'), ('wide', '宽屏布局')],
        default='default',
        verbose_name='界面布局',
    )
    last_theme_update = models.DateTimeField(
        auto_now=True,
        verbose_name='最后主题更新时间',
        help_text='记录用户最后修改主题的时间',
    )
    allow_rich_bio = models.BooleanField(default=False, verbose_name='允许富文本简介')
    email_last_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Last email change time',
    )
    likes_count = models.IntegerField(default=0, verbose_name='获赞数')
    last_updated = models.DateTimeField(auto_now=True, verbose_name='最后更新时间')
    two_fa_enabled = models.BooleanField(default=False, verbose_name='启用两因素认证')
    two_fa_method = models.CharField(
        max_length=10,
        choices=[('totp', 'TOTP验证器'), ('email', '邮箱验证')],
        default='totp',
        blank=True,
        verbose_name='2FA验证方式',
    )
    totp_secret = models.CharField(
        max_length=32,
        blank=True,
        verbose_name='TOTP密钥',
        help_text='用于 Google Authenticator 等 TOTP 应用的密钥',
    )
    backup_codes = models.JSONField(
        default=list,
        blank=True,
        verbose_name='备用验证码',
        help_text='用于 TOTP 设备丢失时的一次性备用码',
    )
    notify_login = models.BooleanField(
        default=True,
        verbose_name='登录通知',
        help_text='账户登录时发送邮件通知',
    )
    notify_password_change = models.BooleanField(
        default=True,
        verbose_name='密码修改通知',
        help_text='密码修改时发送邮件通知',
    )
    notify_password_reset = models.BooleanField(
        default=True,
        verbose_name='密码重置通知',
        help_text='密码重置时发送邮件通知',
    )
    notify_note_activities = models.BooleanField(
        default=False,
        verbose_name='笔记活动通知',
        help_text='笔记创建/修改/删除时发送邮件通知',
    )
    notify_profile_likes = models.BooleanField(
        default=True,
        verbose_name='点赞通知',
        help_text='个人空间或作品被点赞时发送邮件通知',
    )
    discoverable_by_username = models.BooleanField(
        default=False,
        verbose_name='允许通过用户名搜索到我',
        help_text='关闭后即使输入完整用户名也无法被搜索到',
    )
    discoverable_by_email = models.BooleanField(
        default=False,
        verbose_name='允许通过邮箱搜索到我',
        help_text='关闭后即使输入完整邮箱也无法被搜索到',
    )
    search_code = models.CharField(
        max_length=12,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='公开搜索短码',
        help_text='8 位随机字符串，用户可主动分享给朋友用于添加',
    )
    encrypted_vault_key = models.TextField(
        null=True,
        blank=True,
        verbose_name='加密保险柜密钥',
        help_text='Base64编码的AES加密DEK，用KEK加密',
    )
    vault_key_iv = models.TextField(
        null=True,
        blank=True,
        verbose_name='保险柜密钥IV',
        help_text='加密DEK时的初始化向量（Base64编码）',
    )
    vault_initialized = models.BooleanField(
        default=False,
        verbose_name='保险柜已初始化',
        help_text='用户是否已初始化保险柜',
    )

    class Meta:
        db_table = 'accounts_profile'
        verbose_name = '用户资料'
        verbose_name_plural = '用户资料'

    def clean_bio(self):
        from nh3 import clean

        if self.allow_rich_bio:
            return clean(
                self.bio,
                tags={'a', 'b', 'i', 'strong', 'em', 'br', 'p'},
                attributes={'a': {'href', 'title', 'target'}},
                url_schemes={'http', 'https'},
            )
        return self.escape_markup(self.bio)

    @staticmethod
    def escape_markup(text):
        from django.utils.html import escape

        return mark_safe(escape(text))

    def save(self, *args, **kwargs):
        self.bio = self.clean_bio()
        super().save(*args, **kwargs)
        self.process_banner_image()

    def process_banner_image(self):
        if self.banner_image:
            try:
                file_path = self.banner_image.path
                file_ext = os.path.splitext(file_path)[1].lower()

                if file_ext in ['.mp4', '.webm', '.avi', '.mov', '.mkv']:
                    logger.info('Skipping video banner processing: %s', file_path)
                    return

                img = Image.open(file_path)
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                img.thumbnail((2560, 600))

                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=85, optimize=True)
                self.banner_image.save(
                    os.path.basename(self.banner_image.name),
                    ContentFile(buffer.getvalue()),
                    save=False,
                )
            except Exception as exc:
                logger.error('Failed to process banner image: %s', exc)

    def __str__(self):
        return f'{self.user.username} Profile'

    @property
    def avatar_url(self):
        if self.avatar:
            try:
                return self.avatar.url
            except ValueError:
                pass
        return '/static/img/default-avatar.png'


class ProfileVisit(models.Model):
    """A visit to a user's public profile page."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='profile_visits')
    viewer = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='profile_visits_made',
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_profilevisit'
        verbose_name = 'Profile visit'
        verbose_name_plural = 'Profile visits'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['profile', '-created_at'], name='profilevisit_profile_idx'),
            models.Index(fields=['viewer', '-created_at'], name='profilevisit_viewer_idx'),
        ]

    def __str__(self):
        viewer = self.viewer.username if self.viewer_id else self.session_key or 'anonymous'
        return f'{viewer} visited {self.profile.user.username}'


class ProfileLike(models.Model):
    liker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_likes', verbose_name='点赞者')
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='received_likes',
        verbose_name='被点赞的用户资料',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='点赞时间')

    class Meta:
        db_table = 'accounts_profilelike'
        verbose_name = '点赞记录'
        verbose_name_plural = '点赞记录'
        unique_together = ('liker', 'profile')

    def __str__(self):
        return f'{self.liker.username} 点赞了 {self.profile.user.username}'


class PasswordResetToken(models.Model):
    """Password reset token kept for legacy reset flows."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='password_reset_token')
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'accounts_passwordresettoken'
        verbose_name = '密码重置令牌'
        verbose_name_plural = '密码重置令牌'
        indexes = [
            models.Index(fields=['expires_at'], name='knowledge_p_expires_e8717b_idx'),
        ]

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def get_remaining_time(self):
        if self.is_expired:
            return 0
        remaining = self.expires_at - timezone.now()
        return max(0, remaining.total_seconds() / 3600)

    def __str__(self):
        return f'{self.user.username} - {self.token[:8]}...'


class PasswordResetAttempt(models.Model):
    """Password reset attempt record used by reset rate limiting."""

    email = models.EmailField('邮箱', db_index=True)
    ip_address = models.GenericIPAddressField('IP地址', db_index=True)
    fingerprint = models.CharField('客户端指纹', max_length=64, db_index=True)
    attempted_at = models.DateTimeField('尝试时间', auto_now_add=True)
    is_successful = models.BooleanField('是否成功', default=False)
    user_agent = models.TextField('用户代理', blank=True)

    class Meta:
        db_table = 'accounts_passwordresetattempt'
        verbose_name = '密码重置尝试'
        verbose_name_plural = '密码重置尝试'
        indexes = [
            models.Index(fields=['email', 'attempted_at'], name='knowledge_p_email_704833_idx'),
            models.Index(fields=['ip_address', 'attempted_at'], name='knowledge_p_ip_addr_48fcac_idx'),
            models.Index(fields=['fingerprint', 'attempted_at'], name='knowledge_p_fingerp_113a05_idx'),
        ]

    def __str__(self):
        return f'{self.email} - {self.ip_address} - {self.attempted_at.strftime("%Y-%m-%d %H:%M")}'


class SecurityAuditLog(models.Model):
    """Durable audit trail for sensitive account operations."""

    ACTION_EMAIL_CHANGED = 'email_changed'
    ACTION_DEVICE_REVOKED = 'device_revoked'
    ACTION_CHOICES = [
        (ACTION_EMAIL_CHANGED, 'Email changed'),
        (ACTION_DEVICE_REVOKED, 'Login device revoked'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='security_audit_logs')
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_audit_actions',
    )
    action = models.CharField(max_length=64, choices=ACTION_CHOICES, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'accounts_securityauditlog'
        verbose_name = 'Security audit log'
        verbose_name_plural = 'Security audit logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='knowledge_p_user_id_b62207_idx'),
            models.Index(fields=['actor', '-created_at'], name='knowledge_p_actor_i_30257b_idx'),
            models.Index(fields=['action', '-created_at'], name='knowledge_p_action_1a1904_idx'),
        ]

    def __str__(self):
        actor = self.actor.username if self.actor_id else 'system'
        return f'{actor} -> {self.user.username}: {self.action}'


class AccessLog(models.Model):
    """Aggregated security access log for vault/login/IP events."""

    ACTION_CHOICES = [
        ('vault_fail', '保险柜失败'),
        ('login_fail', '登录失败'),
        ('ip_banned', 'IP封禁'),
        ('device_revoked', '设备信任撤销'),
    ]

    user_identifier = models.CharField('用户/账号', max_length=150, db_index=True)
    ip_address = models.GenericIPAddressField('来源IP', db_index=True)
    action = models.CharField('行为', max_length=20, choices=ACTION_CHOICES, default='vault_fail', db_index=True)
    count = models.IntegerField('聚合频次', default=1)
    details = models.TextField('详细信息', blank=True)
    created_at = models.DateTimeField('发生时间', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('最后更新', auto_now=True)

    class Meta:
        db_table = 'accounts_accesslog'
        verbose_name = '安全访问日志'
        verbose_name_plural = '安全访问日志'
        indexes = [
            models.Index(fields=['user_identifier', 'ip_address', 'action'], name='knowledge_p_user_id_1113d0_idx'),
        ]

    def __str__(self):
        return f'{self.user_identifier} - {self.ip_address} - {self.get_action_display()} x{self.count}'

    @classmethod
    def record_vault_fail(cls, user_identifier, ip_address, details=None):
        cutoff = timezone.now() - timedelta(hours=24)
        existing = cls.objects.filter(
            user_identifier=user_identifier,
            ip_address=ip_address,
            action='vault_fail',
            created_at__gte=cutoff,
        ).first()

        if existing:
            existing.count += 1
            if details:
                existing.details = details
            existing.save(update_fields=['count', 'details', 'updated_at'])
            return existing

        return cls.objects.create(
            user_identifier=user_identifier,
            ip_address=ip_address,
            action='vault_fail',
            count=1,
            details=details or '',
        )

    @classmethod
    def get_ip_fail_count(cls, ip_address, hours=24):
        cutoff = timezone.now() - timedelta(hours=hours)
        result = cls.objects.filter(
            ip_address=ip_address,
            action='vault_fail',
            created_at__gte=cutoff,
        ).aggregate(total=Sum('count'))
        return result['total'] or 0


class LoginDevice(models.Model):
    """Login device record used for login notifications and remote logout."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_devices', verbose_name='用户')
    device_fingerprint = models.CharField('设备指纹', max_length=64, db_index=True)
    ip_address = models.GenericIPAddressField('IP地址', db_index=True)
    ip_location = models.CharField('IP归属地', max_length=200, blank=True)
    user_agent = models.TextField('用户代理')
    device_info = models.CharField('设备信息', max_length=200)
    first_login_at = models.DateTimeField('首次登录时间', auto_now_add=True)
    last_login_at = models.DateTimeField('最后登录时间', auto_now=True)
    login_count = models.IntegerField('登录次数', default=1)
    is_trusted = models.BooleanField('是否信任', default=False)
    trusted_at = models.DateTimeField('信任时间', null=True, blank=True)
    session_key = models.CharField('Session key', max_length=40, blank=True, db_index=True)
    is_active = models.BooleanField('Active session', default=True, db_index=True)
    revoked_at = models.DateTimeField('Revoked at', null=True, blank=True)
    revoked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_login_devices',
        verbose_name='Revoked by',
    )

    class Meta:
        db_table = 'accounts_logindevice'
        verbose_name = '登录设备'
        verbose_name_plural = '登录设备'
        unique_together = ('user', 'device_fingerprint')
        indexes = [
            models.Index(fields=['user', 'last_login_at'], name='knowledge_p_user_id_967b54_idx'),
            models.Index(fields=['user', 'is_active'], name='knowledge_p_user_id_4c985c_idx'),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.device_info} - {self.ip_location}'


class LoginNotification(models.Model):
    """Login notification record used to prevent duplicate notification bursts."""

    REASON_CHOICES = [
        ('new_device', '新设备'),
        ('new_location', '新位置'),
        ('suspicious', '可疑登录'),
        ('first_login', '首次登录'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_notifications', verbose_name='用户')
    device = models.ForeignKey(LoginDevice, on_delete=models.CASCADE, related_name='notifications', verbose_name='设备')
    ip_address = models.GenericIPAddressField('IP地址')
    reason = models.CharField('通知原因', max_length=20, choices=REASON_CHOICES)
    sent_at = models.DateTimeField('发送时间', auto_now_add=True)
    email_sent = models.BooleanField('邮件已发送', default=False)

    class Meta:
        db_table = 'accounts_loginnotification'
        verbose_name = '登录通知记录'
        verbose_name_plural = '登录通知记录'
        indexes = [
            models.Index(fields=['user', 'sent_at'], name='knowledge_p_user_id_a9bb4b_idx'),
            models.Index(fields=['device', 'sent_at'], name='knowledge_p_device__6b0641_idx'),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.get_reason_display()} - {self.sent_at.strftime("%Y-%m-%d %H:%M")}'


class TrustedDevice(models.Model):
    """Trusted device token for 2FA bypass with a rolling 30-day expiry."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trusted_devices', verbose_name='用户')
    device_token = models.CharField('加密令牌', max_length=128, unique=True, db_index=True)
    user_agent = models.CharField('UA标识', max_length=500)
    ip_address = models.GenericIPAddressField('首次IP')
    last_login_ip = models.GenericIPAddressField('最近IP', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    last_used_at = models.DateTimeField('最后使用', auto_now=True)
    expires_at = models.DateTimeField('过期时间', db_index=True)
    fail_count = models.IntegerField('设备级失败计数', default=0)
    is_revoked = models.BooleanField('已撤销', default=False, db_index=True)
    revoked_reason = models.CharField('撤销原因', max_length=100, blank=True)

    class Meta:
        db_table = 'accounts_trusteddevice'
        verbose_name = '信任设备'
        verbose_name_plural = '信任设备'
        indexes = [
            models.Index(fields=['user', 'is_revoked'], name='knowledge_p_user_id_91fd9a_idx'),
        ]

    def __str__(self):
        status = '已撤销' if self.is_revoked else ('已过期' if not self.is_valid() else '有效')
        return f'{self.user.username} - {self.user_agent[:50]}... - {status}'

    def is_valid(self):
        return not self.is_revoked and self.expires_at > timezone.now()

    def renew(self, ip):
        self.last_login_ip = ip
        self.expires_at = timezone.now() + timedelta(days=30)
        self.save(update_fields=['last_login_ip', 'last_used_at', 'expires_at'])

    def increment_fail(self):
        self.fail_count += 1
        if self.fail_count >= 3:
            self.is_revoked = True
            self.revoked_reason = f'连续{self.fail_count}次验证失败'
            AccessLog.objects.create(
                user_identifier=self.user.username,
                ip_address=self.last_login_ip or self.ip_address,
                action='device_revoked',
                details=f'设备令牌: {self.device_token[:16]}..., 原因: {self.revoked_reason}',
            )
        self.save(update_fields=['fail_count', 'is_revoked', 'revoked_reason'])
        return self.is_revoked

    @classmethod
    def create_device(cls, user, request):
        import secrets

        token = secrets.token_urlsafe(64)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')[:500]
        ip = get_client_ip(request)

        return cls.objects.create(
            user=user,
            device_token=token,
            user_agent=user_agent,
            ip_address=ip,
            expires_at=timezone.now() + timedelta(days=30),
        )

    @classmethod
    def get_by_token(cls, token):
        try:
            device = cls.objects.select_related('user').get(device_token=token)
            if device.is_valid():
                return device
            return None
        except cls.DoesNotExist:
            return None
