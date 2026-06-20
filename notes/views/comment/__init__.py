"""Comment view exports split by responsibility."""
from .comments import note_comment_create_api, note_comment_delete_api, note_comments_api
from .qqmusic import (
    _compact_qqmusic_text,
    _extract_first_url,
    _extract_qqmusic_ids,
    _is_allowed_qqmusic_url,
    _resolve_qqmusic_share_payload,
    _resolve_songid_from_songmid,
    resolve_qqmusic_share_api,
)
from .reports import _report_payload, note_comment_report_api, note_report_api

__all__ = [
    'note_comments_api',
    'note_comment_create_api',
    'note_comment_delete_api',
    'note_report_api',
    'note_comment_report_api',
    'resolve_qqmusic_share_api',
    '_extract_first_url',
    '_compact_qqmusic_text',
    '_is_allowed_qqmusic_url',
    '_extract_qqmusic_ids',
    '_resolve_songid_from_songmid',
    '_resolve_qqmusic_share_payload',
    '_report_payload',
]
