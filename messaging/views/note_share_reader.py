"""Shared note reader rendering for message note shares."""

import nh3
from django.shortcuts import render


NOTE_CONTENT_TAGS = set(nh3.ALLOWED_TAGS).union({
    'article',
    'aside',
    'br',
    'code',
    'div',
    'figcaption',
    'figure',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'mark',
    'p',
    'pre',
    'section',
    'span',
    's',
    'sub',
    'sup',
})

NOTE_CONTENT_ATTRIBUTES = {
    **nh3.ALLOWED_ATTRIBUTES,
    '*': {'class', 'title'},
    'a': {'href', 'hreflang', 'title', 'target'},
    'img': {'alt', 'src', 'align', 'width', 'height', 'title'},
}


def _clean_note_html(content):
    html = content or '<p>暂无内容</p>'
    return nh3.clean(
        html,
        tags=NOTE_CONTENT_TAGS,
        attributes=NOTE_CONTENT_ATTRIBUTES,
        link_rel='noopener noreferrer',
        url_schemes={'http', 'https', 'mailto', 'tel', 'data'},
    )


def render_note_share_reader(request, note, share_context, status=200):
    """Render a permission-checked note share in a standalone browser page."""
    context = {
        'note': {
            'id': note.id,
            'title': note.title or '未命名笔记',
            'created_at': note.created_at,
            'updated_at': note.updated_at,
            'is_public': note.is_public,
        },
        'share': share_context,
        'note_content': _clean_note_html(note.content),
        'error_message': '',
    }
    return render(request, 'messages/note_share_reader.html', context, status=status)


def render_note_share_error(request, message, status=404):
    return render(
        request,
        'messages/note_share_reader.html',
        {'error_message': message, 'note': None, 'share': None, 'note_content': ''},
        status=status,
    )
