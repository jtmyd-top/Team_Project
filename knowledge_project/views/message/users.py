# knowledge_project/views/message/users.py
"""公开资料 / 精准用户搜索 / 私信页 / 未读数 / 在线心跳"""
import os
import time

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from urllib.parse import quote

from ...models import Note, ProfileLike
from ...utils.session_activity import mark_messages_page_activity
from ._constants import MESSAGES_PAGE_ACTIVE_AT_KEY
from ._helpers import _get_avatar_url, _server_error_response


@require_http_methods(["GET"])
def get_user_public_profile_api(request, user_id):
    try:
        user = get_object_or_404(User, id=user_id)
        profile = user.profile
        notes_count = Note.objects.filter(author=user, is_public=True).count()
        views_count = Note.objects.filter(author=user, is_public=True).aggregate(
            total_views=models.Sum('views')
        )['total_views'] or 0
        likes_count = ProfileLike.objects.filter(profile=profile).count()
        banner_url = profile.banner_image.url if profile.banner_image else ''
        banner_is_video = bool(banner_url.lower().split('?', 1)[0].endswith(('.mp4', '.webm', '.ogg')))
        return JsonResponse({
            'status': 'success',
            'id': user.id,
            'username': user.username,
            'avatar': _get_avatar_url(user),
            'banner_url': banner_url,
            'banner_is_video': banner_is_video,
            'bio': profile.bio or '',
            'notes_count': notes_count,
            'views_count': views_count,
            'likes_count': likes_count,
            'public_notes_url': f'/?author={user.id}&author_name={quote(user.username)}',
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取用户信息错误', e)


@require_http_methods(["GET"])
def search_users_api(request):
    """精准搜索（防用户枚举）

    三路 iexact 精准匹配：username / email / search_code
    不做模糊搜索、不返回前缀建议、空结果统一返回 {'users': []}
    被搜索方的 discoverable_by_username / discoverable_by_email 开关控制是否可被检索到；
    search_code 属于主动分享的公开短码，无需额外开关即可命中。
    """
    try:
        from ...models import Profile

        query = (request.GET.get('q') or '').strip()
        if len(query) < 3 or len(query) > 254:
            return JsonResponse({'users': []})

        viewer_id = request.user.id if request.user.is_authenticated else None
        found = None
        via = None

        # 1. search_code（8 位大写字母数字，优先匹配且无需开关）
        candidate_code = query.upper()
        if 6 <= len(candidate_code) <= 12 and candidate_code.isalnum():
            try:
                profile = Profile.objects.select_related('user').get(search_code=candidate_code)
                found = profile.user
                via = 'code'
            except Profile.DoesNotExist:
                pass

        # 2. username iexact（尊重 discoverable_by_username）
        if not found:
            try:
                candidate = User.objects.select_related('profile').get(username__iexact=query)
                if getattr(candidate.profile, 'discoverable_by_username', False):
                    found = candidate
                    via = 'username'
            except User.DoesNotExist:
                pass

        # 3. email iexact（尊重 discoverable_by_email，且必须形如邮箱）
        if not found and '@' in query:
            try:
                candidate = User.objects.select_related('profile').get(email__iexact=query)
                if getattr(candidate.profile, 'discoverable_by_email', False):
                    found = candidate
                    via = 'email'
            except User.DoesNotExist:
                pass

        # 不能搜到自己、不能搜到被搜到者已屏蔽 viewer 的情况
        if found and viewer_id and found.id == viewer_id:
            found = None
        if found and viewer_id:
            from ...models import UserBlocklist
            if UserBlocklist.objects.filter(
                (Q(user=found, blocked_user_id=viewer_id)) |
                (Q(user_id=viewer_id, blocked_user=found))
            ).exists():
                found = None  # 对方屏蔽了搜索者，仍走中性文案

        if not found:
            return JsonResponse({'users': []})

        return JsonResponse({
            'users': [{
                'id': found.id,
                'username': found.username,
                'avatar': _get_avatar_url(found),
                'bio': getattr(getattr(found, 'profile', None), 'bio', '') or '',
                'matched_by': via,
            }],
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('搜索用户错误', e)


@login_required
def messages_view(request):
    """私信页面"""
    active_at = int(timezone.now().timestamp())
    request.session[MESSAGES_PAGE_ACTIVE_AT_KEY] = active_at
    request.session.modified = True
    mark_messages_page_activity(request.user.id, active_at)
    messages_bundle_path = os.path.join(settings.BASE_DIR, 'staticfiles', 'dist', 'messages.js')
    try:
        messages_asset_version = int(os.path.getmtime(messages_bundle_path))
    except OSError:
        messages_asset_version = int(time.time())
    return render(request, 'messages/messages.html', {
        'realtime_enabled': getattr(settings, 'REALTIME_MESSAGES_ENABLED', False),
        'realtime_ws_path': getattr(settings, 'REALTIME_MESSAGES_PATH', '/ws/messages/'),
        'messages_asset_version': messages_asset_version,
    })


@require_http_methods(["POST"])
@login_required
def touch_messages_page_api(request):
    active_at = int(timezone.now().timestamp())
    request.session[MESSAGES_PAGE_ACTIVE_AT_KEY] = active_at
    request.session.modified = True
    mark_messages_page_activity(request.user.id, active_at)
    return JsonResponse({'status': 'success'})


@require_http_methods(["GET"])
@login_required
def get_unread_messages_count_api(request):
    """当前用户的未读私信总数（供导航栏角标轮询）"""
    try:
        from ...models import Message
        total = Message.objects.filter(
            recipient=request.user,
            is_read=False,
            is_recalled=False,
            deleted_for_recipient=False,
        ).count()
        return JsonResponse({'status': 'success', 'unread_count': total})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取未读数错误', e)
