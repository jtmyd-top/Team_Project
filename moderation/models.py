from django.conf import settings
from django.db import models


class AttachmentReport(models.Model):
    """Report ticket for a private-message attachment."""

    REASON_CHOICES = [
        ('spam', '垃圾广告'),
        ('abuse', '辱骂骚扰'),
        ('porn', '色情低俗'),
        ('scam', '诈骗欺诈'),
        ('privacy', '侵犯隐私'),
        ('illegal', '违法违规'),
        ('other', '其他'),
    ]
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('removed', '已违规删除'),
        ('dismissed', '已驳回误报'),
    ]

    attachment = models.ForeignKey(
        'messaging.MessageAttachment',
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name="关联附件",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
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
    reason = models.CharField(max_length=120, choices=REASON_CHOICES, default='other', verbose_name="举报原因")
    detail = models.TextField(blank=True, max_length=1000, verbose_name="补充说明")
    evidence_snapshot = models.JSONField(default=dict, blank=True, verbose_name="举报证据快照")
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
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name="处理人",
    )
    resolution_note = models.TextField(blank=True, verbose_name="处理备注")

    class Meta:
        db_table = 'moderation_attachmentreport'
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
            models.Index(fields=['attachment', 'status'], name='knowledge_p_attachm_58c78e_idx'),
            models.Index(fields=['status', '-created_at'], name='knowledge_p_status_8f4cb4_idx'),
            models.Index(fields=['reporter', '-created_at'], name='knowledge_p_reporte_46bcc1_idx'),
        ]

    def save(self, *args, **kwargs):
        self.pending_dedup_key = 'pending' if self.status == 'pending' else None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reporter.username} 举报附件 {self.attachment_id} ({self.get_status_display()})"


class NoteReport(models.Model):
    """Report ticket for a public note/article."""

    REASON_CHOICES = AttachmentReport.REASON_CHOICES
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('removed', '已下架'),
        ('dismissed', '已驳回'),
    ]

    note = models.ForeignKey(
        'notes.Note',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reports',
        verbose_name="关联文章",
    )
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+', verbose_name="举报人")
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name="被举报用户",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="处理状态")
    reason = models.CharField(max_length=120, choices=REASON_CHOICES, default='other', verbose_name="举报原因")
    detail = models.TextField(blank=True, max_length=1000, verbose_name="补充说明")
    evidence_snapshot = models.JSONField(default=dict, blank=True, verbose_name="举报证据快照")
    pending_dedup_key = models.CharField(max_length=16, null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="举报时间")
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name="处理时间")
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    resolution_note = models.TextField(blank=True, verbose_name="处理备注")

    class Meta:
        db_table = 'moderation_notereport'
        verbose_name = "文章举报"
        verbose_name_plural = "文章举报"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['note', 'reporter', 'pending_dedup_key'],
                name='uniq_pending_note_report_per_reporter',
            ),
        ]
        indexes = [
            models.Index(fields=['note', 'status'], name='knowledge_p_note_id_5b63af_idx'),
            models.Index(fields=['status', '-created_at'], name='knowledge_p_status_fa622a_idx'),
            models.Index(fields=['reporter', '-created_at'], name='knowledge_p_reporte_b322f9_idx'),
            models.Index(fields=['reported_user'], name='knowledge_p_reporte_45dc07_idx'),
        ]

    def save(self, *args, **kwargs):
        self.pending_dedup_key = 'pending' if self.status == 'pending' else None
        if self.note_id and self.reported_user_id is None:
            self.reported_user = self.note.author
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reporter.username} reported note {self.note_id} ({self.get_status_display()})"


class CommentReport(models.Model):
    """Report ticket for a note comment or reply."""

    REASON_CHOICES = AttachmentReport.REASON_CHOICES
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('removed', '已删除'),
        ('dismissed', '已驳回'),
    ]

    comment = models.ForeignKey(
        'notes.NoteComment',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reports',
        verbose_name="关联评论",
    )
    note = models.ForeignKey(
        'notes.Note',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='comment_reports',
        verbose_name="关联文章",
    )
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+', verbose_name="举报人")
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name="被举报用户",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="处理状态")
    reason = models.CharField(max_length=120, choices=REASON_CHOICES, default='other', verbose_name="举报原因")
    detail = models.TextField(blank=True, max_length=1000, verbose_name="补充说明")
    evidence_snapshot = models.JSONField(default=dict, blank=True, verbose_name="举报证据快照")
    pending_dedup_key = models.CharField(max_length=16, null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="举报时间")
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name="处理时间")
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    resolution_note = models.TextField(blank=True, verbose_name="处理备注")

    class Meta:
        db_table = 'moderation_commentreport'
        verbose_name = "评论举报"
        verbose_name_plural = "评论举报"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['comment', 'reporter', 'pending_dedup_key'],
                name='uniq_pending_comment_report_per_reporter',
            ),
        ]
        indexes = [
            models.Index(fields=['comment', 'status'], name='knowledge_p_comment_d35317_idx'),
            models.Index(fields=['status', '-created_at'], name='knowledge_p_status_25a0ee_idx'),
            models.Index(fields=['reporter', '-created_at'], name='knowledge_p_reporte_17249c_idx'),
            models.Index(fields=['reported_user'], name='knowledge_p_reporte_869c9d_idx'),
        ]

    def save(self, *args, **kwargs):
        self.pending_dedup_key = 'pending' if self.status == 'pending' else None
        if self.comment_id:
            if self.note_id is None:
                self.note = self.comment.note
            if self.reported_user_id is None:
                self.reported_user = self.comment.author
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reporter.username} reported comment {self.comment_id} ({self.get_status_display()})"


class MessageReport(models.Model):
    """Report ticket for private or group messages."""

    REASON_CHOICES = AttachmentReport.REASON_CHOICES
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('resolved', '已处理'),
        ('dismissed', '已驳回'),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='+',
        verbose_name="举报者",
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='+',
        verbose_name="被举报者",
    )
    message = models.ForeignKey(
        'messaging.Message',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reports',
        verbose_name="关联消息",
    )
    group_message = models.ForeignKey(
        'messaging.GroupMessage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reports',
        verbose_name="关联群组消息",
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, verbose_name="原因")
    detail = models.TextField(blank=True, max_length=1000, verbose_name="补充说明")
    evidence_snapshot = models.JSONField(default=dict, blank=True, verbose_name="举报证据快照")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="处理状态",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="举报时间")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="处理时间")
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name="处理人",
    )
    resolution_note = models.TextField(blank=True, verbose_name="处理备注")

    class Meta:
        db_table = 'moderation_messagereport'
        verbose_name = "私信举报"
        verbose_name_plural = "私信举报"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='knowledge_p_status_5b6c65_idx'),
            models.Index(fields=['reported_user'], name='knowledge_p_reporte_e39bf0_idx'),
        ]

    def __str__(self):
        return f"{self.reporter.username} 举报 {self.reported_user.username} ({self.get_reason_display()})"


class UserSanction(models.Model):
    """用户处置 / 制裁记录（实际生效的惩罚）。"""

    SANCTION_TYPE_CHOICES = [
        ('mute_messages', '禁言私信'),
        ('ban_comments', '禁止评论'),
        ('ban_public_notes', '禁止发布公开文章'),
        ('ban_login', '封禁登录'),
    ]
    REPORT_TYPE_CHOICES = [
        ('message', '私信举报'),
        ('attachment', '附件举报'),
        ('note', '文章举报'),
        ('comment', '评论举报'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sanctions',
        verbose_name="被处置用户",
    )
    sanction_type = models.CharField(
        max_length=20,
        choices=SANCTION_TYPE_CHOICES,
        verbose_name="处置类型",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="到期时间",
        help_text="留空表示永久",
    )
    reason = models.TextField(blank=True, verbose_name="处置原因 / 备注")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name="操作管理员",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="处置时间")
    is_active = models.BooleanField(default=True, verbose_name="是否生效")
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name="解除时间")
    source_report_type = models.CharField(
        max_length=20,
        choices=REPORT_TYPE_CHOICES,
        blank=True,
        verbose_name="来源工单类型",
    )
    source_report_id = models.IntegerField(null=True, blank=True, verbose_name="来源工单 ID")

    class Meta:
        db_table = 'moderation_usersanction'
        verbose_name = "用户处置"
        verbose_name_plural = "用户处置"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'sanction_type', 'is_active'], name='usanction_user_type_act_idx'),
            models.Index(fields=['is_active', 'expires_at'], name='usanction_active_exp_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_sanction_type_display()}"

    @property
    def is_effective(self):
        """当前是否实际生效（生效中且未过期）。"""
        from django.utils import timezone

        if not self.is_active:
            return False
        if self.expires_at is not None and self.expires_at <= timezone.now():
            return False
        return True

    @property
    def is_permanent(self):
        return self.expires_at is None

    @classmethod
    def active_for(cls, user, sanction_type):
        """返回该用户某类有效制裁中最晚到期的一条（永久优先），否则 None。"""
        from django.utils import timezone

        if user is None or not getattr(user, 'id', None):
            return None
        now = timezone.now()
        qs = cls.objects.filter(
            user=user,
            sanction_type=sanction_type,
            is_active=True,
        ).filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
        permanent = qs.filter(expires_at__isnull=True).first()
        if permanent is not None:
            return permanent
        return qs.order_by('-expires_at').first()

    @classmethod
    def is_muted(cls, user):
        return cls.active_for(user, 'mute_messages')

    @classmethod
    def is_comment_banned(cls, user):
        return cls.active_for(user, 'ban_comments')

    @classmethod
    def is_public_note_banned(cls, user):
        return cls.active_for(user, 'ban_public_notes')

    @classmethod
    def is_login_banned(cls, user):
        return cls.active_for(user, 'ban_login')


class ModerationLog(models.Model):
    """处置审计日志（append-only），记录每一次举报处置决策。"""

    REPORT_TYPE_CHOICES = [
        ('message', '私信举报'),
        ('attachment', '附件举报'),
        ('note', '文章举报'),
        ('comment', '评论举报'),
    ]

    report_type = models.CharField(
        max_length=20,
        choices=REPORT_TYPE_CHOICES,
        verbose_name="工单类型",
    )
    report_id = models.IntegerField(verbose_name="工单 ID")
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name="处置人",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name="被处置对象",
    )
    action = models.CharField(max_length=40, verbose_name="处置动作")
    note = models.TextField(blank=True, verbose_name="备注")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="处置时间")

    class Meta:
        db_table = 'moderation_moderationlog'
        verbose_name = "处置日志"
        verbose_name_plural = "处置日志"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_type', 'report_id'], name='modlog_report_idx'),
            models.Index(fields=['-created_at'], name='modlog_created_idx'),
        ]

    def __str__(self):
        return f"{self.report_type}#{self.report_id} - {self.action}"


class ModerationAppeal(models.Model):
    """Appeal submitted by a sanctioned user."""

    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('accepted', '申诉通过'),
        ('rejected', '申诉驳回'),
    ]

    sanction = models.ForeignKey(
        UserSanction,
        on_delete=models.CASCADE,
        related_name='appeals',
        verbose_name="关联处置",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='moderation_appeals',
        verbose_name="申诉用户",
    )
    reason = models.TextField(max_length=2000, verbose_name="申诉理由")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="处理状态")
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name="处理人",
    )
    resolution_note = models.TextField(blank=True, verbose_name="处理备注")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="提交时间")
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name="处理时间")

    class Meta:
        db_table = 'moderation_moderationappeal'
        verbose_name = "处置申诉"
        verbose_name_plural = "处置申诉"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='mappeal_status_idx'),
            models.Index(fields=['user', '-created_at'], name='mappeal_user_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} appeal sanction #{self.sanction_id}"


class ModerationTemplate(models.Model):
    """Reusable moderator note template."""

    DECISION_CHOICES = [
        ('uphold', '举报成立'),
        ('dismiss', '驳回举报'),
        ('manual', '重新处置'),
        ('appeal', '申诉处理'),
    ]

    title = models.CharField(max_length=80, verbose_name="模板名称")
    report_type = models.CharField(
        max_length=20,
        choices=ModerationLog.REPORT_TYPE_CHOICES,
        blank=True,
        verbose_name="适用举报类型",
    )
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES, blank=True, verbose_name="适用场景")
    content = models.TextField(max_length=2000, verbose_name="模板内容")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = 'moderation_moderationtemplate'
        verbose_name = "处置模板"
        verbose_name_plural = "处置模板"
        ordering = ['report_type', 'decision', 'title']
        indexes = [
            models.Index(fields=['is_active', 'report_type', 'decision'], name='mtemplate_lookup_idx'),
        ]

    def __str__(self):
        return self.title
