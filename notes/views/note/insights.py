"""个人知识洞察页面与统计 API。

聚合当前用户的笔记、修订、消息数据，生成活动热力图、
文件夹/标签分布、热门笔记等只读统计。保密笔记只计入总量，
不出现在任何带标题的榜单或分布里。
"""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import Length, TruncDate
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from messaging.models import Message
from notes.models import Note, NoteRevision, Tag

HEATMAP_DAYS = 182  # 26 周
MESSAGE_TREND_DAYS = 14
TOP_NOTES_LIMIT = 5
FOLDER_SLICE_LIMIT = 8
TAG_LIMIT = 10


def _local_today():
    return timezone.localtime(timezone.now()).date()


def _day_range(days):
    today = _local_today()
    return [today - timedelta(days=i) for i in range(days - 1, -1, -1)]


def _daily_counts(queryset, date_field, days):
    """按本地日期聚合 queryset 数量，返回 {date: count}。"""
    today = _local_today()
    start = today - timedelta(days=days - 1)
    rows = (
        queryset
        .filter(**{f'{date_field}__date__gte': start})
        .annotate(day=TruncDate(date_field))
        .values('day')
        .annotate(count=Count('id'))
    )
    return {row['day']: row['count'] for row in rows}


def _streaks(count_map, days):
    """基于热力图数据计算当前连续活跃天数与窗口内最长连续天数。"""
    day_list = _day_range(days)
    current = 0
    longest = 0
    running = 0
    for day in day_list:
        if count_map.get(day, 0) > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0

    # 当前连续：从今天往回数；今天还没活动时允许从昨天起算
    for offset, day in enumerate(reversed(day_list)):
        if count_map.get(day, 0) > 0:
            current += 1
        elif offset == 0:
            continue
        else:
            break
    return current, longest


@login_required
def insights_view(request):
    """洞察页面（前端 Vue 渲染）。"""
    return render(request, 'knowledge/insights.html')


@login_required
@require_http_methods(['GET'])
def insights_api(request):
    user = request.user
    now = timezone.now()

    my_notes = Note.objects.filter(author=user, is_trashed=False)
    visible_notes = my_notes.filter(is_secret=False)

    # ---- 概览卡片 ----
    summary = {
        'note_count': my_notes.count(),
        'public_count': visible_notes.filter(is_public=True).count(),
        'favorited_count': visible_notes.filter(is_favorited=True).count(),
        'vault_count': my_notes.filter(is_secret=True).count(),
        'total_views': visible_notes.aggregate(total=Sum('views'))['total'] or 0,
        'content_chars': (
            visible_notes.exclude(content__isnull=True)
            .aggregate(total=Sum(Length('content')))['total'] or 0
        ),
        'tag_count': Tag.objects.filter(notes__in=my_notes).distinct().count(),
    }

    thirty_days_ago = now - timedelta(days=30)
    summary['messages_sent_30d'] = Message.objects.filter(
        sender=user, created_at__gte=thirty_days_ago
    ).count()
    summary['messages_received_30d'] = Message.objects.filter(
        recipient=user, created_at__gte=thirty_days_ago
    ).count()

    # ---- 活动热力图（按笔记修订记录，每次保存计一次） ----
    revision_qs = NoteRevision.objects.filter(created_by=user)
    heat_map = _daily_counts(revision_qs, 'created_at', HEATMAP_DAYS)
    current_streak, longest_streak = _streaks(heat_map, HEATMAP_DAYS)
    heatmap = [
        {'date': day.isoformat(), 'count': heat_map.get(day, 0)}
        for day in _day_range(HEATMAP_DAYS)
    ]

    # ---- 文件夹分布（不含保密笔记） ----
    folder_rows = list(
        visible_notes
        .values('folder__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    folder_distribution = []
    other = 0
    for index, row in enumerate(folder_rows):
        name = row['folder__name'] or '未分类'
        if index < FOLDER_SLICE_LIMIT:
            folder_distribution.append({'name': name, 'count': row['count']})
        else:
            other += row['count']
    if other:
        folder_distribution.append({'name': '其他', 'count': other})

    # ---- 标签 Top（不含保密笔记） ----
    tag_rows = (
        Tag.objects.filter(notes__in=visible_notes)
        .annotate(count=Count('notes'))
        .order_by('-count')[:TAG_LIMIT]
    )
    top_tags = [{'name': tag.name, 'count': tag.count} for tag in tag_rows]

    # ---- 热门笔记（浏览量 Top，不含保密笔记） ----
    top_notes = [
        {
            'id': note.id,
            'title': note.title or '(无标题)',
            'views': note.views,
            'is_public': note.is_public,
        }
        for note in visible_notes.filter(views__gt=0).order_by('-views')[:TOP_NOTES_LIMIT]
    ]

    # ---- 消息趋势（近 14 天） ----
    sent_map = _daily_counts(
        Message.objects.filter(sender=user), 'created_at', MESSAGE_TREND_DAYS
    )
    received_map = _daily_counts(
        Message.objects.filter(recipient=user), 'created_at', MESSAGE_TREND_DAYS
    )
    message_trend = [
        {
            'date': day.isoformat(),
            'sent': sent_map.get(day, 0),
            'received': received_map.get(day, 0),
        }
        for day in _day_range(MESSAGE_TREND_DAYS)
    ]

    return JsonResponse({
        'summary': summary,
        'heatmap': heatmap,
        'streak': {'current': current_streak, 'longest': longest_streak},
        'folder_distribution': folder_distribution,
        'top_tags': top_tags,
        'top_notes': top_notes,
        'message_trend': message_trend,
    })
