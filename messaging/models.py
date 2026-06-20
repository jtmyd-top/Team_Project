import os
import secrets
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


# ============ ??/???? ============
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
            models.Index(
                fields=['recipient', 'is_read', 'deleted_for_recipient', 'is_recalled', '-created_at'],
                name='message_recipient_unread_idx',
            ),
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
    group_message = models.ForeignKey(
        'GroupMessage',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name="关联群组消息",
    )
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
            models.Index(fields=['uploader', 'group_message']),
            models.Index(fields=['group_message', 'created_at']),
            models.Index(fields=['was_reported']),
        ]

    def __str__(self):
        return self.original_name or self.file.name


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
    notify_group_mentions_email = models.BooleanField(default=False, verbose_name="邮件通知群@提及")
    email_mention_groups = models.ManyToManyField(
        'MessageGroup',
        blank=True,
        db_table='messaging_messagepreference_email_mention_groups',
        related_name='email_mention_preferences',
        verbose_name="群@邮件通知群组",
    )
    quiet_hours_enabled = models.BooleanField(default=False, verbose_name="Quiet hours enabled")
    quiet_hours_start = models.TimeField(null=True, blank=True, verbose_name="Quiet hours start")
    quiet_hours_end = models.TimeField(null=True, blank=True, verbose_name="Quiet hours end")
    last_email_notified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="最后邮件通知时间",
        help_text="用于聚合邮件（同一对话 15 分钟内最多一封）"
    )
    last_group_mention_email_notified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="最后群@邮件通知时间",
        help_text="用于抑制群@邮件通知频率",
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


class MessageGroupPolicy(models.Model):
    """私信群组创建策略。管理员可在后台调整阈值，默认开启。"""
    enabled = models.BooleanField(default=True, verbose_name="允许用户创建群组")
    min_public_notes = models.PositiveIntegerField(default=10, verbose_name="公开文章数门槛")
    min_followers = models.PositiveIntegerField(default=50, verbose_name="关注者数门槛")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "私信群组创建策略"
        verbose_name_plural = "私信群组创建策略"

    def __str__(self):
        status = "开启" if self.enabled else "关闭"
        return f"群组创建策略（{status}，公开文章≥{self.min_public_notes} 或关注者≥{self.min_followers}）"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_current(cls):
        policy, _ = cls.objects.get_or_create(pk=1)
        return policy

    def user_stats(self, user):
        from notes.models import Note

        public_notes = Note.objects.filter(author=user, is_public=True, is_trashed=False).count()
        followers = UserFollow.objects.filter(following=user).count()
        return {
            'public_notes': public_notes,
            'followers': followers,
        }

    def can_create_group(self, user):
        stats = self.user_stats(user)
        eligible = self.enabled and (
            stats['public_notes'] >= self.min_public_notes or
            stats['followers'] >= self.min_followers
        )
        return eligible, stats


class MessageGroup(models.Model):
    """私信群组。群组不支持阅后即焚，消息可撤回、可举报。"""
    MUTE_MODE_NONE = 'none'
    MUTE_MODE_ADMINS_ONLY = 'admins_only'
    MUTE_MODE_CHOICES = [
        (MUTE_MODE_NONE, '不限制发言'),
        (MUTE_MODE_ADMINS_ONLY, '仅群主/管理员可发言'),
    ]

    name = models.CharField(max_length=80, verbose_name="群组名称")
    avatar = models.ImageField(upload_to='group_avatars/', null=True, blank=True, verbose_name="群头像")
    description = models.TextField(blank=True, default='', verbose_name="群简介")
    announcement = models.TextField(blank=True, default='', verbose_name="群公告")
    # Phase 3: 群公告增强
    announcement_pinned_at = models.DateTimeField(null=True, blank=True, verbose_name="公告置顶时间")
    announcement_updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='updated_group_announcements', verbose_name="公告更新者"
    )
    # Phase 3: 入群审批
    require_approval = models.BooleanField(default=False, verbose_name="需要入群审批")
    allow_member_mention_all = models.BooleanField(default=False, verbose_name="Allow members to mention everyone")
    pinned_message = models.ForeignKey(
        'GroupMessage', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='pinned_in_groups', verbose_name="Pinned group message"
    )
    # Phase 3: 自动回复
    auto_reply_enabled = models.BooleanField(default=False, verbose_name="启用自动回复")
    auto_reply_text = models.TextField(max_length=500, blank=True, default='', verbose_name="自动回复文本")
    mute_mode = models.CharField(
        max_length=32,
        choices=MUTE_MODE_CHOICES,
        default=MUTE_MODE_NONE,
        verbose_name="发言模式",
    )
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='owned_message_groups', verbose_name="群主"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='+', verbose_name="创建者"
    )
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "私信群组"
        verbose_name_plural = "私信群组"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['owner', '-created_at']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name


class MessageGroupMember(models.Model):
    ROLE_CHOICES = [
        ('owner', '群主'),
        ('admin', '管理员'),
        ('member', '成员'),
    ]

    group = models.ForeignKey(
        MessageGroup, on_delete=models.CASCADE, related_name='memberships', verbose_name="群组"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='message_group_memberships', verbose_name="成员"
    )
    role = models.CharField(max_length=12, choices=ROLE_CHOICES, default='member', verbose_name="角色")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="加入时间")
    left_at = models.DateTimeField(null=True, blank=True, verbose_name="退出时间")
    last_read_at = models.DateTimeField(null=True, blank=True, verbose_name="最后读取时间")
    is_pinned = models.BooleanField(default=False, verbose_name="置顶")
    pinned_at = models.DateTimeField(null=True, blank=True, verbose_name="置顶时间")
    is_muted = models.BooleanField(default=False, verbose_name="消息免打扰")
    muted_until = models.DateTimeField(null=True, blank=True, verbose_name="群内禁言到期时间")
    is_archived = models.BooleanField(default=False, verbose_name="已归档")
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name="归档时间")
    force_unread = models.BooleanField(default=False, verbose_name="手动标记未读")
    cleared_before = models.DateTimeField(null=True, blank=True, verbose_name="清空时间")

    class Meta:
        verbose_name = "私信群组成员"
        verbose_name_plural = "私信群组成员"
        unique_together = ('group', 'user')
        indexes = [
            models.Index(fields=['user', 'is_archived']),
            models.Index(fields=['group', 'left_at']),
        ]

    def __str__(self):
        return f"{self.user.username} @ {self.group.name}"

    @property
    def is_active(self):
        return self.left_at is None and self.group.is_active


def generate_group_invite_token():
    return secrets.token_urlsafe(24)


class MessageGroupInviteLink(models.Model):
    """群组邀请链接。可撤销，可设置过期时间和使用次数上限。"""
    group = models.ForeignKey(
        MessageGroup, on_delete=models.CASCADE, related_name='invite_links', verbose_name="群组"
    )
    token = models.CharField(
        max_length=64, unique=True, default=generate_group_invite_token, verbose_name="邀请令牌"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='+', verbose_name="创建者"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="过期时间")
    max_uses = models.PositiveIntegerField(null=True, blank=True, verbose_name="最大使用次数")
    uses_count = models.PositiveIntegerField(default=0, verbose_name="已使用次数")
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name="撤销时间")

    class Meta:
        verbose_name = "群组邀请链接"
        verbose_name_plural = "群组邀请链接"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'revoked_at'], name='knowledge_p_group_i_6012d6_idx'),
            models.Index(fields=['token'], name='knowledge_p_token_cf0d54_idx'),
        ]

    def __str__(self):
        return f"{self.group.name} invite"

    def is_valid(self, now=None):
        now = now or timezone.now()
        if self.revoked_at is not None:
            return False
        if self.expires_at and self.expires_at <= now:
            return False
        if self.max_uses is not None and self.uses_count >= self.max_uses:
            return False
        return self.group.is_active


class MessageGroupInviteUse(models.Model):
    invite = models.ForeignKey(
        MessageGroupInviteLink, on_delete=models.CASCADE,
        related_name='use_records', verbose_name="Invite link"
    )
    group = models.ForeignKey(
        MessageGroup, on_delete=models.CASCADE,
        related_name='invite_use_records', verbose_name="Group"
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='message_group_invite_uses', verbose_name="Joined user"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Used at")

    class Meta:
        verbose_name = "Group invite use"
        verbose_name_plural = "Group invite uses"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invite', '-created_at']),
            models.Index(fields=['group', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        username = self.user.username if self.user else 'unknown'
        return f"{username} used invite {self.invite_id}"


class MessageGroupAnnouncementHistory(models.Model):
    group = models.ForeignKey(
        MessageGroup, on_delete=models.CASCADE,
        related_name='announcement_history', verbose_name="Group"
    )
    editor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='message_group_announcement_edits', verbose_name="Editor"
    )
    content = models.TextField(blank=True, default='', verbose_name="Announcement")
    pinned = models.BooleanField(default=False, verbose_name="Pinned")
    message = models.OneToOneField(
        'GroupMessage', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='announcement_record', verbose_name="Announcement message"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Edited at")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated at")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Deleted at")

    class Meta:
        verbose_name = "Group announcement history"
        verbose_name_plural = "Group announcement history"
        ordering = ['-pinned', '-updated_at', '-created_at']
        indexes = [
            models.Index(fields=['group', 'deleted_at', '-pinned', '-updated_at']),
            models.Index(fields=['editor', '-created_at']),
        ]

    def __str__(self):
        return f"{self.group.name} announcement @ {self.created_at}"


class MessageGroupAnnouncementRead(models.Model):
    group = models.ForeignKey(
        MessageGroup,
        on_delete=models.CASCADE,
        related_name='announcement_reads',
        verbose_name='Group',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='group_announcement_reads',
        verbose_name='User',
    )
    announcement = models.ForeignKey(
        MessageGroupAnnouncementHistory,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='read_receipts',
        verbose_name='Announcement',
    )
    read_at = models.DateTimeField(auto_now=True, verbose_name='Read at')

    class Meta:
        verbose_name = 'Group announcement read'
        verbose_name_plural = 'Group announcement reads'
        unique_together = ('group', 'user', 'announcement')
        indexes = [
            models.Index(fields=['group', 'announcement']),
            models.Index(fields=['user', '-read_at']),
        ]

    def __str__(self):
        return f'{self.user.username} read announcement {self.announcement_id} in {self.group.name}'


class GroupMessage(models.Model):
    """群组消息。独立于一对一 Message，避免继承阅后即焚语义。"""
    group = models.ForeignKey(
        MessageGroup, on_delete=models.CASCADE, related_name='messages', verbose_name="群组"
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_group_messages', verbose_name="发送者"
    )
    content = models.TextField(verbose_name="消息内容")
    searchable_text = models.TextField(blank=True, default='', verbose_name="搜索文本")
    # Phase 2: 消息引用和转发
    reply_to = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='replies', verbose_name="回复消息"
    )
    forwarded_from = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='forwards', verbose_name="转发自消息"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="发送时间")
    is_edited = models.BooleanField(default=False, verbose_name="已编辑")
    edited_at = models.DateTimeField(null=True, blank=True, verbose_name="编辑时间")
    is_recalled = models.BooleanField(default=False, verbose_name="已撤回")
    recalled_at = models.DateTimeField(null=True, blank=True, verbose_name="撤回时间")
    was_reported = models.BooleanField(default=False, verbose_name="是否曾被举报")

    class Meta:
        verbose_name = "群组消息"
        verbose_name_plural = "群组消息"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['was_reported']),
        ]

    def __str__(self):
        return f"{self.sender.username} → {self.group.name}"


class GroupMessageDeletion(models.Model):
    """群组消息对单个成员隐藏。"""
    message = models.ForeignKey(
        GroupMessage, on_delete=models.CASCADE, related_name='deletions', verbose_name="群组消息"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+', verbose_name="用户")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="删除时间")

    class Meta:
        verbose_name = "群组消息删除记录"
        verbose_name_plural = "群组消息删除记录"
        unique_together = ('message', 'user')
        indexes = [
            models.Index(fields=['user', 'message']),
        ]


class MessageGroupBan(models.Model):
    """群组封禁记录。有效封禁会阻止用户通过邀请链接或管理员添加重新入群。"""
    group = models.ForeignKey(
        MessageGroup, on_delete=models.CASCADE, related_name='bans', verbose_name="群组"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='message_group_bans', verbose_name="被封禁用户"
    )
    banned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='issued_message_group_bans', verbose_name="封禁操作者"
    )
    reason = models.TextField(blank=True, default='', verbose_name="封禁原因")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="过期时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="封禁时间")
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name="解封时间")
    revoked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='revoked_message_group_bans', verbose_name="解封操作者"
    )

    class Meta:
        verbose_name = "群组封禁记录"
        verbose_name_plural = "群组封禁记录"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'user']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['revoked_at']),
        ]

    def __str__(self):
        return f"{self.user.username} banned from {self.group.name}"

    def is_active(self, now=None):
        now = now or timezone.now()
        if self.revoked_at is not None:
            return False
        if self.expires_at and self.expires_at <= now:
            return False
        return True


class MessageGroupAuditLog(models.Model):
    """群组管理审计日志。"""
    ACTION_CHOICES = [
        ('group_create', '创建群组'),
        ('group_update_profile', '更新群资料'),
        ('group_rename', '修改群名'),
        ('group_announcement_update', '更新群公告'),
        ('member_add', '添加成员'),
        ('member_remove', '移除成员'),
        ('member_role_change', '修改成员角色'),
        ('member_mute', '禁言成员'),
        ('member_unmute', '解除成员禁言'),
        ('group_mute_change', '修改全员禁言'),
        ('ownership_transfer', '转让群主'),
        ('invite_link_create', '创建邀请链接'),
        ('invite_link_revoke', '撤销邀请链接'),
        ('member_ban', '封禁成员'),
        ('member_unban', '解除封禁'),
        ('group_dissolve', '解散群组'),
        ('group_leave', '退出群组'),
    ]

    group = models.ForeignKey(
        MessageGroup, on_delete=models.CASCADE, related_name='audit_logs', verbose_name="群组"
    )
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='message_group_audit_actions', verbose_name="操作者"
    )
    target_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='message_group_audit_targets', verbose_name="目标用户"
    )
    action = models.CharField(max_length=64, choices=ACTION_CHOICES, verbose_name="动作")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="元数据")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "群组审计日志"
        verbose_name_plural = "群组审计日志"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', '-created_at']),
            models.Index(fields=['actor']),
            models.Index(fields=['target_user']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.group.name} {self.action}"


def create_message_preference(sender, instance, created, **kwargs):
    """自动为新用户创建私信偏好设置"""
    if created:
        MessagePreference.objects.get_or_create(user=instance)


# ==================== Phase 2: 群组消息系统增强 ====================


class GroupMessageMention(models.Model):
    """群组消息@提及记录"""
    message = models.ForeignKey(
        'GroupMessage', on_delete=models.CASCADE, related_name='mentions', verbose_name="消息"
    )
    mentioned_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='group_mentions', verbose_name="被提及用户"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="提及时间")

    class Meta:
        verbose_name = "群组消息提及"
        verbose_name_plural = "群组消息提及"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['message']),
            models.Index(fields=['mentioned_user', '-created_at']),
        ]
        unique_together = [('message', 'mentioned_user')]

    def __str__(self):
        return f"@{self.mentioned_user.username} in {self.message.group.name}"


class GroupMessageReaction(models.Model):
    """群组消息表情回应"""
    message = models.ForeignKey(
        'GroupMessage', on_delete=models.CASCADE, related_name='reactions', verbose_name="消息"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='group_message_reactions', verbose_name="用户"
    )
    emoji = models.CharField(max_length=20, verbose_name="表情符号")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="反应时间")

    class Meta:
        verbose_name = "群组消息表情回应"
        verbose_name_plural = "群组消息表情回应"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['message', 'emoji']),
            models.Index(fields=['user', '-created_at']),
        ]
        unique_together = [('message', 'user', 'emoji')]

    def __str__(self):
        return f"{self.user.username} {self.emoji} on {self.message_id}"


# ==================== Phase 3: 群组管理功能增强 ====================


class GroupJoinRequest(models.Model):
    """入群审批请求"""
    STATUS_CHOICES = [
        ('pending', '待审批'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
    ]

    group = models.ForeignKey(
        MessageGroup, on_delete=models.CASCADE, related_name='join_requests', verbose_name="群组"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='group_join_requests', verbose_name="申请用户"
    )
    request_message = models.TextField(
        max_length=200, blank=True, default='', verbose_name="申请留言"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态"
    )
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='reviewed_join_requests', verbose_name="审批人"
    )
    rejection_reason = models.TextField(
        max_length=200, blank=True, default='', verbose_name="拒绝原因"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="申请时间")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="审批时间")

    class Meta:
        verbose_name = "入群申请"
        verbose_name_plural = "入群申请"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'status', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
        unique_together = [('group', 'user', 'status')]

    def __str__(self):
        return f"{self.user.username} -> {self.group.name} ({self.get_status_display()})"


class GroupTag(models.Model):
    """群组标签"""
    name = models.CharField(max_length=20, unique=True, verbose_name="标签名称")
    color = models.CharField(max_length=7, default='#409EFF', verbose_name="标签颜色")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "群组标签"
        verbose_name_plural = "群组标签"
        ordering = ['name']

    def __str__(self):
        return self.name


class GroupTagRelation(models.Model):
    """用户给群组打标签的关系"""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='group_tag_relations', verbose_name="用户"
    )
    group = models.ForeignKey(
        MessageGroup, on_delete=models.CASCADE, related_name='user_tags', verbose_name="群组"
    )
    tag = models.ForeignKey(
        GroupTag, on_delete=models.CASCADE, related_name='group_relations', verbose_name="标签"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "群组标签关系"
        verbose_name_plural = "群组标签关系"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'group']),
            models.Index(fields=['group', 'tag']),
        ]
        unique_together = [('user', 'group', 'tag')]

    def __str__(self):
        return f"{self.user.username} tagged {self.group.name} as {self.tag.name}"
