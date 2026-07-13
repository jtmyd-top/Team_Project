"""Storage quota helpers for user-owned assets."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db.models import Count, Sum


DEFAULT_USER_STORAGE_QUOTA_BYTES = 1024 * 1024 * 1024


class StorageQuotaExceeded(Exception):
    def __init__(self, summary):
        self.summary = summary
        super().__init__('storage quota exceeded')


@dataclass(frozen=True)
class StorageUsage:
    used_bytes: int
    limit_bytes: int
    incoming_bytes: int = 0

    @property
    def remaining_bytes(self) -> int:
        return max(0, self.limit_bytes - self.used_bytes)

    @property
    def percent(self) -> int:
        if self.limit_bytes <= 0:
            return 0
        return min(100, round((self.used_bytes / self.limit_bytes) * 100))

    @property
    def will_exceed(self) -> bool:
        return self.limit_bytes > 0 and self.used_bytes + self.incoming_bytes > self.limit_bytes


def user_storage_limit_bytes(user) -> int:
    profile_limit = getattr(getattr(user, 'profile', None), 'storage_quota_bytes', None)
    if profile_limit:
        return int(profile_limit)
    return int(getattr(settings, 'USER_STORAGE_QUOTA_BYTES', DEFAULT_USER_STORAGE_QUOTA_BYTES))


def _safe_file_size(field_file) -> int:
    if not field_file:
        return 0
    try:
        return int(field_file.size or 0)
    except Exception:
        return 0


def note_assets_usage_bytes(user) -> int:
    from notes.models import Asset

    total = 0
    for asset in Asset.objects.filter(uploader=user).only('file'):
        total += _safe_file_size(asset.file)
    return total


def message_attachments_usage_bytes(user) -> int:
    from messaging.models import MessageAttachment

    return (
        MessageAttachment.objects
        .filter(uploader=user)
        .aggregate(total=Sum('size'))
        .get('total')
        or 0
    )


def owned_group_attachments_usage_bytes(user) -> int:
    from messaging.models import MessageAttachment

    return (
        MessageAttachment.objects
        .filter(group_message__group__owner=user)
        .aggregate(total=Sum('size'))
        .get('total')
        or 0
    )


def get_storage_summary(user, incoming_bytes: int = 0) -> dict:
    from messaging.models import MessageAttachment, MessageGroup
    from notes.models import Asset, Note

    note_asset_bytes = note_assets_usage_bytes(user)
    message_attachment_bytes = message_attachments_usage_bytes(user)
    used_bytes = note_asset_bytes + message_attachment_bytes
    usage = StorageUsage(
        used_bytes=used_bytes,
        limit_bytes=user_storage_limit_bytes(user),
        incoming_bytes=max(0, int(incoming_bytes or 0)),
    )
    group_usage_bytes = owned_group_attachments_usage_bytes(user)
    group_count = MessageGroup.objects.filter(owner=user, is_active=True).count()
    attachment_counts = (
        MessageAttachment.objects
        .filter(uploader=user)
        .values('attachment_type')
        .annotate(count=Count('id'), bytes=Sum('size'))
    )

    return {
        'limit_bytes': usage.limit_bytes,
        'used_bytes': usage.used_bytes,
        'remaining_bytes': usage.remaining_bytes,
        'incoming_bytes': usage.incoming_bytes,
        'percent': usage.percent,
        'will_exceed': usage.will_exceed,
        'breakdown': {
            'note_assets_bytes': note_asset_bytes,
            'message_attachments_bytes': message_attachment_bytes,
            'owned_group_attachments_bytes': group_usage_bytes,
        },
        'counts': {
            'notes': Note.objects.filter(author=user, is_trashed=False).count(),
            'secret_notes': Note.objects.filter(author=user, is_secret=True, is_trashed=False).count(),
            'note_assets': Asset.objects.filter(uploader=user).count(),
            'message_attachments': MessageAttachment.objects.filter(uploader=user).count(),
            'owned_groups': group_count,
        },
        'attachment_types': {
            row['attachment_type']: {
                'count': row['count'],
                'bytes': row['bytes'] or 0,
            }
            for row in attachment_counts
        },
    }


def lock_user_storage_quota(user) -> None:
    """Serialize quota-consuming writes for one user inside the caller's transaction.

    Usage aggregation is derived from the asset tables, so the lock must be held
    from the availability check through the Asset/MessageAttachment insert.
    Profile exists for every authenticated account and provides a stable lock row
    without introducing a second, potentially stale byte counter.
    """
    from accounts.models import Profile

    Profile.objects.select_for_update().get(user_id=user.id)


def ensure_storage_available(user, incoming_bytes: int) -> dict:
    summary = get_storage_summary(user, incoming_bytes=incoming_bytes)
    if summary['will_exceed']:
        raise StorageQuotaExceeded(summary)
    return summary


def quota_exceeded_payload(summary: dict) -> dict:
    return {
        'status': 'error',
        'code': 'storage_quota_exceeded',
        'error': '存储空间不足，请清理文件或升级配额后再上传。',
        'quota': summary,
    }
