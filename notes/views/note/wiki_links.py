"""Wiki-style bidirectional links between notes (``[[Note title]]``).

A note can reference another note by writing ``[[Some title]]`` in its body.
This module resolves those references against the notes a signed-in user can
already reach (their own notes plus notes shared with them as a collaborator,
never secret or trashed ones) and computes the reverse relation — the
*backlinks* — so a note can show "what links here".

Resolution is title-based and case-insensitive. Only titles that resolve to
exactly one accessible note are treated as a live link; ambiguous or missing
targets are reported as unresolved so the UI can render them differently.
"""
from __future__ import annotations

import re

from .common import *  # noqa: F401, F403


# ``[[ ... ]]`` where the inner text has no newline and no nested brackets.
WIKI_LINK_PATTERN = re.compile(r'\[\[([^\[\]\n]{1,255}?)\]\]')

# Cap how many links we resolve per note so a pathological body can't fan out
# into an unbounded number of title lookups.
MAX_WIKI_LINKS = 50
MAX_BACKLINKS = 50


def extract_wiki_link_titles(content):
    """Return the ordered, de-duplicated list of ``[[title]]`` targets.

    ``content`` is note HTML. We strip tags first so bracket syntax that lives
    in text (not inside an attribute) is what gets matched, then collapse
    duplicates while preserving first-seen order.
    """
    if not content:
        return []
    text = BeautifulSoup(content, 'html.parser').get_text('\n')
    seen = set()
    titles = []
    for match in WIKI_LINK_PATTERN.finditer(text):
        title = match.group(1).strip()
        if not title:
            continue
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        titles.append(title)
        if len(titles) >= MAX_WIKI_LINKS:
            break
    return titles


def _accessible_notes_queryset(user):
    """Notes the user may read for the purpose of link resolution.

    Own notes and notes shared as a collaborator, excluding secret and trashed
    notes. Secret notes are intentionally never linkable — their titles are
    server-visible but their existence should not leak through backlinks.
    """
    return (
        Note.objects.filter(
            Q(author=user) | Q(collaborators__user=user),
            is_secret=False,
            is_trashed=False,
        )
        .distinct()
    )


def _resolve_titles(user, titles):
    """Map each requested title to a resolved note or an unresolved marker.

    Returns ``(resolved, unresolved)`` where ``resolved`` is a list of
    ``{title, id, note_title, is_public}`` and ``unresolved`` is a list of the
    raw titles that matched zero or more-than-one accessible note.
    """
    resolved = []
    unresolved = []
    if not titles:
        return resolved, unresolved

    accessible = _accessible_notes_queryset(user)
    for title in titles:
        matches = list(
            accessible.filter(title__iexact=title)
            .order_by('-updated_at')
            .values('id', 'title', 'is_public')[:2]
        )
        if len(matches) == 1:
            note = matches[0]
            resolved.append({
                'title': title,
                'id': note['id'],
                'note_title': note['title'],
                'is_public': note['is_public'],
            })
        else:
            # Zero matches, or ambiguous (multiple notes share the title).
            unresolved.append(title)
    return resolved, unresolved


def _find_backlinks(user, note):
    """Accessible notes whose body contains ``[[<this note's title>]]``.

    The ``icontains`` filter is a cheap pre-filter; we then confirm with the
    parsed link titles so a substring match inside prose ("see [[Roadmap
    2025]]") does not falsely link to a note titled "Roadmap".
    """
    title = (note.title or '').strip()
    if not title:
        return []

    needle = '[[%s' % title  # opening bracket + title; refine below
    candidates = (
        _accessible_notes_queryset(user)
        .exclude(pk=note.pk)
        .filter(content__icontains=needle)
        .order_by('-updated_at')
        .values('id', 'title', 'is_public', 'content')[:MAX_BACKLINKS * 2]
    )

    target = title.casefold()
    backlinks = []
    for candidate in candidates:
        link_titles = {t.casefold() for t in extract_wiki_link_titles(candidate['content'])}
        if target in link_titles:
            backlinks.append({
                'id': candidate['id'],
                'title': candidate['title'],
                'is_public': candidate['is_public'],
            })
            if len(backlinks) >= MAX_BACKLINKS:
                break
    return backlinks


@login_required
@require_http_methods(["GET"])
def note_links_api(request, note_id):
    """Return outgoing wiki-links and backlinks for a note.

    Response shape::

        {
            "outgoing": {
                "resolved": [{"title", "id", "note_title", "is_public"}],
                "unresolved": ["Some missing title"]
            },
            "backlinks": [{"id", "title", "is_public"}]
        }

    Requires read permission on the note. Secret notes never participate in
    the wiki-link graph, so a request for one returns 400.
    """
    note = get_object_or_404(Note, id=note_id, is_trashed=False)

    if note.is_secret:
        return JsonResponse({'error': '保密笔记不支持双向链接'}, status=400)

    if not note.has_read_permission(request.user):
        return JsonResponse({'error': '无权访问该笔记'}, status=403)

    titles = extract_wiki_link_titles(note.content)
    resolved, unresolved = _resolve_titles(request.user, titles)
    backlinks = _find_backlinks(request.user, note)

    return JsonResponse({
        'outgoing': {
            'resolved': resolved,
            'unresolved': unresolved,
        },
        'backlinks': backlinks,
    })
