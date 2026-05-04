"""knowledge_project.views.stats

首页社区统计与活跃贡献者 API。从 legacy.py 拆出。
"""
from django.contrib.auth.models import User
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone

from ..models import Note


SESSION_LAST_ACTIVITY_KEY = 'last_activity_at'
ONLINE_WINDOW_SECONDS = 5 * 60


def _count_online_users():
    """统计最近 5 分钟内有请求活动的已登录用户数。"""
    from django.contrib.sessions.models import Session

    now = timezone.now()
    active_since = int(now.timestamp()) - ONLINE_WINDOW_SECONDS
    user_ids = set()

    sessions = Session.objects.filter(expire_date__gte=now).iterator()
    for session in sessions:
        data = session.get_decoded()
        user_id = data.get('_auth_user_id')
        last_activity_at = data.get(SESSION_LAST_ACTIVITY_KEY)
        if user_id and last_activity_at and int(last_activity_at) >= active_since:
            user_ids.add(user_id)

    return len(user_ids)


def home_stats_api(request):
    """首页社区统计和活跃贡献者 API"""
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

    # 格式化数字
    def fmt(n):
        if n >= 10000:
            return f'{n / 1000:.1f}k'
        elif n >= 1000:
            return f'{n / 1000:.1f}k'
        return str(n)

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

    return JsonResponse({
        'stats': {
            'totalNotes': fmt(total_notes),
            'onlineUsers': fmt(online_users),
            'todayNew': today_new,
        },
        'contributors': contributors,
    })
