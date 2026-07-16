"""Unified quick-search for the global command palette (Ctrl+K).

Searches across the resources a signed-in user can already reach — their own
notes plus notes shared with them as a collaborator, and the message groups
they belong to. It deliberately does NOT expose fuzzy user enumeration: user
lookup keeps the strict, anti-enumeration contract enforced by
``messaging.views.users.search_users_api``.
"""
from .common import *  # noqa: F401, F403


QUICK_SEARCH_LIMIT = 8


@login_required
@require_http_methods(["GET"])
def quick_search_api(request):
    """Return a compact, grouped result set for the command palette.

    Response shape::

        {
            "query": "roadmap",
            "notes": [{"id", "title", "is_public", "updated_at"}],
            "groups": [{"id", "name", "role", "avatar"}]
        }
    """
    query = (request.GET.get('q') or '').strip()
    if not query:
        return JsonResponse({'query': '', 'notes': [], 'groups': []})

    # Cap the query length so a pathological input can't build a huge ILIKE.
    query = query[:80]
    user = request.user

    notes = list(
        Note.objects.filter(
            Q(title__icontains=query) | Q(content__icontains=query),
            Q(author=user) | Q(collaborators__user=user),
            is_secret=False,
            is_trashed=False,
        )
        .distinct()
        .order_by('-updated_at')
        .values('id', 'title', 'is_public', 'updated_at')[:QUICK_SEARCH_LIMIT]
    )
    note_results = [
        {
            'id': note['id'],
            'title': note['title'],
            'is_public': note['is_public'],
            'updated_at': timezone.localtime(note['updated_at']).strftime('%Y-%m-%d %H:%M'),
        }
        for note in notes
    ]

    from messaging.models import MessageGroupMember

    memberships = (
        MessageGroupMember.objects.filter(
            user=user,
            left_at__isnull=True,
            group__is_active=True,
            group__name__icontains=query,
        )
        .select_related('group')
        .order_by('-group__updated_at')[:QUICK_SEARCH_LIMIT]
    )
    group_results = [
        {
            'id': membership.group_id,
            'name': membership.group.name,
            'role': membership.role,
            'avatar': (
                membership.group.avatar.url
                if getattr(membership.group, 'avatar', None)
                else '/static/img/default-avatar.png'
            ),
        }
        for membership in memberships
    ]

    return JsonResponse({
        'query': query,
        'notes': note_results,
        'groups': group_results,
    })
