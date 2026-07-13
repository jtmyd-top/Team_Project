import logging
import os
import re
import uuid
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup
import jieba.analyse
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_ckeditor_5.fields import CKEditor5Field
import nh3

logger = logging.getLogger(__name__)

# ---------------- 标签 ----------------
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="标签名")

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'knowledge_project_tag'
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
        db_table = 'knowledge_project_folder'
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

    def collaborator_role_for(self, user):
        if not user or not getattr(user, 'is_authenticated', False):
            return None
        if self.author_id == user.id:
            return NoteCollaborator.ROLE_MANAGER
        return self.collaborators.filter(user=user).values_list('role', flat=True).first()

    def has_read_permission(self, user):
        if self.is_secret:
            return self.author == user
        return self.is_public or self.author == user or bool(self.collaborator_role_for(user))

    def has_comment_permission(self, user):
        if self.is_secret or not user or not getattr(user, 'is_authenticated', False):
            return False
        if self.author_id == user.id:
            return True
        role = self.collaborator_role_for(user)
        return role in {
            NoteCollaborator.ROLE_COMMENTER,
            NoteCollaborator.ROLE_EDITOR,
            NoteCollaborator.ROLE_MANAGER,
        }

    def has_write_permission(self, user):
        if self.is_secret:
            return self.author == user
        if self.author == user:
            return True
        return self.collaborator_role_for(user) == NoteCollaborator.ROLE_EDITOR

    def has_manage_permission(self, user):
        if self.is_secret:
            return self.author == user
        return self.author == user or self.collaborator_role_for(user) == NoteCollaborator.ROLE_MANAGER

    def has_permission(self, user):
        return self.has_read_permission(user)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        normalized_update_fields = set(update_fields) if update_fields is not None else None
        is_create = self._state.adding
        old_content = None

        if not is_create and normalized_update_fields is None:
            old_content = type(self).objects.filter(pk=self.pk).values_list('content', flat=True).first()

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
            from notes.toc import extract_toc_from_html
            toc_list, updated_html = extract_toc_from_html(self.content)
            self.toc = toc_list
            self.content = updated_html

        super().save(*args, **kwargs)
        should_sync_assets = False
        if normalized_update_fields is not None:
            should_sync_assets = 'content' in normalized_update_fields
        elif is_create:
            should_sync_assets = bool(self.content)
        else:
            should_sync_assets = old_content != self.content

        if should_sync_assets:
            sync_note_asset_links(self)

    def __str__(self):
        return (self.title[:50] + "…") if len(self.title) > 50 else self.title

    class Meta:
        db_table = 'knowledge_project_note'
        verbose_name, verbose_name_plural = "知识笔记", "知识笔记"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['author']),
            models.Index(fields=['folder']),
            models.Index(fields=['is_trashed']),
            models.Index(fields=['is_favorited']),
            models.Index(fields=['is_secret']),
            models.Index(fields=['author', 'is_trashed', 'is_secret'], name='note_author_trash_secret_idx'),
            models.Index(fields=['is_public', '-updated_at'], name='note_public_updated_idx'),
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


class NoteCollaborator(models.Model):
    ROLE_READER = 'reader'
    ROLE_COMMENTER = 'commenter'
    ROLE_EDITOR = 'editor'
    ROLE_MANAGER = 'manager'
    ROLE_CHOICES = [
        (ROLE_READER, 'Reader'),
        (ROLE_COMMENTER, 'Commenter'),
        (ROLE_EDITOR, 'Editor'),
        (ROLE_MANAGER, 'Manager'),
    ]

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='collaborators')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='note_collaborations')
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_READER)
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='added_note_collaborators',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'knowledge_project_notecollaborator'
        unique_together = ('note', 'user')
        indexes = [
            models.Index(fields=['user', 'role'], name='notecollab_user_role_idx'),
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
        db_table = 'knowledge_project_asset'
        verbose_name = "个人资产"
        verbose_name_plural = "个人资产"
        ordering = ['-uploaded_at']
        unique_together = ('uploader', 'image_hash')


def extract_protected_upload_paths(html_content):
    paths = set()
    if not html_content:
        return paths

    soup = BeautifulSoup(html_content, 'html.parser')
    candidates = []
    candidates.extend(tag.get('src') for tag in soup.find_all(src=True))
    candidates.extend(tag.get('href') for tag in soup.find_all(href=True))
    candidates.extend(
        match.group(0)
        for match in re.finditer(r'/protected_uploads/[^\s"\'<>]+', str(html_content))
    )

    for raw_value in candidates:
        if not raw_value:
            continue
        parsed = urlparse(str(raw_value))
        path = unquote(parsed.path or str(raw_value))
        prefix = '/protected_uploads/'
        if not path.startswith(prefix):
            continue
        file_path = path[len(prefix):].lstrip('/\\')
        normalized = os.path.normpath(file_path).replace('\\', '/')
        if normalized and not normalized.startswith('../') and normalized != '..':
            paths.add(normalized)
    return paths


class NoteAsset(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='asset_links')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='note_links')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'knowledge_project_noteasset'
        verbose_name = "Note asset link"
        verbose_name_plural = "Note asset links"
        unique_together = ('note', 'asset')
        indexes = [
            models.Index(fields=['asset', 'note'], name='noteasset_asset_note_idx'),
        ]


def sync_note_asset_links(note):
    if not note.pk:
        return
    paths = extract_protected_upload_paths(note.content or '')
    assets = list(Asset.objects.filter(file__in=paths))
    asset_ids = {asset.id for asset in assets}

    NoteAsset.objects.filter(note=note).exclude(asset_id__in=asset_ids).delete()
    existing_ids = set(
        NoteAsset.objects.filter(note=note, asset_id__in=asset_ids)
        .values_list('asset_id', flat=True)
    )
    NoteAsset.objects.bulk_create(
        [NoteAsset(note=note, asset=asset) for asset in assets if asset.id not in existing_ids],
        ignore_conflicts=True,
    )


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
    # Store a text-based anchor instead of a fragile browser DOM path.
    anchor_text = models.CharField(max_length=1000, blank=True, default='')
    anchor_start = models.PositiveIntegerField(null=True, blank=True)
    anchor_end = models.PositiveIntegerField(null=True, blank=True)
    anchor_context = models.CharField(max_length=240, blank=True, default='')
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
        db_table = 'knowledge_project_notecomment'
        verbose_name = "笔记评论"
        verbose_name_plural = "笔记评论"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['note', 'created_at'], name='notecomment_note_created_idx'),
            models.Index(fields=['note', 'anchor_start'], name='notecomment_note_anchor_idx'),
        ]

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
        db_table = 'knowledge_project_notehistory'
        verbose_name = "笔记浏览历史"
        verbose_name_plural = "笔记浏览历史"
        ordering = ['-viewed_at']
        unique_together = ('user', 'note')
        indexes = [
            models.Index(fields=['user', '-viewed_at'], name='notehistory_user_viewed_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} 浏览了 《{self.note.title}》"


class NoteRevision(models.Model):
    """Immutable note snapshot used for history, comparison, and recovery."""

    ACTION_CREATED = 'created'
    ACTION_UPDATED = 'updated'
    ACTION_RESTORED = 'restored'
    ACTION_CHOICES = [
        (ACTION_CREATED, 'Created'),
        (ACTION_UPDATED, 'Updated'),
        (ACTION_RESTORED, 'Restored'),
    ]

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='revisions')
    version_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255, blank=True, default='')
    content = models.TextField(blank=True, default='')
    toc = models.JSONField(default=list, blank=True)
    action = models.CharField(max_length=16, choices=ACTION_CHOICES, default=ACTION_UPDATED)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='note_revisions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'knowledge_project_noterevision'
        ordering = ['-version_number']
        constraints = [
            models.UniqueConstraint(fields=['note', 'version_number'], name='note_revision_unique_version'),
        ]
        indexes = [
            models.Index(fields=['note', '-created_at'], name='noterevision_note_created_idx'),
        ]

    def __str__(self):
        return f'{self.note_id} v{self.version_number}'


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
