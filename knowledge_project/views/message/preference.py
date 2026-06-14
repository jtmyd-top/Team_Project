# knowledge_project/views/message/preference.py
"""私信偏好 / 屏蔽 / 账户可发现性"""
import json
from datetime import time

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from ._helpers import _get_avatar_url, _server_error_response


def _parse_quiet_time(value):
    if value in (None, ''):
        return None
    if not isinstance(value, str):
        raise ValueError('time must be a string')
    parsed = time.fromisoformat(value)
    return parsed.replace(second=0, microsecond=0)


def _available_email_mention_groups(user):
    from ...models import MessageGroup

    return (
        MessageGroup.objects
        .filter(is_active=True)
        .filter(
            Q(owner=user) |
            Q(memberships__user=user, memberships__left_at__isnull=True)
        )
        .distinct()
        .order_by('name', 'id')
    )


def _email_mention_group_payload(group):
    return {
        'id': group.id,
        'name': group.name,
    }


@require_http_methods(["GET"])
@login_required
def get_message_preference_api(request):
    """获取用户的私信偏好设置"""
    try:
        from ...models import MessagePreference

        target_user_id = request.GET.get('user_id')
        if target_user_id:
            target_user = get_object_or_404(User, id=target_user_id)
            pref, _ = MessagePreference.objects.get_or_create(user=target_user)
        else:
            pref, _ = MessagePreference.objects.get_or_create(user=request.user)

        preference = {
            'allow_messages': pref.allow_messages,
            'message_mode': pref.message_mode,
            'show_read_status': pref.show_read_status,
            'auto_reply_enabled': pref.auto_reply_enabled,
            'auto_reply_text': pref.auto_reply_text,
            'notify_new_message': pref.notify_new_message,
            'browser_new_message': pref.browser_new_message,
            'quiet_hours_enabled': pref.quiet_hours_enabled,
            'quiet_hours_start': pref.quiet_hours_start.strftime('%H:%M') if pref.quiet_hours_start else '',
            'quiet_hours_end': pref.quiet_hours_end.strftime('%H:%M') if pref.quiet_hours_end else '',
        }
        if pref.user_id == request.user.id:
            available_groups = list(_available_email_mention_groups(request.user))
            available_group_ids = [group.id for group in available_groups]
            selected_ids = list(
                pref.email_mention_groups
                .filter(id__in=available_group_ids)
                .values_list('id', flat=True)
            )
            preference.update({
                'notify_group_mentions_email': pref.notify_group_mentions_email,
                'email_mention_group_ids': selected_ids,
                'available_email_mention_groups': [
                    _email_mention_group_payload(group)
                    for group in available_groups
                ],
            })

        return JsonResponse({
            'status': 'success',
            'preference': preference,
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取私信设置错误', e)


@require_http_methods(["POST"])
@login_required
def update_message_preference_api(request):
    """更新用户的私信偏好设置"""
    try:
        from ...models import MessagePreference
        data = json.loads(request.body)
        pref, _ = MessagePreference.objects.get_or_create(user=request.user)
        if 'allow_messages' in data:
            pref.allow_messages = data['allow_messages']
        if 'message_mode' in data and data['message_mode'] in ['all', 'followers_only', 'following_only', 'disabled']:
            pref.message_mode = data['message_mode']
        if 'show_read_status' in data:
            pref.show_read_status = data['show_read_status']
        if 'auto_reply_enabled' in data:
            pref.auto_reply_enabled = data['auto_reply_enabled']
        if 'auto_reply_text' in data:
            pref.auto_reply_text = data['auto_reply_text'][:500]
        if 'notify_new_message' in data:
            pref.notify_new_message = bool(data['notify_new_message'])
        if 'browser_new_message' in data:
            pref.browser_new_message = bool(data['browser_new_message'])
        if 'notify_group_mentions_email' in data:
            pref.notify_group_mentions_email = bool(data['notify_group_mentions_email'])
        if 'quiet_hours_enabled' in data:
            pref.quiet_hours_enabled = bool(data['quiet_hours_enabled'])
        if 'quiet_hours_start' in data:
            try:
                pref.quiet_hours_start = _parse_quiet_time(data.get('quiet_hours_start'))
            except ValueError:
                return JsonResponse({'error': 'quiet_hours_start must be HH:MM'}, status=400)
        if 'quiet_hours_end' in data:
            try:
                pref.quiet_hours_end = _parse_quiet_time(data.get('quiet_hours_end'))
            except ValueError:
                return JsonResponse({'error': 'quiet_hours_end must be HH:MM'}, status=400)
        pref.save()
        if 'email_mention_group_ids' in data:
            raw_group_ids = data.get('email_mention_group_ids') or []
            if not isinstance(raw_group_ids, list):
                return JsonResponse({'error': 'email_mention_group_ids 必须是数组'}, status=400)
            try:
                group_ids = {int(group_id) for group_id in raw_group_ids}
            except (TypeError, ValueError):
                return JsonResponse({'error': '群组选择参数无效'}, status=400)
            available_ids = set(_available_email_mention_groups(request.user).values_list('id', flat=True))
            if not group_ids.issubset(available_ids):
                return JsonResponse({'error': '只能选择你加入或创建的群组'}, status=400)
            pref.email_mention_groups.set(group_ids)
        return JsonResponse({'status': 'success', 'message': '设置已更新'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新私信设置错误', e)


@require_http_methods(["POST"])
@login_required
def block_user_api(request):
    """屏蔽用户"""
    try:
        from ...models import UserBlocklist
        data = json.loads(request.body)
        blocked_user_id = data.get('user_id')
        reason = data.get('reason', '')
        if not blocked_user_id:
            return JsonResponse({'error': '缺少user_id参数'}, status=400)
        blocked_user = get_object_or_404(User, id=blocked_user_id)
        if blocked_user == request.user:
            return JsonResponse({'error': '无法屏蔽自己'}, status=400)
        blocklist, created = UserBlocklist.objects.get_or_create(
            user=request.user, blocked_user=blocked_user, defaults={'reason': reason}
        )
        if not created:
            blocklist.reason = reason
            blocklist.save()
        return JsonResponse({'status': 'success', 'message': '已屏蔽用户'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('屏蔽用户错误', e)


@require_http_methods(["POST"])
@login_required
def unblock_user_api(request):
    """取消屏蔽"""
    try:
        from ...models import UserBlocklist
        data = json.loads(request.body)
        blocked_user_id = data.get('user_id')
        if not blocked_user_id:
            return JsonResponse({'error': '缺少user_id参数'}, status=400)
        UserBlocklist.objects.filter(
            user=request.user, blocked_user_id=blocked_user_id
        ).delete()
        return JsonResponse({'status': 'success', 'message': '已取消屏蔽'})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('取消屏蔽错误', e)


@require_http_methods(["GET"])
@login_required
def get_blocked_users_api(request):
    """获取屏蔽列表"""
    try:
        from ...models import UserBlocklist
        blocked = UserBlocklist.objects.filter(user=request.user).select_related('blocked_user')
        blocked_list = []
        for item in blocked:
            blocked_list.append({
                'id': item.blocked_user.id,
                'username': item.blocked_user.username,
                'avatar_url': _get_avatar_url(item.blocked_user),
                'avatar': _get_avatar_url(item.blocked_user),
                'blocked_at': item.created_at.strftime('%Y-%m-%d') if hasattr(item, 'created_at') and item.created_at else None,
                'reason': item.reason,
            })
        return JsonResponse({'status': 'success', 'blocked_users': blocked_list})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取屏蔽列表错误', e)


@require_http_methods(["GET", "POST"])
@login_required
def update_discoverability_api(request):
    """账户可发现性开关 + search_code 管理

    GET : 读取当前开关与 search_code
    POST: body {discoverable_by_username?, discoverable_by_email?, regenerate_code?}
    """
    import secrets
    import string
    from ...models import Profile

    profile = request.user.profile

    if request.method == 'GET':
        return JsonResponse({
            'status': 'success',
            'discoverable_by_username': profile.discoverable_by_username,
            'discoverable_by_email': profile.discoverable_by_email,
            'search_code': profile.search_code or '',
        })

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)

    update_fields = []
    if 'discoverable_by_username' in data:
        profile.discoverable_by_username = bool(data['discoverable_by_username'])
        update_fields.append('discoverable_by_username')
    if 'discoverable_by_email' in data:
        profile.discoverable_by_email = bool(data['discoverable_by_email'])
        update_fields.append('discoverable_by_email')

    if data.get('regenerate_code'):
        abc = string.ascii_uppercase + string.digits
        for _ in range(8):
            code = ''.join(secrets.choice(abc) for _ in range(8))
            if not Profile.objects.filter(search_code=code).exclude(pk=profile.pk).exists():
                profile.search_code = code
                update_fields.append('search_code')
                break
        else:
            return JsonResponse({'error': '生成搜索短码失败，请稍后重试'}, status=500)

    if update_fields:
        profile.save(update_fields=update_fields)

    return JsonResponse({
        'status': 'success',
        'discoverable_by_username': profile.discoverable_by_username,
        'discoverable_by_email': profile.discoverable_by_email,
        'search_code': profile.search_code or '',
    })
