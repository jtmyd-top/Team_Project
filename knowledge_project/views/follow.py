# knowledge_project/views/follow.py
"""用户关注 / 订阅相关视图"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
@login_required
def follow_user_api(request):
    """关注某用户"""
    try:
        from ..models import UserFollow, UserBlocklist

        data = json.loads(request.body) if request.body else {}
        target_id = data.get('user_id')
        if not target_id:
            return JsonResponse({'error': '缺少 user_id'}, status=400)

        target = get_object_or_404(User, id=target_id)
        if target == request.user:
            return JsonResponse({'error': '不能关注自己'}, status=400)

        from django.db.models import Q
        if UserBlocklist.objects.filter(
            (Q(user=request.user) & Q(blocked_user=target)) |
            (Q(user=target) & Q(blocked_user=request.user))
        ).exists():
            return JsonResponse({'error': '由于屏蔽关系，无法关注此用户'}, status=403)

        _, created = UserFollow.objects.get_or_create(
            follower=request.user, following=target
        )
        followers_count = UserFollow.objects.filter(following=target).count()
        return JsonResponse({
            'status': 'success',
            'is_following': True,
            'created': created,
            'followers_count': followers_count,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        logger.error("关注用户错误: %s", e, exc_info=True)
        return JsonResponse({'error': '服务器错误'}, status=500)


@require_http_methods(["POST"])
@login_required
def unfollow_user_api(request):
    """取消关注"""
    try:
        from ..models import UserFollow

        data = json.loads(request.body) if request.body else {}
        target_id = data.get('user_id')
        if not target_id:
            return JsonResponse({'error': '缺少 user_id'}, status=400)

        target = get_object_or_404(User, id=target_id)
        UserFollow.objects.filter(
            follower=request.user, following=target
        ).delete()
        followers_count = UserFollow.objects.filter(following=target).count()
        return JsonResponse({
            'status': 'success',
            'is_following': False,
            'followers_count': followers_count,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        logger.error("取消关注错误: %s", e, exc_info=True)
        return JsonResponse({'error': '服务器错误'}, status=500)


@require_http_methods(["GET"])
def follow_status_api(request, user_id):
    """查询当前登录用户是否已关注 target；并返回目标用户粉丝数 / 关注数

    匿名访问：is_following 固定 false，仍返回公开计数
    """
    try:
        from ..models import UserFollow

        target = get_object_or_404(User, id=user_id)
        followers_count = UserFollow.objects.filter(following=target).count()
        following_count = UserFollow.objects.filter(follower=target).count()
        if request.user.is_authenticated and request.user != target:
            is_following = UserFollow.objects.filter(
                follower=request.user, following=target
            ).exists()
        else:
            is_following = False
        return JsonResponse({
            'status': 'success',
            'is_following': is_following,
            'followers_count': followers_count,
            'following_count': following_count,
            'is_self': request.user.is_authenticated and request.user == target,
        })
    except Http404:
        raise
    except Exception as e:
        logger.error("查询关注状态错误: %s", e, exc_info=True)
        return JsonResponse({'error': '服务器错误'}, status=500)
