"""Note share management APIs."""

import json

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ._helpers import _get_avatar_url


def _bounded_int(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(maximum, max(minimum, parsed))


def _user_payload(user):
    return {
        'id': user.id,
        'username': user.username,
        'avatar': _get_avatar_url(user),
    }


def _group_avatar_url(group):
    if getattr(group, 'avatar', None):
        try:
            return group.avatar.url
        except Exception:
            pass
    return '/static/img/default-avatar.png'


def _note_payload(note, title_snapshot=''):
    return {
        'id': note.id,
        'title': title_snapshot or note.title or '未命名笔记',
        'is_public': note.is_public,
        'is_secret': note.is_secret,
        'is_trashed': note.is_trashed,
    }


def _direct_share_payload(share):
    read_records = list(share.read_records.all())
    last_read_at = max(
        (record.last_read_at for record in read_records if record.last_read_at),
        default=None,
    )
    return {
        'id': share.id,
        'scope': 'direct',
        'note': _note_payload(share.note, share.title_snapshot),
        'target': {
            'type': 'user',
            'id': share.recipient_id,
            'name': share.recipient.username,
            'avatar': _get_avatar_url(share.recipient),
        },
        'message_id': share.message_id,
        'created_at': share.created_at.isoformat() if share.created_at else None,
        'revoked_at': share.revoked_at.isoformat() if share.revoked_at else None,
        'is_revoked': share.revoked_at is not None,
        'allow_forwarding': share.allow_forwarding,
        'read_count': len(read_records),
        'view_count': sum(record.view_count for record in read_records),
        'last_read_at': last_read_at.isoformat() if last_read_at else None,
        'access_url': f'/api/messages/note-shares/{share.id}/',
        'view_url': f'/messages/note-shares/{share.id}/view/',
    }


def _group_share_payload(share):
    read_records = list(share.read_records.all())
    last_read_at = max(
        (record.last_read_at for record in read_records if record.last_read_at),
        default=None,
    )
    return {
        'id': share.id,
        'scope': 'group',
        'note': _note_payload(share.note, share.title_snapshot),
        'target': {
            'type': 'group',
            'id': share.group_id,
            'name': share.group.name,
            'avatar': _group_avatar_url(share.group),
        },
        'message_id': share.message_id,
        'created_at': share.created_at.isoformat() if share.created_at else None,
        'revoked_at': share.revoked_at.isoformat() if share.revoked_at else None,
        'is_revoked': share.revoked_at is not None,
        'allow_forwarding': share.allow_forwarding,
        'read_count': len(read_records),
        'view_count': sum(record.view_count for record in read_records),
        'last_read_at': last_read_at.isoformat() if last_read_at else None,
        'access_url': f'/api/messages/groups/{share.group_id}/note-shares/{share.id}/',
        'view_url': f'/messages/groups/{share.group_id}/note-shares/{share.id}/view/',
    }


@require_http_methods(["GET"])
@login_required
def list_note_shares_api(request):
    from messaging.models import DirectNoteShare, GroupNoteShare

    status = (request.GET.get('status') or '').strip()
    scope = (request.GET.get('scope') or '').strip()
    page = _bounded_int(request.GET.get('page'), 1, 1, 1000000)
    page_size = _bounded_int(request.GET.get('page_size'), 30, 1, 100)

    shares = []
    if scope in ('', 'direct'):
        direct_qs = DirectNoteShare.objects.filter(shared_by=request.user).select_related(
            'note',
            'recipient',
            'message',
        ).prefetch_related('read_records__reader')
        if status == 'active':
            direct_qs = direct_qs.filter(revoked_at__isnull=True, note__is_trashed=False)
        elif status == 'revoked':
            direct_qs = direct_qs.filter(revoked_at__isnull=False)
        shares.extend(_direct_share_payload(item) for item in direct_qs[:500])

    if scope in ('', 'group'):
        group_qs = GroupNoteShare.objects.filter(shared_by=request.user).select_related(
            'note',
            'group',
            'message',
        ).prefetch_related('read_records__reader')
        if status == 'active':
            group_qs = group_qs.filter(revoked_at__isnull=True, note__is_trashed=False)
        elif status == 'revoked':
            group_qs = group_qs.filter(revoked_at__isnull=False)
        shares.extend(_group_share_payload(item) for item in group_qs[:500])

    shares.sort(key=lambda item: item.get('created_at') or '', reverse=True)
    paginator = Paginator(shares, page_size)
    current = paginator.get_page(page)
    return JsonResponse({
        'status': 'success',
        'shares': list(current.object_list),
        'pagination': {
            'page': current.number,
            'page_size': page_size,
            'total': paginator.count,
            'total_pages': paginator.num_pages,
            'has_next': current.has_next(),
            'has_previous': current.has_previous(),
        },
    })


@require_http_methods(["POST"])
@login_required
def revoke_note_share_api(request, scope, share_id):
    from messaging.models import DirectNoteShare, GroupNoteShare

    if scope == 'direct':
        share = get_object_or_404(DirectNoteShare, id=share_id, shared_by=request.user)
    elif scope == 'group':
        share = get_object_or_404(GroupNoteShare, id=share_id, shared_by=request.user)
    else:
        return JsonResponse({'error': '无效的分享类型'}, status=400)

    if share.revoked_at is None:
        share.revoked_at = timezone.now()
        share.save(update_fields=['revoked_at'])

    return JsonResponse({
        'status': 'success',
        'share': _direct_share_payload(share) if scope == 'direct' else _group_share_payload(share),
    })


def _get_owned_share(scope, share_id, user):
    from messaging.models import DirectNoteShare, GroupNoteShare

    if scope == 'direct':
        return get_object_or_404(
            DirectNoteShare.objects.select_related('note', 'recipient').prefetch_related(
                'read_records__reader'
            ),
            id=share_id,
            shared_by=user,
        )
    if scope == 'group':
        return get_object_or_404(
            GroupNoteShare.objects.select_related('note', 'group').prefetch_related(
                'read_records__reader'
            ),
            id=share_id,
            shared_by=user,
        )
    return None


@require_http_methods(["POST"])
@login_required
def update_note_share_forwarding_api(request, scope, share_id):
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)

    allow_forwarding = payload.get('allow_forwarding')
    if not isinstance(allow_forwarding, bool):
        return JsonResponse({'error': 'allow_forwarding 必须为布尔值'}, status=400)

    share = _get_owned_share(scope, share_id, request.user)
    if share is None:
        return JsonResponse({'error': '无效的分享类型'}, status=400)

    share.allow_forwarding = allow_forwarding
    share.save(update_fields=['allow_forwarding'])
    return JsonResponse({
        'status': 'success',
        'share': _direct_share_payload(share) if scope == 'direct' else _group_share_payload(share),
    })


@require_http_methods(["GET"])
@login_required
def list_note_share_reads_api(request, scope, share_id):
    share = _get_owned_share(scope, share_id, request.user)
    if share is None:
        return JsonResponse({'error': '无效的分享类型'}, status=400)

    records = [
        {
            'user': _user_payload(record.reader),
            'view_count': record.view_count,
            'first_read_at': record.first_read_at.isoformat() if record.first_read_at else None,
            'last_read_at': record.last_read_at.isoformat() if record.last_read_at else None,
        }
        for record in share.read_records.all()
    ]
    records.sort(key=lambda item: item['last_read_at'] or '', reverse=True)
    return JsonResponse({
        'status': 'success',
        'scope': scope,
        'share_id': share.id,
        'read_count': len(records),
        'view_count': sum(record.view_count for record in share.read_records.all()),
        'reads': records,
    })
