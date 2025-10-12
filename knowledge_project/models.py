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

logger = logging.getLogger(__name__)
# ---------------- 标签 ----------------
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="标签名")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "标签"
        verbose_name_plural = "标签"


# ---------------- 笔记 ----------------
class Note(models.Model):
    title = models.CharField(max_length=255, verbose_name="笔记标题")
    content = CKEditor5Field(verbose_name="笔记内容", null=True, blank=True, config_name='full')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes', verbose_name="作者")

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
    tags = models.ManyToManyField(Tag, blank=True, related_name='notes', verbose_name="标签")

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
            allowed_attributes = {
                'a': {'href', 'title', 'target'},
                'img': {'alt', 'title', 'width', 'height', 'src'},
                '*': {'class'},
            }
            self.content = nh3.clean(
                self.content,
                tags=allowed_tags,
                attributes=allowed_attributes,
                strip_comments=True,
                url_schemes={'http', 'https'}
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return (self.title[:50] + "…") if len(self.title) > 50 else self.title

    class Meta:
        verbose_name, verbose_name_plural = "知识笔记", "知识笔记"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['author']),
        ]


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
        'mode': 'system',
        'primary_color': '#2196F3',
        'dark_mode': False
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
        default=default_theme_settings,  # 使用可调用函数而不是字典实例
        verbose_name="主题设置"
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
        Profile.objects.create(user=instance)
        fetch_avatar(instance)  # 自动拉取头像


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
