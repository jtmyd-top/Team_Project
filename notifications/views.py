import json
from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import BrowserPushSubscription, UserNotification


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


def _push_configuration_payload(request):
    return {
        'status': 'success',
        'configured': settings.WEB_PUSH_CONFIGURED,
        'enabled': bool(
            settings.WEB_PUSH_CONFIGURED
            and BrowserPushSubscription.objects.filter(user=request.user).exists()
        ),
        'public_key': settings.VAPID_PUBLIC_KEY if settings.WEB_PUSH_CONFIGURED else '',
        'subscription_count': BrowserPushSubscription.objects.filter(user=request.user).count(),
    }


def _parse_expiration_time(value):
    if value in (None, ''):
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError('expiration_time must be a Unix timestamp in milliseconds')
    return datetime.fromtimestamp(value / 1000, tz=datetime_timezone.utc)


def _load_json_body(request):
    try:
        return json.loads(request.body) if request.body else {}
    except json.JSONDecodeError as exc:
        raise ValueError('Invalid JSON') from exc


@login_required
@require_http_methods(["GET"])
def notifications_list_api(request):
    unread = request.GET.get('unread')
    page = _bounded_int(request.GET.get('page'), 1, 1, 1000000)
    page_size = _bounded_int(request.GET.get('page_size'), 20, 1, 50)

    qs = UserNotification.objects.filter(user=request.user)
    if unread in ('1', 'true', 'yes'):
        qs = qs.filter(is_read=False)
    kind = (request.GET.get('kind') or '').strip()
    if kind:
        qs = qs.filter(kind=kind)

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
        data = _load_json_body(request)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

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


@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def push_subscriptions_api(request):
    if request.method == 'GET':
        return JsonResponse(_push_configuration_payload(request))

    try:
        data = _load_json_body(request)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    endpoint = data.get('endpoint')
    if (
        not isinstance(endpoint, str)
        or len(endpoint) > 255
        or not endpoint.startswith(('https://', 'http://'))
    ):
        return JsonResponse({'error': 'A valid push endpoint is required.'}, status=400)

    if request.method == 'DELETE':
        deleted_count, _ = BrowserPushSubscription.objects.filter(
            user=request.user,
            endpoint=endpoint,
        ).delete()
        payload = _push_configuration_payload(request)
        payload['deleted'] = bool(deleted_count)
        return JsonResponse(payload)

    if not settings.WEB_PUSH_CONFIGURED:
        return JsonResponse({
            'error': 'Browser push is not configured on this server.',
            'code': 'web_push_unavailable',
        }, status=503)

    keys = data.get('keys')
    if not isinstance(keys, dict):
        return JsonResponse({'error': 'Push subscription keys are required.'}, status=400)
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')
    if not isinstance(p256dh, str) or not p256dh or len(p256dh) > 255:
        return JsonResponse({'error': 'Invalid p256dh key.'}, status=400)
    if not isinstance(auth, str) or not auth or len(auth) > 255:
        return JsonResponse({'error': 'Invalid auth key.'}, status=400)

    try:
        expiration_time = _parse_expiration_time(data.get('expiration_time'))
    except (OverflowError, OSError, ValueError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    endpoint_owner = BrowserPushSubscription.objects.filter(endpoint=endpoint).only('user_id').first()
    if endpoint_owner and endpoint_owner.user_id != request.user.id:
        return JsonResponse(
            {'error': 'This browser push subscription is already linked to another account.'},
            status=409,
        )

    subscription, created = BrowserPushSubscription.objects.update_or_create(
        user=request.user,
        endpoint=endpoint,
        defaults={
            'user': request.user,
            'p256dh': p256dh,
            'auth': auth,
            'expiration_time': expiration_time,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:512],
        },
    )
    payload = _push_configuration_payload(request)
    payload.update({
        'subscription_id': subscription.id,
        'created': created,
    })
    return JsonResponse(payload, status=201 if created else 200)
