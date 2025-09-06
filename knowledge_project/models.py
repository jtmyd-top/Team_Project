# knowledge_project/models.py
from bs4 import BeautifulSoup
import jieba.analyse
from django.db import models
import uuid
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django_ckeditor_5.fields import CKEditor5Field
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django_ckeditor_5.fields import CKEditor5Field
import nh3



# 【架构重构】：移除了 Project 和 ProjectMembership 模型。
# 笔记和资产现在直接与用户关联，不再通过项目进行组织。

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="标签名")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "标签"
        verbose_name_plural = "标签"


# 【已移除】Project 模型被完全移除。

# 【已移除】ProjectMembership 模型被完全移除。

class Note(models.Model):
    title = models.CharField(max_length=255, verbose_name="笔记标题")
    content = CKEditor5Field(verbose_name="笔记内容", null=True, blank=True, config_name='full')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes', verbose_name="作者")

    # 【已移除】移除了 project 字段
    # project = models.ForeignKey(
    #     Project,
    #     on_delete=models.CASCADE,
    #     ...
    # )

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

    # --- 👇👇👇 【修改】简化权限检查逻辑 👇👇👇 ---
    def has_permission(self, user):
        """
        检查用户是否有权访问此笔记。
        由于没有了项目，权限规则简化为：只有笔记的作者有权访问。
        """
        # 公开笔记逻辑可以加在这里，但核心私有权限是作者本人
        # if self.is_public:
        #     return True
        return self.author == user

    # --- 👆👆👆 修改结束 👆👆👆 ---

    # --- 👇👇👇 用下面这个 save 方法替换掉您现有的 save 方法 👇👇👇 ---
    def save(self, *args, **kwargs):
        if self.content:
            # 我们将所有规则定义移到函数内部，确保它们是最新的
            allowed_tags = {
                'p', 'img', 'b', 'i', 'u', 'strong', 'em', 'strike', 'a', 'h1', 'h2', 'h3',
                'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'br', 'hr',
                'table', 'thead', 'tbody', 'tr', 'td', 'th', 'span', 'div', 'section',
                'article', 'header', 'footer', 'nav', 'aside', 'figure', 'figcaption',
                'details', 'summary'
            }

            allowed_attributes = {
                'a': {'href', 'title', 'target'},
                # 关键：我们明确列出所有需要的img属性
                'img': {'alt', 'title', 'width', 'height', 'src'},
                # 再次强调：为了安全，不建议使用 '*' 通配符允许 style
                '*': {'class'},
            }

            # 使用 nh3.clean 进行清理
            self.content = nh3.clean(
                self.content,
                tags=allowed_tags,
                attributes=allowed_attributes,
                strip_comments=True,
                # 最终确认的、最稳定的 URL 协议配置
                url_schemes={'http', 'https', ''}
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name, verbose_name_plural = "知识笔记", "知识笔记"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            # 【已移除】移除了 project 字段的索引
            # models.Index(fields=['project']),
            models.Index(fields=['author']),
        ]


def user_directory_path(instance, filename):
    if instance.uploader and instance.uploader.id:
        return f'user_{instance.uploader.id}/{filename}'
    return f'unknown_user/{filename}'


class Asset(models.Model):
    ASSET_TYPE_CHOICES = [
        ('file', '普通文件'), ('image', '图片'), ('code', '代码片段'), ('doc', '文档'),
    ]
    # 【已移除】移除了 project 字段
    # project = models.ForeignKey(...)

    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="uploaded_assets",
                                 verbose_name="上传者")
    name = models.CharField(max_length=255, verbose_name="文件名/资源名", blank=True)
    file = models.FileField(upload_to=user_directory_path, verbose_name="上传文件", null=True)
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPE_CHOICES, default='file', verbose_name="资源类型")
    description = models.TextField(blank=True, verbose_name="描述")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")
    image_hash = models.CharField(max_length=64, blank=True, db_index=True, verbose_name="文件哈希值")

    def get_protected_url(self):
        # --- 👇👇👇 这是强烈建议的修复 👇👇👇 ---
        # 手动构建一个确定的、以斜杠开头的相对URL。
        # 'protected_uploads/' 必须与您 urls.py 中的 re_path 路径前缀完全一致。
        if self.file:
            return f"/protected_uploads/{self.file.name}"
        return ""
    def __str__(self):
        return self.name or self.file.name

    class Meta:
        verbose_name = "个人资产"  # 【修改】名称可以改得更贴切
        verbose_name_plural = "个人资产"
        ordering = ['-uploaded_at']
        unique_together = ('uploader', 'image_hash')


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="关联用户")
    activation_code = models.CharField(max_length=8, blank=True, verbose_name="激活码")
    code_created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    def __str__(self):
        return f'{self.user.username} Profile'

    class Meta:
        verbose_name = "用户资料"
        verbose_name_plural = "用户资料"


# --- Django Signals ---
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


# 【已移除】为新用户创建个人项目的信号处理器已被移除
# @receiver(post_save, sender=User)
# def create_personal_project_for_new_user(sender, instance, created, **kwargs):
#     ...

@receiver(post_save, sender=Note)
def auto_generate_tags_for_note(sender, instance, created, **kwargs):
    if not instance.content:
        return
    soup = BeautifulSoup(instance.content, 'html.parser')
    text = soup.get_text()
    if len(text) < 20:
        return
    keywords = jieba.analyse.extract_tags(
        text,
        topK=5,
        withWeight=False,
        allowPOS=('n', 'nr', 'ns', 'nz', 'v')
    )
    if not keywords:
        return
    post_save.disconnect(auto_generate_tags_for_note, sender=Note)
    instance.tags.clear()
    for keyword in keywords:
        tag, _ = Tag.objects.get_or_create(name=keyword)
        instance.tags.add(tag)
    post_save.connect(auto_generate_tags_for_note, sender=Note)