from django.conf import settings
from django.db import models


class UserNotification(models.Model):
    """Lightweight in-app notification record."""

    KIND_CHOICES = [
        ('report_received', '举报已收到'),
        ('report_resolved', '举报已处理'),
        ('sanction_applied', '用户处置'),
        ('sanction_revoked', '处置解除'),
        ('appeal_submitted', '申诉已提交'),
        ('appeal_resolved', '申诉已处理'),
        ('new_comment', 'New comment'),
        ('comment_reply', 'Comment reply'),
        ('profile_liked', 'Profile liked'),
        ('new_follower', 'New follower'),
        ('new_message', 'New message'),
        ('note_copied', 'Note copied'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='接收用户',
    )
    kind = models.CharField(max_length=40, choices=KIND_CHOICES, verbose_name='通知类型')
    title = models.CharField(max_length=120, verbose_name='标题')
    body = models.TextField(blank=True, verbose_name='内容')
    data = models.JSONField(default=dict, blank=True, verbose_name='附加数据')
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'notifications_usernotification'
        verbose_name = '用户通知'
        verbose_name_plural = '用户通知'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at'], name='unotify_user_read_idx'),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.title}'
