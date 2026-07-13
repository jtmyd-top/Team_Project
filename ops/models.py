from django.conf import settings
from django.db import models


class BackupRecord(models.Model):
    KIND_SNAPSHOT = 'snapshot'
    KIND_RECOVERY_DRILL = 'recovery_drill'
    KIND_CHOICES = [
        (KIND_SNAPSHOT, 'Snapshot'),
        (KIND_RECOVERY_DRILL, 'Recovery drill'),
    ]
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_FAILED, 'Failed'),
    ]

    kind = models.CharField(max_length=24, choices=KIND_CHOICES, default=KIND_SNAPSHOT)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    storage_path = models.CharField(max_length=512, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='backup_records',
    )

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['kind', 'status', '-started_at'], name='backup_kind_status_idx'),
        ]

    def __str__(self):
        return f'{self.kind}:{self.status}:{self.started_at:%Y-%m-%d %H:%M}'
