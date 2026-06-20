"""knowledge_project.views.stats

首页社区统计与活跃贡献者 API。从 legacy.py 拆出。
"""
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone

from notes.models import Note


ONLINE_WINDOW_SECONDS = 5 * 60
HOME_STATS_CACHE_TIMEOUT = 60


def _count_online_users():
    """统计最近 5 分钟内有请求活动的已登录用户数。"""
    from core.utils.session_activity import count_recent_users

    return count_recent_users(ONLINE_WINDOW_SECONDS)


def _format_stat_count(value):
    if value >= 10000:
        return f'{value / 1000:.1f}k'
    if value >= 1000:
        return f'{value / 1000:.1f}k'
    return str(value)


def home_stats_api(request):
    """首页社区统计和活跃贡献者 API"""
    response_data = cache.get('home_stats_api:v1')
    if response_data:
        try:
            response_data['stats']['onlineUsers'] = _format_stat_count(_count_online_users())
        except Exception:
            response_data['stats']['onlineUsers'] = _format_stat_count(0)
        return JsonResponse(response_data)

    # 社区统计
    total_notes = Note.objects.filter(is_public=True, is_trashed=False).count()

    # 在线用户：最近 5 分钟内有请求活动的已登录用户数量
    try:
        online_users = _count_online_users()
    except Exception:
        online_users = 0

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = Note.objects.filter(
        is_public=True, is_trashed=False, created_at__gte=today_start
    ).count()

    # 活跃贡献者：最近7天内发布/更新公开笔记最多的用户
    seven_days_ago = timezone.now() - timezone.timedelta(days=7)
    top_users = (
        User.objects
        .filter(notes__is_public=True, notes__is_trashed=False, notes__updated_at__gte=seven_days_ago)
        .annotate(note_count=Count('notes'))
        .order_by('-note_count')[:5]
    )

    contributors = []
    for u in top_users:
        avatar = '/static/img/default-avatar.png'
        try:
            if u.profile.avatar:
                avatar = u.profile.avatar.url
        except Exception:
            pass
        contributors.append({
            'id': u.id,
            'name': u.username,
            'avatar': avatar,
            'activity': f'发布了 {u.note_count} 篇笔记',
            'online': True,
        })

    response_data = {
        'stats': {
            'totalNotes': _format_stat_count(total_notes),
            'onlineUsers': _format_stat_count(online_users),
            'todayNew': today_new,
        },
        'contributors': contributors,
    }
    cache.set('home_stats_api:v1', response_data, HOME_STATS_CACHE_TIMEOUT)
    return JsonResponse(response_data)
