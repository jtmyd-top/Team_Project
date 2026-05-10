import random as pyrandom
import logging

from bs4 import BeautifulSoup
import jieba.analyse
from django.db import models
import uuid
from django.contrib.auth.models import User
from django_ckeditor_5.fields import CKEditor5Field
from django.db.models.signals import post_save
from django.dispatch import receiver
import nh3
import os
import hashlib, io, re, requests, colorsys
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from django.utils.safestring import mark_safe
from django.core.validators import MaxLengthValidator
from io import BytesIO
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)
# ---------------- 标签 ----------------
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="标签名")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "标签"
        verbose_name_plural = "标签"


# ---------------- 文件夹 ----------------
class Folder(models.Model):
    """文件夹模型，用于组织笔记"""
    name = models.CharField(max_length=100, verbose_name="文件夹名称")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='folders', verbose_name="所有者")
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="父文件夹"
    )
    order = models.IntegerField(default=0, verbose_name="排序顺序")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    # 【新增】回收站相关字段
    is_trashed = models.BooleanField(default=False, verbose_name="已删除")
    trashed_at = models.DateTimeField(null=True, blank=True, verbose_name="删除时间")
    original_parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='restored_children',
        verbose_name="删除前的父文件夹"
    )

    class Meta:
        verbose_name = "文件夹"
        verbose_name_plural = "文件夹"
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['owner', 'parent']),
            models.Index(fields=['is_trashed']),  # 【新增】回收站索引
        ]

    def __str__(self):
        return self.name

    def get_ancestors(self):
        """获取所有祖先文件夹（用于面包屑导航）"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors

    def get_descendants(self):
        """获取所有后代文件夹"""
        descendants = []
        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants

    def get_notes_count(self):
        """获取文件夹内的笔记数量（包括子文件夹）"""
        count = self.notes_in_folder.filter(is_trashed=False).count()
        for child in self.children.all():
            count += child.get_notes_count()
        return count

    # 【新增】回收站相关方法
    def move_to_trash(self):
        """将文件夹移入回收站"""
        from django.utils import timezone
        self.is_trashed = True
        self.trashed_at = timezone.now()
        # 保存原始父文件夹，用于恢复
        if self.parent:
            self.original_parent = self.parent
        self.save(update_fields=['is_trashed', 'trashed_at', 'original_parent'])

    def restore_from_trash(self):
        """从回收站恢复文件夹"""
        self.is_trashed = False
        self.trashed_at = None
        # 恢复到原始父文件夹
        if self.original_parent:
            self.parent = self.original_parent
        self.save(update_fields=['is_trashed', 'trashed_at', 'parent'])

    def get_trashed_children_count(self):
        """获取回收站中该文件夹包含的笔记和子文件夹数量"""
        notes_count = self.notes_in_folder.filter(is_trashed=True).count()
        folders_count = self.children.filter(is_trashed=True).count()
        return notes_count + folders_count


# ---------------- 笔记 ----------------
class Note(models.Model):
    title = models.CharField(max_length=255, verbose_name="笔记标题")
    content = CKEditor5Field(verbose_name="笔记内容", null=True, blank=True, config_name='full')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes', verbose_name="作者")
    folder = models.ForeignKey(
        Folder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notes_in_folder',
        verbose_name="所属文件夹"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="最后修改时间")
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_notes',
        verbose_name="最后修改者"
    )
    is_public = models.BooleanField(default=False, verbose_name="是否公开")
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    views = models.PositiveIntegerField(default=0, verbose_name="查看次数")
    tags = models.ManyToManyField(Tag, blank=True, related_name='notes', verbose_name="标签")

    # 目录数据（JSON 格式存储）
    toc = models.JSONField(default=list, blank=True, verbose_name="目录结构")

    # 状态标记
    is_trashed = models.BooleanField(default=False, verbose_name="已删除")
    is_favorited = models.BooleanField(default=False, verbose_name="已收藏")
    is_secret = models.BooleanField(default=False, verbose_name="保密笔记", help_text="标记为保密的笔记需要2FA验证才能访问")
    trashed_at = models.DateTimeField(null=True, blank=True, verbose_name="删除时间")

    def has_permission(self, user):
        if self.is_public:
            return True
        return self.author == user

    def save(self, *args, **kwargs):
        if self.content:
            allowed_tags = {
                'p', 'img', 'b', 'i', 'u', 'strong', 'em', 'strike', 'a', 'h1', 'h2', 'h3',
                'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'br', 'hr',
                'table', 'thead', 'tbody', 'tr', 'td', 'th', 'span', 'div', 'section',
                'article', 'header', 'footer', 'nav', 'aside', 'figure', 'figcaption',
                'details', 'summary'
            }
            # 允许标题有 id 属性（用于目录跳转）
            allowed_attributes = {
                'a': {'href', 'title', 'target'},
                'img': {'alt', 'title', 'width', 'height', 'src'},
                '*': {'class', 'id'},  # 添加 id 属性
            }
            self.content = nh3.clean(
                self.content,
                tags=allowed_tags,
                attributes=allowed_attributes,
                strip_comments=True,
                url_schemes={'http', 'https'}
            )

            # 提取目录并注入 ID 到标题
            from knowledge_project.utils.toc_extractor import extract_toc_from_html
            toc_list, updated_html = extract_toc_from_html(self.content)
            self.toc = toc_list
            self.content = updated_html

        super().save(*args, **kwargs)

    def __str__(self):
        return (self.title[:50] + "…") if len(self.title) > 50 else self.title

    class Meta:
        verbose_name, verbose_name_plural = "知识笔记", "知识笔记"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['author']),
            models.Index(fields=['folder']),
            models.Index(fields=['is_trashed']),
            models.Index(fields=['is_favorited']),
            models.Index(fields=['is_secret']),
        ]

    def move_to_trash(self):
        """移动到回收站"""
        from django.utils import timezone
        self.is_trashed = True
        self.trashed_at = timezone.now()
        self.save(update_fields=['is_trashed', 'trashed_at'])

    def restore_from_trash(self):
        """从回收站恢复"""
        self.is_trashed = False
        self.trashed_at = None
        self.save(update_fields=['is_trashed', 'trashed_at'])

    def move_to_inbox(self):
        """移动到收件箱（移除文件夹关联）"""
        self.folder = None
        self.save(update_fields=['folder'])


# ---------------- 资源 ----------------
def user_directory_path(instance, filename):
    if instance.uploader and instance.uploader.id:
        return f'user_{instance.uploader.id}/{filename}'
    return f'unknown_user/{filename}'


class Asset(models.Model):
    ASSET_TYPE_CHOICES = [
        ('file', '普通文件'), ('image', '图片'), ('code', '代码片段'), ('doc', '文档'),
    ]

    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="uploaded_assets",
                                 verbose_name="上传者")
    name = models.CharField(max_length=255, verbose_name="文件名/资源名", blank=True)
    file = models.FileField(upload_to=user_directory_path, verbose_name="上传文件", null=True)
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPE_CHOICES, default='file', verbose_name="资源类型")
    description = models.TextField(blank=True, verbose_name="描述")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")
    image_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True, verbose_name="文件哈希值")

    def get_protected_url(self):
        if self.file:
            return f"/protected_uploads/{self.file.name}"
        return ""

    def __str__(self):
        return self.name or (self.file.name if self.file else "未命名文件")

    class Meta:
        verbose_name = "个人资产"
        verbose_name_plural = "个人资产"
        ordering = ['-uploaded_at']
        unique_together = ('uploader', 'image_hash')


# ---------------- 用户资料 + 头像 ----------------
def user_avatar_path(instance, filename):
    return f'user_{instance.user.id}/avatar/{filename}'

def default_theme_settings():
    """为 JSONField 提供默认主题设置的可调用函数"""
    return {
        'mode': 'light',
        'primary_color': '#409EFF',
        'font_size': 14,
        'compact_mode': False,
        'animations': True,
        'dark_mode': False  # 保留兼容性
    }

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="关联用户")
    activation_code = models.CharField(max_length=8, blank=True, null=True, unique=True, verbose_name="激活码")
    code_created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    avatar = models.ImageField(upload_to=user_avatar_path, null=True, blank=True, verbose_name="头像")
    avatar_source = models.CharField(max_length=32, blank=True, verbose_name="头像来源")
    THEME_CHOICES = [
        ('light', '浅色主题'),
        ('dark', '深色主题'),
        ('system', '系统默认')
    ]

    # 新增个性化字段
    bio = models.TextField(
        max_length=160,
        blank=True,
        validators=[MaxLengthValidator(160)],
        verbose_name="个人简介"
    )
    banner_image = models.FileField(
        upload_to=user_avatar_path,  # 复用头像路径函数
        null=True,
        blank=True,
        verbose_name="主页横幅"
    )
    theme = models.JSONField(
        default=default_theme_settings,
        verbose_name="主题设置",
        help_text="存储用户界面主题配置"
    )
    layout_mode = models.CharField(
        max_length=20,
        choices=[('default', '默认布局'), ('compact', '紧凑布局'), ('wide', '宽屏布局')],
        default='default',
        verbose_name="界面布局"
    )
    last_theme_update = models.DateTimeField(
        auto_now=True,
        verbose_name="最后主题更新时间",
        help_text="记录用户最后修改主题的时间"
    )
    allow_rich_bio = models.BooleanField(
        default=False,
        verbose_name="允许富文本简介"
    )

    # 点赞功能字段
    likes_count = models.IntegerField(
        default=0,
        verbose_name="获赞数"
    )

    last_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="最后更新时间"
    )

    # ==================== 两因素认证（2FA）相关字段 ====================
    two_fa_enabled = models.BooleanField(
        default=False,
        verbose_name="启用两因素认证"
    )
    two_fa_method = models.CharField(
        max_length=10,
        choices=[('totp', 'TOTP验证器'), ('email', '邮箱验证')],
        default='totp',
        blank=True,
        verbose_name="2FA验证方式"
    )
    totp_secret = models.CharField(
        max_length=32,
        blank=True,
        verbose_name="TOTP密钥",
        help_text="用于 Google Authenticator 等 TOTP 应用的密钥"
    )
    backup_codes = models.JSONField(
        default=list,
        blank=True,
        verbose_name="备用验证码",
        help_text="用于 TOTP 设备丢失时的一次性备用码"
    )

    # ==================== 邮件通知偏好设置 ====================
    notify_login = models.BooleanField(
        default=True,
        verbose_name="登录通知",
        help_text="账户登录时发送邮件通知"
    )
    notify_password_change = models.BooleanField(
        default=True,
        verbose_name="密码修改通知",
        help_text="密码修改时发送邮件通知"
    )
    notify_password_reset = models.BooleanField(
        default=True,
        verbose_name="密码重置通知",
        help_text="密码重置时发送邮件通知"
    )
    notify_note_activities = models.BooleanField(
        default=False,
        verbose_name="笔记活动通知",
        help_text="笔记创建/修改/删除时发送邮件通知"
    )
    notify_profile_likes = models.BooleanField(
        default=True,
        verbose_name="点赞通知",
        help_text="个人空间或作品被点赞时发送邮件通知"
    )

    # ==================== 账户可发现性（防用户枚举） ====================
    discoverable_by_username = models.BooleanField(
        default=False,
        verbose_name="允许通过用户名搜索到我",
        help_text="关闭后即使输入完整用户名也无法被搜索到"
    )
    discoverable_by_email = models.BooleanField(
        default=False,
        verbose_name="允许通过邮箱搜索到我",
        help_text="关闭后即使输入完整邮箱也无法被搜索到"
    )
    search_code = models.CharField(
        max_length=12,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="公开搜索短码",
        help_text="8 位随机字符串，用户可主动分享给朋友用于添加"
    )

    # ==================== 保险柜加密相关字段 ====================
    encrypted_vault_key = models.TextField(
        null=True,
        blank=True,
        verbose_name="加密保险柜密钥",
        help_text="Base64编码的AES加密DEK，用KEK加密"
    )
    vault_key_iv = models.TextField(
        null=True,
        blank=True,
        verbose_name="保险柜密钥IV",
        help_text="加密DEK时的初始化向量（Base64编码）"
    )
    vault_initialized = models.BooleanField(
        default=False,
        verbose_name="保险柜已初始化",
        help_text="用户是否已初始化保险柜"
    )

    def clean_bio(self):
        """净化用户输入的富文本内容"""
        from nh3 import clean
        if self.allow_rich_bio:
            return clean(
                self.bio,
                tags={'a', 'b', 'i', 'strong', 'em', 'br', 'p'},
                attributes={'a': {'href', 'title', 'target'}},
                url_schemes={'http', 'https'}
            )
        return self.escape_markup(self.bio)

    @staticmethod
    def escape_markup(text):
        """转义纯文本中的HTML标记"""
        return mark_safe(text).replace('<', '&lt;').replace('>', '&gt;')

    def save(self, *args, **kwargs):
        self.bio = self.clean_bio()
        super().save(*args, **kwargs)
        self.process_banner_image()  # 处理横幅图片

    def process_banner_image(self):
        """处理横幅图片的压缩和裁剪（仅处理图片，跳过视频）"""
        if self.banner_image:
            try:
                # 检查文件类型，只处理图片
                file_path = self.banner_image.path
                file_ext = os.path.splitext(file_path)[1].lower()

                # 如果是视频文件，跳过处理
                if file_ext in ['.mp4', '.webm', '.avi', '.mov', '.mkv']:
                    logger.info(f"跳过视频文件处理: {file_path}")
                    return

                img = Image.open(file_path)

                # 转换为RGB模式
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # 限制尺寸最大为2560x600
                img.thumbnail((2560, 600))

                # 质量压缩
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=85, optimize=True)

                # 保存回文件
                self.banner_image.save(
                    os.path.basename(self.banner_image.name),
                    ContentFile(buffer.getvalue()),
                    save=False
                )
            except Exception as e:
                logger.error(f"处理横幅图片失败: {str(e)}")
    def __str__(self):
        return f'{self.user.username} Profile'

    @property
    def avatar_url(self):
        if self.avatar:
            try:
                return self.avatar.url
            except ValueError:
                pass
        return "/static/img/default-avatar.png"
    class Meta:
        verbose_name = "用户资料"
        verbose_name_plural = "用户资料"


# ---------------- 点赞记录模型 ----------------
class ProfileLike(models.Model):
    """
    记录用户之间的点赞关系
    后续可以扩展为通用点赞模型，支持对笔记的点赞
    """
    liker = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='given_likes',
        verbose_name="点赞者"
    )
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='received_likes',
        verbose_name="被点赞的用户资料"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="点赞时间")

    class Meta:
        verbose_name = "点赞记录"
        verbose_name_plural = "点赞记录"
        unique_together = ('liker', 'profile')  # 确保一个用户只能点赞同一个资料一次
        indexes = [
            models.Index(fields=['liker', 'profile']),
        ]

    def __str__(self):
        return f"{self.liker.username} 点赞了 {self.profile.user.username}"


class PasswordResetToken(models.Model):
    """密码重置令牌模型"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='password_reset_token')
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = '密码重置令牌'
        verbose_name_plural = '密码重置令牌'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]

    @property
    def is_expired(self):
        """检查令牌是否已过期"""
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def save(self, *args, **kwargs):
        # 创建时设置过期时间为24小时后
        if not self.pk:
            from django.utils import timezone
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def get_remaining_time(self):
        """获取剩余有效时间（小时）"""
        from django.utils import timezone
        from datetime import timedelta
        if self.is_expired:
            return 0
        remaining = self.expires_at - timezone.now()
        return max(0, remaining.total_seconds() / 3600)

    def __str__(self):
        return f'{self.user.username} - {self.token[:8]}...'


class PasswordResetAttempt(models.Model):
    """密码重置尝试记录，用于频率限制"""
    email = models.EmailField('邮箱', db_index=True)
    ip_address = models.GenericIPAddressField('IP地址', db_index=True)
    fingerprint = models.CharField('客户端指纹', max_length=64, db_index=True)
    attempted_at = models.DateTimeField('尝试时间', auto_now_add=True)
    is_successful = models.BooleanField('是否成功', default=False)
    user_agent = models.TextField('用户代理', blank=True)

    class Meta:
        verbose_name = '密码重置尝试'
        verbose_name_plural = '密码重置尝试'
        indexes = [
            models.Index(fields=['email', 'attempted_at']),
            models.Index(fields=['ip_address', 'attempted_at']),
            models.Index(fields=['fingerprint', 'attempted_at']),
        ]

    def __str__(self):
        return f'{self.email} - {self.ip_address} - {self.attempted_at.strftime("%Y-%m-%d %H:%M")}'




class LoginDevice(models.Model):
    """
    登录设备记录模型 - 用于智能登录通知
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_devices', verbose_name='用户')
    device_fingerprint = models.CharField('设备指纹', max_length=64, db_index=True)
    ip_address = models.GenericIPAddressField('IP地址', db_index=True)
    ip_location = models.CharField('IP归属地', max_length=200, blank=True)
    user_agent = models.TextField('用户代理')
    device_info = models.CharField('设备信息', max_length=200)
    
    # 首次和最后登录时间
    first_login_at = models.DateTimeField('首次登录时间', auto_now_add=True)
    last_login_at = models.DateTimeField('最后登录时间', auto_now=True)
    login_count = models.IntegerField('登录次数', default=1)
    
    # 信任状态
    is_trusted = models.BooleanField('是否信任', default=False)
    trusted_at = models.DateTimeField('信任时间', null=True, blank=True)
    
    class Meta:
        verbose_name = '登录设备'
        verbose_name_plural = '登录设备'
        unique_together = ('user', 'device_fingerprint')
        indexes = [
            models.Index(fields=['user', 'device_fingerprint']),
            models.Index(fields=['user', 'last_login_at']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.device_info} - {self.ip_location}'


class LoginNotification(models.Model):
    """
    登录通知记录 - 防止通知滥发
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_notifications', verbose_name='用户')
    device = models.ForeignKey(LoginDevice, on_delete=models.CASCADE, related_name='notifications', verbose_name='设备')
    ip_address = models.GenericIPAddressField('IP地址')
    
    # 通知原因
    REASON_CHOICES = [
        ('new_device', '新设备'),
        ('new_location', '新位置'),
        ('suspicious', '可疑登录'),
        ('first_login', '首次登录'),
    ]
    reason = models.CharField('通知原因', max_length=20, choices=REASON_CHOICES)
    
    # 通知时间
    sent_at = models.DateTimeField('发送时间', auto_now_add=True)
    
    # 邮件发送状态
    email_sent = models.BooleanField('邮件已发送', default=False)
    
    class Meta:
        verbose_name = '登录通知记录'
        verbose_name_plural = '登录通知记录'
        indexes = [
            models.Index(fields=['user', 'sent_at']),
            models.Index(fields=['device', 'sent_at']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.get_reason_display()} - {self.sent_at.strftime("%Y-%m-%d %H:%M")}'


class AccessLog(models.Model):
    """安全访问日志 - 持久化保密柜失败记录，按用户+IP聚合24小时"""
    ACTION_CHOICES = [
        ('vault_fail', '保密柜失败'),
        ('login_fail', '登录失败'),
        ('ip_banned', 'IP封禁'),
        ('device_revoked', '设备信任撤销'),
    ]

    user_identifier = models.CharField("用户/账号", max_length=150, db_index=True)
    ip_address = models.GenericIPAddressField("来源IP", db_index=True)
    action = models.CharField("行为", max_length=20, choices=ACTION_CHOICES, default='vault_fail', db_index=True)
    count = models.IntegerField("聚合频次", default=1)
    details = models.TextField("详细信息", blank=True)
    created_at = models.DateTimeField("发生时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("最后更新", auto_now=True)

    class Meta:
        verbose_name = '安全访问日志'
        verbose_name_plural = '安全访问日志'
        indexes = [
            models.Index(fields=['user_identifier', 'ip_address', 'action']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.user_identifier} - {self.ip_address} - {self.get_action_display()} x{self.count}'

    @classmethod
    def record_vault_fail(cls, user_identifier, ip_address, details=None):
        """记录失败，自动聚合24小时内同用户+IP"""
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(hours=24)

        # 查找24小时内同用户+IP的现有记录
        existing = cls.objects.filter(
            user_identifier=user_identifier,
            ip_address=ip_address,
            action='vault_fail',
            created_at__gte=cutoff
        ).first()

        if existing:
            existing.count += 1
            if details:
                existing.details = details
            existing.save(update_fields=['count', 'details', 'updated_at'])
            return existing
        else:
            return cls.objects.create(
                user_identifier=user_identifier,
                ip_address=ip_address,
                action='vault_fail',
                count=1,
                details=details or ''
            )

    @classmethod
    def get_ip_fail_count(cls, ip_address, hours=24):
        """获取指定IP在时间窗口内的总失败次数"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum

        cutoff = timezone.now() - timedelta(hours=hours)
        result = cls.objects.filter(
            ip_address=ip_address,
            action='vault_fail',
            created_at__gte=cutoff
        ).aggregate(total=Sum('count'))

        return result['total'] or 0


class TrustedDevice(models.Model):
    """信任设备 - 管理免2FA的设备令牌，30天滚动续期"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trusted_devices', verbose_name='用户')
    device_token = models.CharField("加密令牌", max_length=128, unique=True, db_index=True)
    user_agent = models.CharField("UA标识", max_length=500)
    ip_address = models.GenericIPAddressField("首次IP")
    last_login_ip = models.GenericIPAddressField("最近IP", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    last_used_at = models.DateTimeField("最后使用", auto_now=True)
    expires_at = models.DateTimeField("过期时间", db_index=True)
    fail_count = models.IntegerField("设备级失败计数", default=0)
    is_revoked = models.BooleanField("已撤销", default=False, db_index=True)
    revoked_reason = models.CharField("撤销原因", max_length=100, blank=True)

    class Meta:
        verbose_name = '信任设备'
        verbose_name_plural = '信任设备'
        indexes = [
            models.Index(fields=['user', 'is_revoked']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        status = '已撤销' if self.is_revoked else ('已过期' if not self.is_valid() else '有效')
        return f'{self.user.username} - {self.user_agent[:50]}... - {status}'

    def is_valid(self):
        """检查设备是否有效（未撤销且未过期）"""
        from django.utils import timezone
        return not self.is_revoked and self.expires_at > timezone.now()

    def renew(self, ip):
        """滚动续期30天"""
        from django.utils import timezone
        from datetime import timedelta

        self.last_login_ip = ip
        self.expires_at = timezone.now() + timedelta(days=30)
        self.save(update_fields=['last_login_ip', 'last_used_at', 'expires_at'])

    def increment_fail(self):
        """增加失败计数，>=3时自动撤销"""
        self.fail_count += 1
        if self.fail_count >= 3:
            self.is_revoked = True
            self.revoked_reason = f'连续{self.fail_count}次验证失败'
            # 记录撤销日志
            AccessLog.objects.create(
                user_identifier=self.user.username,
                ip_address=self.last_login_ip or self.ip_address,
                action='device_revoked',
                details=f'设备令牌: {self.device_token[:16]}..., 原因: {self.revoked_reason}'
            )
        self.save(update_fields=['fail_count', 'is_revoked', 'revoked_reason'])
        return self.is_revoked

    @classmethod
    def create_device(cls, user, request):
        """创建新信任设备"""
        import secrets
        from django.utils import timezone
        from datetime import timedelta

        token = secrets.token_urlsafe(64)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')[:500]
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '127.0.0.1'))
        if ',' in ip:
            ip = ip.split(',')[0].strip()

        return cls.objects.create(
            user=user,
            device_token=token,
            user_agent=user_agent,
            ip_address=ip,
            expires_at=timezone.now() + timedelta(days=30)
        )

    @classmethod
    def get_by_token(cls, token):
        """根据token获取有效设备"""
        try:
            device = cls.objects.select_related('user').get(device_token=token)
            if device.is_valid():
                return device
            return None
        except cls.DoesNotExist:
            return None


# ---------------- 头像抓取逻辑 ----------------
def _http_get(url):
    try:
        r = requests.get(url, timeout=4, stream=True)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            return r.content
    except requests.RequestException:
        return None

def _md5(email): return hashlib.md5(email.strip().lower().encode()).hexdigest()

def fetch_avatar(user):
    email = (user.email or "").strip().lower()
    img_bytes, source = None, "default"

    if email:
        # 1. Libravatar
        url = f"https://seccdn.libravatar.org/avatar/{_md5(email)}?s=256&d=404"
        img_bytes = _http_get(url)
        if img_bytes: source = "libravatar"

        # 2. Gravatar
        if not img_bytes:
            url = f"https://www.gravatar.com/avatar/{_md5(email)}?s=256&d=404"
            img_bytes = _http_get(url)
            if img_bytes: source = "gravatar"

        # 3. QQ 邮箱头像
        if not img_bytes and email.endswith("@qq.com"):
            qq = email.split("@")[0]
            url = f"https://q1.qlogo.cn/g?b=qq&nk={qq}&s=100"
            img_bytes = _http_get(url)
            if img_bytes: source = "qq"

    # 4. 兜底：纯色首字母
    if not img_bytes:
        img_bytes = generate_initial_avatar(user.username or email)
        source = "default"

    if img_bytes:
        filename = f"avatar_{source}.png"
        user.profile.avatar.save(filename, ContentFile(img_bytes), save=True)
        user.profile.avatar_source = source
        user.profile.save(update_fields=["avatar", "avatar_source"])

from io import BytesIO

def generate_initial_avatar(text, size=128):
    img = Image.new("RGB", (size, size),
                    (pyrandom.randint(64, 192),
                     pyrandom.randint(64, 192),
                     pyrandom.randint(64, 192)))
    draw = ImageDraw.Draw(img)
    font_path = os.path.join(settings.BASE_DIR, "knowledge_project", "utils", "kumo.ttf")
    font = ImageFont.truetype(font_path, size // 2)

    ch = text[0].upper() if text else "?"
    bbox = draw.textbbox((0, 0), ch, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, (size - th) / 2), ch, font=font, fill=(255, 255, 255))

    # 返回字节流而不是 Image 对象，避免 ContentFile 出错
    from io import BytesIO
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


# ---------------- Signals ----------------
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile = Profile.objects.create(user=instance)
        fetch_avatar(instance)  # 自动拉取头像

        # 生成 8 位搜索短码（若未生成）
        try:
            import secrets, string
            if not profile.search_code:
                alphabet = string.ascii_uppercase + string.digits
                for _ in range(5):
                    code = ''.join(secrets.choice(alphabet) for _ in range(8))
                    if not Profile.objects.filter(search_code=code).exists():
                        profile.search_code = code
                        break
        except Exception as e:
            logger.error(f"[Profile] 生成 search_code 失败: {e}")

        # ==================== 【新增】自动初始化保密柜 ====================
        try:
            from knowledge_project.utils.vault_crypto import VaultEncryption

            # 生成随机 DEK（数据加密密钥）
            dek = VaultEncryption.generate_dek()

            # 用 KEK（密钥加密密钥）加密 DEK
            encrypted_dek_b64, iv_b64 = VaultEncryption.encrypt_dek(dek)

            # 保存到 Profile
            profile.encrypted_vault_key = encrypted_dek_b64
            profile.vault_key_iv = iv_b64
            profile.vault_initialized = True
            profile.save(update_fields=['encrypted_vault_key', 'vault_key_iv', 'vault_initialized'])

            logger.info(f"[Vault] Auto-initialized vault for new user: {instance.username}")
        except Exception as e:
            logger.error(f"[Vault] Failed to auto-initialize vault for user {instance.username}: {e}")
            # 继续执行，vault 初始化失败不应该阻止用户创建


# ---------------- 笔记评论模型 ----------------
class NoteComment(models.Model):
    """公开笔记的讨论评论"""
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name="所属笔记"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='note_comments',
        verbose_name="评论者"
    )
    content = models.TextField(max_length=2000, verbose_name="评论内容")
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name="回复的评论"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="评论时间")

    class Meta:
        verbose_name = "笔记评论"
        verbose_name_plural = "笔记评论"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.username} 评论了 《{self.note.title}》"


# ============ 笔记浏览历史模型 ============
class NoteHistory(models.Model):
    """用户浏览笔记的历史记录"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='note_history',
        verbose_name="用户"
    )
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name='view_history',
        verbose_name="笔记"
    )
    viewed_at = models.DateTimeField(auto_now=True, verbose_name="浏览时间")

    class Meta:
        verbose_name = "笔记浏览历史"
        verbose_name_plural = "笔记浏览历史"
        ordering = ['-viewed_at']
        unique_together = ('user', 'note')
        indexes = [
            models.Index(fields=['user', '-viewed_at']),
        ]

    def __str__(self):
        return f"{self.user.username} 浏览了 《{self.note.title}》"


@receiver(post_save, sender=Note)
def auto_generate_tags_for_note(sender, instance, created, **kwargs):
    if not created or not instance.content:
        return
    soup = BeautifulSoup(instance.content, 'html.parser')
    text = soup.get_text()
    if len(text) < 20:
        return
    keywords = jieba.analyse.extract_tags(text, topK=5, withWeight=False, allowPOS=('n','nr','ns','nz','v'))
    for keyword in keywords:
        tag, _ = Tag.objects.get_or_create(name=keyword)
        instance.tags.add(tag)


# ============ 私信功能模型 ============
def message_attachment_path(instance, filename):
    user_id = instance.uploader_id or 'unknown'
    _, ext = os.path.splitext(filename or '')
    safe_ext = ext[:16] if ext else ''
    return f'messages/user_{user_id}/{uuid.uuid4().hex}{safe_ext}'


class Message(models.Model):
    """用户之间的私信"""
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name="发送者"
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_messages',
        verbose_name="接收者"
    )
    content = models.TextField(verbose_name="消息内容")
    searchable_text = models.TextField(blank=True, default='', verbose_name="搜索文本")
    is_read = models.BooleanField(default=False, verbose_name="已读")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="发送时间")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="读取时间")
    # 软删除：各自对自己隐藏
    deleted_for_sender = models.BooleanField(default=False, verbose_name="发送者已删除")
    deleted_for_recipient = models.BooleanField(default=False, verbose_name="接收者已删除")
    # 撤回：双方均不可见（发送者 2 分钟内可撤回 / 阅后即焚触发）
    is_recalled = models.BooleanField(default=False, verbose_name="已撤回")
    recalled_at = models.DateTimeField(null=True, blank=True, verbose_name="撤回时间")
    was_reported = models.BooleanField(default=False, verbose_name="是否曾被举报")
    pending_purge_at = models.DateTimeField(null=True, blank=True, verbose_name="计划物理清理时间")
    purged_at = models.DateTimeField(null=True, blank=True, verbose_name="实际物理清理时间")

    class Meta:
        verbose_name = "私信"
        verbose_name_plural = "私信"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender', 'recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['pending_purge_at']),
            models.Index(fields=['was_reported']),
        ]

    def __str__(self):
        return f"{self.sender.username} → {self.recipient.username}"

    def visible_to(self, user):
        """判断该消息对给定用户是否可见"""
        if self.is_recalled:
            return False
        if user.id == self.sender_id and self.deleted_for_sender:
            return False
        if user.id == self.recipient_id and self.deleted_for_recipient:
            return False
        return True


class MessageAttachment(models.Model):
    """私信附件，先上传为草稿，发送消息时绑定到 Message。"""
    ATTACHMENT_TYPE_CHOICES = [
        ('image', '图片'),
        ('audio', '语音'),
        ('video', '视频'),
        ('file', '文件'),
    ]

    uploader = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='message_attachments',
        verbose_name="上传者",
    )
    message = models.ForeignKey(
        Message,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name="关联私信",
    )
    file = models.FileField(upload_to=message_attachment_path, verbose_name="附件文件")
    original_name = models.CharField(max_length=255, verbose_name="原始文件名")
    attachment_type = models.CharField(
        max_length=10,
        choices=ATTACHMENT_TYPE_CHOICES,
        default='file',
        verbose_name="附件类型",
    )
    mime_type = models.CharField(max_length=120, blank=True, verbose_name="MIME 类型")
    size = models.PositiveIntegerField(default=0, verbose_name="文件大小")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")
    was_reported = models.BooleanField(default=False, verbose_name="是否曾被举报")

    class Meta:
        verbose_name = "私信附件"
        verbose_name_plural = "私信附件"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['uploader', 'message']),
            models.Index(fields=['message', 'created_at']),
            models.Index(fields=['was_reported']),
        ]

    def __str__(self):
        return self.original_name or self.file.name


class AttachmentReport(models.Model):
    """私信附件举报工单。只有待处理工单会临时打开管理员审查权限。"""
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('removed', '已违规删除'),
        ('dismissed', '已驳回误报'),
    ]

    attachment = models.ForeignKey(
        MessageAttachment,
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name="关联附件",
    )
    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='+',
        verbose_name="举报人",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="处理状态",
    )
    reason = models.CharField(max_length=120, blank=True, verbose_name="举报原因")
    detail = models.TextField(blank=True, max_length=1000, verbose_name="补充说明")
    pending_dedup_key = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        editable=False,
        verbose_name="待处理去重标记",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="举报时间")
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name="处理时间")
    handled_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name="处理人",
    )

    class Meta:
        verbose_name = "私信附件举报"
        verbose_name_plural = "私信附件举报"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['attachment', 'reporter', 'pending_dedup_key'],
                name='uniq_pending_attachment_report_per_reporter',
            ),
        ]
        indexes = [
            models.Index(fields=['attachment', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['reporter', '-created_at']),
        ]

    def save(self, *args, **kwargs):
        self.pending_dedup_key = 'pending' if self.status == 'pending' else None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reporter.username} 举报附件 {self.attachment_id} ({self.get_status_display()})"


class MessagePreference(models.Model):
    """用户的私信偏好设置"""
    MESSAGE_MODE_CHOICES = [
        ('all', '所有已登录用户'),
        ('followers_only', '仅关注者'),
        ('following_only', '仅我关注的人'),
        ('disabled', '禁用私信'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='message_preference',
        verbose_name="用户"
    )
    allow_messages = models.BooleanField(default=False, verbose_name="允许接收私信")
    message_mode = models.CharField(
        max_length=20,
        choices=MESSAGE_MODE_CHOICES,
        default='all',
        verbose_name="私信模式"
    )
    show_read_status = models.BooleanField(default=True, verbose_name="显示已读状态")
    auto_reply_enabled = models.BooleanField(default=False, verbose_name="启用自动回复")
    auto_reply_text = models.TextField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="自动回复内容"
    )
    notify_new_message = models.BooleanField(default=True, verbose_name="邮件通知新私信")
    browser_new_message = models.BooleanField(default=False, verbose_name="浏览器通知新私信")
    last_email_notified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="最后邮件通知时间",
        help_text="用于聚合邮件（同一对话 15 分钟内最多一封）"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "私信偏好设置"
        verbose_name_plural = "私信偏好设置"

    def __str__(self):
        return f"{self.user.username} 的私信设置"


class UserBlocklist(models.Model):
    """用户屏蔽列表"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='blocked_users',
        verbose_name="屏蔽者"
    )
    blocked_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='blocked_by',
        verbose_name="被屏蔽用户"
    )
    reason = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="屏蔽原因"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="屏蔽时间")

    class Meta:
        verbose_name = "用户屏蔽"
        verbose_name_plural = "用户屏蔽"
        unique_together = ('user', 'blocked_user')
        indexes = [
            models.Index(fields=['user', 'blocked_user']),
        ]

    def __str__(self):
        return f"{self.user.username} 屏蔽了 {self.blocked_user.username}"


class UserFollow(models.Model):
    """用户关注 / 订阅关系"""
    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='following_set',
        verbose_name="关注者"
    )
    following = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='follower_set',
        verbose_name="被关注者"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="关注时间")

    class Meta:
        verbose_name = "用户关注"
        verbose_name_plural = "用户关注"
        unique_together = ('follower', 'following')
        indexes = [
            models.Index(fields=['follower', 'following']),
            models.Index(fields=['following', '-created_at']),
        ]

    def __str__(self):
        return f"{self.follower.username} 关注了 {self.following.username}"


class NewConversationQuotaLog(models.Model):
    """新对话配额日志：用户每天主动向多少个陌生人发起新对话"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='new_conv_quota_logs',
        verbose_name="发起者"
    )
    peer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='+',
        verbose_name="对方"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="发起时间")
    turnstile_passed = models.BooleanField(default=False, verbose_name="本次是否通过了 Turnstile")

    class Meta:
        verbose_name = "新对话配额日志"
        verbose_name_plural = "新对话配额日志"
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.peer.username} @ {self.created_at}"


class ConversationSettings(models.Model):
    """用户对单个对话（peer）的个人会话设置

    设计为单向记录：user 视角下对 peer 的所有可调项。同一个会话在双方各有一条。
    """
    DISAPPEARING_CHOICES = [
        (0, '立即（阅读后即焚）'),
        (3600, '1 小时'),
        (86400, '24 小时'),
        (604800, '7 天'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='conversation_settings', verbose_name="归属用户"
    )
    peer = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='+', verbose_name="对方"
    )
    is_pinned = models.BooleanField(default=False, verbose_name="置顶")
    pinned_at = models.DateTimeField(null=True, blank=True, verbose_name="置顶时间")
    is_muted = models.BooleanField(default=False, verbose_name="消息免打扰")
    is_archived = models.BooleanField(default=False, verbose_name="已归档")
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name="归档时间")
    disappearing_enabled = models.BooleanField(default=False, verbose_name="开启阅后即焚")
    disappearing_ttl_seconds = models.IntegerField(default=86400, verbose_name="阅后即焚 TTL (秒)")
    last_read_at = models.DateTimeField(null=True, blank=True, verbose_name="最后读取时间")
    force_unread = models.BooleanField(default=False, verbose_name="手动标记未读")
    cleared_before = models.DateTimeField(null=True, blank=True, verbose_name="清空时间（不显示此时间之前的消息）")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "会话设置"
        verbose_name_plural = "会话设置"
        unique_together = ('user', 'peer')
        indexes = [
            models.Index(fields=['user', 'is_archived']),
            models.Index(fields=['user', 'is_pinned']),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.peer.username} 会话设置"


class MessageReport(models.Model):
    """举报记录"""
    REASON_CHOICES = [
        ('spam', '垃圾广告'),
        ('abuse', '辱骂骚扰'),
        ('porn', '色情低俗'),
        ('scam', '诈骗欺诈'),
        ('other', '其他'),
    ]
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('resolved', '已处理'),
        ('dismissed', '已驳回'),
    ]

    reporter = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='+', verbose_name="举报者"
    )
    reported_user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='+', verbose_name="被举报者"
    )
    message = models.ForeignKey(
        Message, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='reports', verbose_name="关联消息"
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, verbose_name="原因")
    detail = models.TextField(blank=True, max_length=1000, verbose_name="补充说明")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="处理状态"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="举报时间")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="处理时间")

    class Meta:
        verbose_name = "私信举报"
        verbose_name_plural = "私信举报"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['reported_user']),
        ]

    def __str__(self):
        return f"{self.reporter.username} 举报 {self.reported_user.username} ({self.get_reason_display()})"


@receiver(post_save, sender=User)
def create_message_preference(sender, instance, created, **kwargs):
    """自动为新用户创建私信偏好设置"""
    if created:
        MessagePreference.objects.get_or_create(user=instance)
