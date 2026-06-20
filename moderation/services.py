from django.utils.html import strip_tags


def _trim(value, limit=300):
    return (strip_tags(str(value or '')).strip())[:limit]


def note_report_snapshot(note, request=None):
    if note is None:
        return {}
    return {
        'object_type': 'note',
        'note_id': note.id,
        'title': note.title,
        'content_preview': _trim(note.content, 1000),
        'author_id': note.author_id,
        'author_username': note.author.username if getattr(note, 'author', None) else '',
        'is_public': note.is_public,
        'public_id': str(note.public_id) if note.public_id else '',
        'reported_url': getattr(request, 'build_absolute_uri', lambda: '')() if request else '',
    }


def comment_report_snapshot(comment, request=None):
    if comment is None:
        return {}
    note = getattr(comment, 'note', None)
    return {
        'object_type': 'comment',
        'comment_id': comment.id,
        'comment_content': _trim(comment.content, 1000),
        'comment_author_id': comment.author_id,
        'comment_author_username': comment.author.username if getattr(comment, 'author', None) else '',
        'comment_created_at': comment.created_at.isoformat() if getattr(comment, 'created_at', None) else '',
        'note_id': note.id if note else None,
        'note_title': note.title if note else '',
        'note_author_id': note.author_id if note else None,
        'reported_url': getattr(request, 'build_absolute_uri', lambda: '')() if request else '',
    }


def message_report_snapshot(message=None, group_message=None, request=None):
    target = group_message or message
    if target is None:
        return {}
    sender = getattr(target, 'sender', None)
    recipient = getattr(target, 'recipient', None)
    group = getattr(target, 'group', None)
    return {
        'object_type': 'group_message' if group_message else 'message',
        'message_id': getattr(target, 'id', None),
        'content_preview': _trim(getattr(target, 'content', ''), 1000),
        'sender_id': getattr(target, 'sender_id', None),
        'sender_username': sender.username if sender else '',
        'recipient_id': getattr(target, 'recipient_id', None),
        'recipient_username': recipient.username if recipient else '',
        'group_id': getattr(target, 'group_id', None),
        'group_name': group.name if group else '',
        'created_at': target.created_at.isoformat() if getattr(target, 'created_at', None) else '',
        'reported_url': getattr(request, 'build_absolute_uri', lambda: '')() if request else '',
    }


def attachment_report_snapshot(attachment, request=None):
    if attachment is None:
        return {}
    message = getattr(attachment, 'message', None)
    uploader = getattr(attachment, 'uploader', None)
    return {
        'object_type': 'attachment',
        'attachment_id': attachment.id,
        'name': attachment.original_name,
        'size': attachment.size,
        'mime_type': attachment.mime_type,
        'uploader_id': getattr(attachment, 'uploader_id', None),
        'uploader_username': uploader.username if uploader else '',
        'message_id': message.id if message else None,
        'message_preview': _trim(message.content if message else '', 500),
        'reported_url': getattr(request, 'build_absolute_uri', lambda: '')() if request else '',
    }
