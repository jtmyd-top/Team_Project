import json
import logging

from django.conf import settings
from django.db import transaction

from core.realtime import push_user_event
from notifications.models import BrowserPushSubscription, UserNotification


logger = logging.getLogger(__name__)


def _notification_url(notification):
    data = notification.data or {}
    url = data.get('url')
    if isinstance(url, str) and url.startswith('/'):
        return url
    if data.get('note_id'):
        return f'/knowledge/?note={data["note_id"]}'
    if data.get('group_id') or data.get('message_id') or notification.kind == 'new_message':
        return '/messages/'
    return '/'


def _push_is_enabled_for_user(user, notification):
    if notification.kind != 'new_message' or not settings.WEB_PUSH_CONFIGURED:
        return False

    try:
        from messaging.models import MessagePreference

        preference = MessagePreference.objects.filter(user=user).only(
            'browser_new_message'
        ).first()
    except Exception:
        logger.exception('Unable to read browser push preference for user %s', user.id)
        return False

    return bool(preference and preference.browser_new_message)


def _delete_expired_subscription(subscription):
    BrowserPushSubscription.objects.filter(
        id=subscription.id,
        endpoint=subscription.endpoint,
    ).delete()


def _send_browser_pushes(notification_id):
    """Deliver a persisted notification only after its creating transaction committed."""
    notification = (
        UserNotification.objects
        .select_related('user')
        .filter(id=notification_id)
        .first()
    )
    if notification is None or not _push_is_enabled_for_user(notification.user, notification):
        return

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning('pywebpush is not installed; browser push is unavailable.')
        return

    payload = json.dumps({
        'title': notification.title,
        'body': notification.body,
        'url': _notification_url(notification),
        'tag': f'notification-{notification.id}',
    })
    subscriptions = BrowserPushSubscription.objects.filter(user=notification.user)
    for subscription in subscriptions.iterator():
        try:
            webpush(
                subscription_info={
                    'endpoint': subscription.endpoint,
                    'keys': {
                        'p256dh': subscription.p256dh,
                        'auth': subscription.auth,
                    },
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={'sub': settings.VAPID_SUBJECT},
                ttl=max(0, settings.WEB_PUSH_TTL_SECONDS),
            )
        except WebPushException as exc:
            status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
            if status_code in (404, 410):
                _delete_expired_subscription(subscription)
            else:
                logger.warning(
                    'Browser push failed for subscription %s: %s',
                    subscription.id,
                    exc,
                )
        except Exception:
            logger.exception(
                'Unexpected browser push failure for subscription %s',
                subscription.id,
            )


def _realtime_notification_payload(notification):
    return {
        'id': notification.id,
        'kind': notification.kind,
        'title': notification.title,
        'body': notification.body,
        'data': notification.data or {},
        'is_read': notification.is_read,
        'created_at': notification.created_at.isoformat(),
    }


def _push_realtime_notification(notification_id):
    """事务提交后向用户的 WebSocket 组推送通知事件。"""
    notification = UserNotification.objects.filter(id=notification_id).first()
    if notification is None:
        return
    unread_count = UserNotification.objects.filter(
        user_id=notification.user_id,
        is_read=False,
    ).count()
    push_user_event(notification.user_id, {
        'type': 'notification',
        'notification': _realtime_notification_payload(notification),
        'unread_count': unread_count,
    })


def notify_user(user, kind, title, body='', **data):
    if user is None or not getattr(user, 'id', None):
        return None

    notification = UserNotification.objects.create(
        user=user,
        kind=kind,
        title=title[:120],
        body=(body or '')[:2000],
        data=data or {},
    )
    transaction.on_commit(lambda: _push_realtime_notification(notification.id))
    if _push_is_enabled_for_user(user, notification):
        transaction.on_commit(lambda: _send_browser_pushes(notification.id))
    return notification
