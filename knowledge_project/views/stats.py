"""knowledge_project.views.stats

首页社区统计与活跃贡献者 API。从 legacy.py 拆出。
"""
from django.contrib.auth.models import User
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone

from ..models import Note


def home_stats_api(request):
    """首页社区统计和活跃贡献者 API"""
    # 社区统计
    total_notes = Note.objects.filter(is_public=True, is_trashed=False).count()

    # 在线用户：最近 5 分钟内有活跃 session 的数量
    try:
        from django.contrib.sessions.models import Session
        from django.conf import settings as django_settings
        cookie_age = getattr(django_settings, 'SESSION_COOKIE_AGE', 10800)
        five_min_ago_threshold = timezone.now() + timezone.timedelta(seconds=cookie_age) - timezone.timedelta(minutes=5)
        online_users = Session.objects.filter(expire_date__gte=five_min_ago_threshold).count()
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
