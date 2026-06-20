"""Group common audit helpers."""
from .base import *  # noqa: F401,F403
from .users import _user_payload

def _create_group_audit_log(group, actor, action, target_user=None, metadata=None):
    try:
        from messaging.models import MessageGroupAuditLog
        MessageGroupAuditLog.objects.create(
            group=group,
            actor=actor if getattr(actor, 'is_authenticated', False) else None,
            target_user=target_user,
            action=action,
            metadata=metadata or {},
        )
    except Exception:
        logger.warning('写入群组审计日志失败: group=%s action=%s', getattr(group, 'id', None), action, exc_info=True)

def _parse_expires_at(value):
    if value in (None, '', False):
        return None
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed
    return None

def _invite_link_payload(link, request=None):
    path = f"/messages/?group_invite={link.token}"
    use_records = getattr(link, 'prefetched_use_records', None)
    if use_records is None:
        use_records = list(
            link.use_records.select_related('user').order_by('-created_at')[:10]
        ) if getattr(link, 'id', None) else []
    return {
        'id': link.id,
        'token': link.token,
        'url': request.build_absolute_uri(path) if request else path,
        'created_by': link.created_by.username if link.created_by else None,
        'created_at': link.created_at.isoformat() if link.created_at else None,
        'expires_at': link.expires_at.isoformat() if link.expires_at else None,
        'max_uses': link.max_uses,
        'uses_count': link.uses_count,
        'revoked_at': link.revoked_at.isoformat() if link.revoked_at else None,
        'is_active': link.is_valid(),
        'recent_uses': [_invite_use_payload(record) for record in use_records],
    }

def _invite_use_payload(record):
    return {
        'id': record.id,
        'user': _user_payload(record.user),
        'created_at': record.created_at.isoformat() if record.created_at else None,
    }

def _extract_links_from_text(text):
    pattern = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
    links = []
    for match in pattern.finditer(text or ''):
        url = match.group(0).rstrip('.,;!?)]}')
        if url and url not in links:
            links.append(url)
    return links

__all__ = [
    '_create_group_audit_log',
    '_parse_expires_at',
    '_invite_link_payload',
    '_invite_use_payload',
    '_extract_links_from_text',
]
