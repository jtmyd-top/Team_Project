import json

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from ..models import UserNotification


def _bounded_int(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(maximum, max(minimum, parsed))


def _notification_payload(item):
    return {
        'id': item.id,
        'kind': item.kind,
        'title': item.title,
        'body': item.body,
        'data': item.data or {},
        'is_read': item.is_read,
        'created_at': item.created_at.isoformat(),
    }


@login_required
@require_http_methods(["GET"])
def notifications_list_api(request):
    unread = request.GET.get('unread')
    page = _bounded_int(request.GET.get('page'), 1, 1, 1000000)
    page_size = _bounded_int(request.GET.get('page_size'), 20, 1, 50)

    qs = UserNotification.objects.filter(user=request.user)
    if unread in ('1', 'true', 'yes'):
        qs = qs.filter(is_read=False)

    paginator = Paginator(qs, page_size)
    current = paginator.get_page(page)
    return JsonResponse({
        'status': 'success',
        'notifications': [_notification_payload(item) for item in current.object_list],
        'pagination': {
            'page': current.number,
            'page_size': page_size,
            'total': paginator.count,
            'total_pages': paginator.num_pages,
            'has_next': current.has_next(),
            'has_previous': current.has_previous(),
        },
        'unread_count': UserNotification.objects.filter(user=request.user, is_read=False).count(),
    })


@login_required
@require_http_methods(["GET"])
def notifications_unread_count_api(request):
    return JsonResponse({
        'status': 'success',
        'unread_count': UserNotification.objects.filter(user=request.user, is_read=False).count(),
    })


@login_required
@require_http_methods(["POST"])
def notifications_mark_read_api(request):
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    qs = UserNotification.objects.filter(user=request.user, is_read=False)
    if data.get('all'):
        updated = qs.update(is_read=True)
    else:
        ids = data.get('notification_ids') or []
        if not isinstance(ids, list):
            return JsonResponse({'error': 'notification_ids must be a list'}, status=400)
        updated = qs.filter(id__in=ids).update(is_read=True)

    return JsonResponse({
        'status': 'success',
        'updated': updated,
        'unread_count': UserNotification.objects.filter(user=request.user, is_read=False).count(),
    })
