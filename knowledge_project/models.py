# Create your models here.
# knowledge_project/models.py

from django.db import models
import uuid
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django_ckeditor_5.fields import CKEditor5Field
from django.db.models.signals import post_save
from django.dispatch import receiver

from django_ckeditor_5.fields import CKEditor5Field
# 架构已重构：移除了 Team 和 TeamMembership 模型。
# 权限和成员管理现在直接在 Project 层级进行。

class Project(models.Model):
    """
    重构后的核心模型。每个项目都是一个独立的协作空间。
    """
    STATUS_CHOICES = [('planning', '计划中'), ('active', '进行中'), ('completed', '已完成')]
    is_personal_inbox = models.BooleanField(default=False, verbose_name="是否为随手笔记")
    title = models.CharField(max_length=200, verbose_name="项目标题")
    description = models.TextField(blank=True, null=True, verbose_name="项目描述")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='planning', verbose_name="状态")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    # 【新增】通过 ProjectMembership 将用户和项目关联起来
    members = models.ManyToManyField(
        User,
        through='ProjectMembership',
        related_name='projects',
        verbose_name="项目成员"
    )
    # 【新增】用于区分普通项目和用户注册时创建的个人项目
    is_personal_space = models.BooleanField(default=False, verbose_name="是否为个人空间")

    def __str__(self):
        return self.title

    @property
    def owner(self):
        """提供一个便捷的方式来获取项目所有者"""
        try:
            # membership关系在ProjectMembership模型中定义
            return self.memberships.get(role='owner').user
        except ProjectMembership.DoesNotExist:
            return None

    class Meta:
        verbose_name, verbose_name_plural = "项目", "项目"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['is_personal_space']),
        ]

class ProjectMembership(models.Model):
    """
    【新增】项目成员关系模型，替代原有的 TeamMembership。
    定义了用户在某个项目中的角色。
    """
    ROLE_CHOICES = [
        ('owner', '所有者'),
        ('admin', '管理员'),
        ('editor', '编辑者'),
        ('viewer', '查看者'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="project_memberships", verbose_name="用户")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships", verbose_name="项目")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='viewer', verbose_name="角色")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="加入时间")

    def clean(self):
        """
        校验逻辑，确保每个项目有且仅有一个所有者。
        """
        super().clean()
        # 规则1: 确保一个项目只有一个 'owner'
        if self.role == 'owner':
            if ProjectMembership.objects.filter(project=self.project, role='owner').exclude(pk=self.pk).exists():
                raise ValidationError('一个项目只能有一个所有者。')

        # 规则2: 防止唯一的 'owner' 被降级或删除 (在视图/序列化器中处理删除逻辑)
        if self.pk: # 仅在更新现有记录时检查
            original_instance = ProjectMembership.objects.get(pk=self.pk)
            if original_instance.role == 'owner' and self.role != 'owner':
                # 检查是否还有其他 owner
                if not ProjectMembership.objects.filter(project=self.project, role='owner').exclude(pk=self.pk).exists():
                    raise ValidationError('不能移除唯一的项目所有者。请在更改此角色之前，先将另一位成员设为所有者。')

    def __str__(self):
        return f"{self.user.username} is {self.get_role_display()} in {self.project.title}"

    class Meta:
        unique_together = ('user', 'project') # 确保一个用户在一个项目中只有一个角色
        verbose_name, verbose_name_plural = "项目成员关系", "项目成员关系"
        indexes = [
            models.Index(fields=['user', 'project']),
            models.Index(fields=['role']),
        ]

class Note(models.Model):
    title = models.CharField(max_length=255, verbose_name="笔记标题")
    content = CKEditor5Field(verbose_name="笔记内容", null=True, blank=True, config_name='full')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes', verbose_name="作者")
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name="所属项目",
        null=True,  # 允许数据库中该字段为NULL
        blank=True  # 允许在表单中（如Django Admin）提交时该字段为空
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    is_public = models.BooleanField(default=False, verbose_name="是否公开")
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name, verbose_name_plural = "知识笔记", "知识笔记"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['project']),
            models.Index(fields=['author']),  # 为新字段添加索引
        ]



def user_directory_path(instance, filename):
    """
    动态生成文件上传路径。
    文件将被上传到 MEDIA_ROOT/user_<id>/<filename> 格式的路径中。
    例如: uploads/user_1/report.pdf
    """
    # 检查 Asset 实例是否有 uploader 关联
    if instance.uploader and instance.uploader.id:
        # 使用 f-string 格式化路径，'user_' 前缀让文件夹用途更清晰
        return f'user_{instance.uploader.id}/{filename}'

    # 提供一个备用路径，以防万一 uploader 没有被设置
    return f'unknown_user/{filename}'


class Asset(models.Model):
    ASSET_TYPE_CHOICES = [
        ('file', '普通文件'), ('image', '图片'), ('code', '代码片段'), ('doc', '文档'),
    ]

    project = models.ForeignKey('Project', on_delete=models.CASCADE, related_name="assets", verbose_name="所属项目")
    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="uploaded_assets",
                                 verbose_name="上传者")

    # 【修改点】在这里添加 blank=True，使其变为非必填字段
    name = models.CharField(max_length=255, verbose_name="文件名/资源名", blank=True)

    file = models.FileField(upload_to=user_directory_path, verbose_name="上传文件")
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPE_CHOICES, default='file', verbose_name="资源类型")
    description = models.TextField(blank=True, verbose_name="描述")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")

    def __str__(self):
        # 如果name为空，就显示文件名，避免显示空白
        return self.name or self.file.name

    class Meta:
        verbose_name = "项目资产"
        verbose_name_plural = "项目资产"
        ordering = ['-uploaded_at']

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
    """当新用户创建时，自动为其创建 Profile。"""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def create_personal_project_for_new_user(sender, instance, created, **kwargs):
    """
    【新增信号】当新用户创建时，自动为其创建一个个人项目空间。
    """
    if created:
        # 1. 创建个人项目
        personal_project = Project.objects.create(
            title=f"{instance.username}的个人空间",
            description="这是您的个人项目空间，用于存放您的私人笔记和资产。",
            is_personal_space=True
        )
        # 2. 将该用户设为项目的所有者
        ProjectMembership.objects.create(
            user=instance,
            project=personal_project,
            role='owner'
        )