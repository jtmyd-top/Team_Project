"""Moderation common list_items helpers."""
from .base import *  # noqa: F401,F403
from .reports_meta import _report_group_meta

def _message_report_list_item(r):
    data = {
        'type': 'message',
        'id': r.id,
        'status': r.status,
        'status_display': r.get_status_display(),
        'reason': r.reason,
        'reason_display': r.get_reason_display(),
        'detail': r.detail or '',
        'created_at': r.created_at.isoformat(),
        'reporter': {'id': r.reporter_id, 'username': r.reporter.username, 'avatar': _get_avatar_url(r.reporter)},
        'reported': {'id': r.reported_user_id, 'username': r.reported_user.username, 'avatar': _get_avatar_url(r.reported_user)},
        'preview': (_message_preview(r.message) if r.message else '')[:80],
    }
    data.update(_report_group_meta('message', r))
    return data

def _attachment_report_list_item(r):
    uploader = r.attachment.uploader if r.attachment else None
    data = {
        'type': 'attachment',
        'id': r.id,
        'status': r.status,
        'status_display': r.get_status_display(),
        'reason': r.reason or 'other',
        'reason_display': r.reason or '其他',
        'detail': r.detail or '',
        'created_at': r.created_at.isoformat(),
        'reporter': {'id': r.reporter_id, 'username': r.reporter.username, 'avatar': _get_avatar_url(r.reporter)},
        'reported': (
            {'id': uploader.id, 'username': uploader.username, 'avatar': _get_avatar_url(uploader)}
            if uploader else None
        ),
        'preview': f'[附件] {r.attachment.original_name}' if r.attachment else '[附件已删除]',
    }

def _note_report_list_item(r):
    note = r.note
    data = {
        'type': 'note',
        'id': r.id,
        'status': r.status,
        'status_display': r.get_status_display(),
        'reason': r.reason or 'other',
        'reason_display': r.reason or '文章举报',
        'detail': r.detail or '',
        'created_at': r.created_at.isoformat(),
        'reporter': {'id': r.reporter_id, 'username': r.reporter.username, 'avatar': _get_avatar_url(r.reporter)},
        'reported': (
            {'id': r.reported_user_id, 'username': r.reported_user.username, 'avatar': _get_avatar_url(r.reported_user)}
            if r.reported_user else None
        ),
        'preview': f'[文章] {note.title}' if note else '[文章已删除]',
    }
    data.update(_report_group_meta('note', r))
    return data
    data.update(_report_group_meta('attachment', r))
    return data

def _comment_report_list_item(r):
    comment = r.comment
    preview = strip_tags(comment.content or '')[:80] if comment else ''
    data = {
        'type': 'comment',
        'id': r.id,
        'status': r.status,
        'status_display': r.get_status_display(),
        'reason': r.reason or 'other',
        'reason_display': r.reason or '评论举报',
        'detail': r.detail or '',
        'created_at': r.created_at.isoformat(),
        'reporter': {'id': r.reporter_id, 'username': r.reporter.username, 'avatar': _get_avatar_url(r.reporter)},
        'reported': (
            {'id': r.reported_user_id, 'username': r.reported_user.username, 'avatar': _get_avatar_url(r.reported_user)}
            if r.reported_user else None
        ),
        'preview': f'[评论] {preview}' if preview else '[评论已删除]',
    }
    data.update(_report_group_meta('comment', r))
    return data

__all__ = [
    '_message_report_list_item',
    '_attachment_report_list_item',
    '_note_report_list_item',
    '_comment_report_list_item',
]
