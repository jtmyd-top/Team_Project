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

    class Meta:
        verbose_name = "文件夹"
        verbose_name_plural = "文件夹"
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['owner', 'parent']),
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
    banner_image = models.ImageField(
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
