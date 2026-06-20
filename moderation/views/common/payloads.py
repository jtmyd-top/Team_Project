"""Moderation common payloads helpers."""
from .base import *  # noqa: F401,F403

def _sanction_payload(s):
    pending_appeal = None
    try:
        appeal = s.appeals.filter(status='pending').order_by('-created_at').first()
        if appeal:
            pending_appeal = {
                'id': appeal.id,
                'reason': appeal.reason,
                'created_at': appeal.created_at.isoformat(),
            }
    except Exception:
        pending_appeal = None
    return {
        'id': s.id,
        'type': s.sanction_type,
        'type_display': s.get_sanction_type_display(),
        'expires_at': s.expires_at.isoformat() if s.expires_at else None,
        'is_permanent': s.is_permanent,
        'reason': s.reason or '',
        'created_at': s.created_at.isoformat(),
        'created_by': s.created_by.username if s.created_by else '',
        'pending_appeal': pending_appeal,
    }

def _user_card(user):
    """被举报者 / 举报者的内联卡片信息（含统计、既往举报、现有制裁）。"""
    if user is None:
        return None
    from moderation.models import AttachmentReport, CommentReport, MessageReport, NoteReport, UserSanction
    from notes.models import Note

    profile = getattr(user, 'profile', None)
    reports_filed = MessageReport.objects.filter(reporter=user).count()
    reports_received = (
        MessageReport.objects.filter(reported_user=user).count()
        + AttachmentReport.objects.filter(attachment__uploader=user).count()
        + NoteReport.objects.filter(reported_user=user).count()
        + CommentReport.objects.filter(reported_user=user).count()
    )
    notes_count = Note.objects.filter(author=user, is_public=True).count()

    sanctions = [
        _sanction_payload(s)
        for s in UserSanction.objects.filter(user=user, is_active=True).order_by('-created_at')
        if s.is_effective
    ]

    return {
        'id': user.id,
        'username': user.username,
        'avatar': _get_avatar_url(user),
        'bio': (getattr(profile, 'bio', '') or '') if profile else '',
        'email': user.email or '',
        'is_active': user.is_active,
        'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        'notes_count': notes_count,
        'reports_filed': reports_filed,
        'reports_received': reports_received,
        'active_sanctions': sanctions,
    }

def _attachment_brief(attachment, *, with_preview=False):
    if attachment is None:
        return None
    data = {
        'id': attachment.id,
        'type': attachment.attachment_type,
        'name': attachment.original_name,
        'mime_type': attachment.mime_type,
        'size': attachment.size,
        'was_reported': attachment.was_reported,
    }
    if with_preview:
        # 仅管理员可访问的内联预览端点
        data['preview_url'] = f'/api/moderation/attachments/{attachment.id}/file/'
    return data

def _message_context_payload(message):
    """给定违规消息，返回该会话中其前后若干条消息（管理员视角，包含已删除/已撤回）。"""
    from messaging.models import Message

    if message is None:
        return []
    a, b = message.sender_id, message.recipient_id
    convo = Message.objects.filter(
        Q(sender_id=a, recipient_id=b) | Q(sender_id=b, recipient_id=a)
    ).select_related('sender', 'recipient').prefetch_related('attachments').order_by('created_at')

    ids = list(convo.values_list('id', flat=True))
    try:
        idx = ids.index(message.id)
    except ValueError:
        idx = None

    if idx is None:
        window = list(convo)[-CONTEXT_WINDOW:]
    else:
        start = max(0, idx - CONTEXT_WINDOW)
        end = idx + CONTEXT_WINDOW + 1
        window = list(convo)[start:end]

    return [_context_message_payload(m, highlight_id=message.id) for m in window]

def _context_message_payload(m, highlight_id=None):
    merged_forward = _parse_merged_forward(m.content)
    return {
        'id': m.id,
        'sender': m.sender.username,
        'sender_id': m.sender_id,
        'recipient': m.recipient.username,
        'recipient_id': m.recipient_id,
        'content': m.content,
        'merged_forward': merged_forward,
        'created_at': m.created_at.isoformat(),
        'is_recalled': m.is_recalled,
        'deleted_for_sender': m.deleted_for_sender,
        'deleted_for_recipient': m.deleted_for_recipient,
        'is_highlight': (m.id == highlight_id),
        'attachments': [_attachment_brief(a, with_preview=True) for a in m.attachments.all()],
    }

__all__ = [
    '_sanction_payload',
    '_user_card',
    '_attachment_brief',
    '_message_context_payload',
    '_context_message_payload',
]
