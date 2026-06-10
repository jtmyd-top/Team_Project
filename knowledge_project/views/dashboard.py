# knowledge_project/dashboard_views.py
"""战情室 Dashboard 相关视图(仅超级管理员)

原属于 views.py 4761-5233 段。抽出后 views.py 底部 re-export 兼容。
"""
import json
import logging
import platform
import re as _re
import time
from datetime import datetime, time as datetime_time, timedelta

import psutil
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connections
from django.db.models import Count, F
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import Asset, Folder, Note

logger = logging.getLogger(__name__)


def _aware_day_start(day):
    value = datetime.combine(day, datetime_time.min)
    if settings.USE_TZ and timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _dashboard_days(now, days):
    return [(now - timedelta(days=i)).date() for i in range(days - 1, -1, -1)]


def _daily_count_map(queryset, date_field, start, end, alias='day'):
    filters = {
        f'{date_field}__gte': start,
        f'{date_field}__lt': end,
    }
    return {
        row[alias]: row['count']
        for row in (
            queryset
            .filter(**filters)
            .annotate(**{alias: TruncDate(date_field)})
            .values(alias)
            .annotate(count=Count('id'))
        )
    }


def _cache_health_details():
    try:
        cache.set('_health_check', '1', 5)
        if cache.get('_health_check') != '1':
            return {'ok': False, 'detail': 'cache read-back failed'}

        try:
            client = cache.client.get_client()
            info = client.info()
            return {
                'ok': True,
                'detail': {
                    'used_memory_human': info.get('used_memory_human', 'N/A'),
                    'connected_clients': info.get('connected_clients', 0),
                    'uptime_in_seconds': info.get('uptime_in_seconds', 0),
                }
            }
        except Exception:
            return {'ok': True, 'detail': 'ping ok'}
    except Exception as exc:
        return {'ok': False, 'detail': str(exc)[:200]}


def _database_health_details():
    try:
        connection = connections['default']
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return {'ok': True, 'detail': 'ok'}
    except Exception as exc:
        return {'ok': False, 'detail': str(exc)[:200]}


def healthz(request):
    return JsonResponse({
        'status': 'ok',
        'service': 'team_project',
        'time': timezone.now().isoformat(),
    })


@require_http_methods(["GET"])
def readyz(request):
    cache_status = _cache_health_details()
    db_status = _database_health_details()

    if settings.REALTIME_MESSAGES_ENABLED:
        channel_layer_backend = (
            getattr(settings, 'CHANNEL_LAYERS', {})
            .get('default', {})
            .get('BACKEND')
        )
        websocket_ready = bool(channel_layer_backend)
        websocket_detail = channel_layer_backend or 'disabled'
    else:
        websocket_ready = True
        websocket_detail = 'realtime disabled'

    payload = {
        'status': 'ok' if cache_status['ok'] and db_status['ok'] and websocket_ready else 'error',
        'checks': {
            'database': db_status,
            'cache': cache_status,
            'websocket': {
                'ok': websocket_ready,
                'detail': websocket_detail,
            },
        },
        'time': timezone.now().isoformat(),
    }
    return JsonResponse(payload, status=200 if payload['status'] == 'ok' else 503)


@login_required
def dashboard_view(request):
    """战情室页面视图，仅超级管理员可访问"""
    if not request.user.is_superuser:
        return redirect('home')
    return render(request, 'knowledge/dashboard.html')


@login_required
@require_http_methods(["GET"])
def dashboard_stats_api(request):
    """
    战情室数据 API，仅超级管理员可访问
    支持 ?section=heartbeat|assets|vault_alerts|trash_backlog|content_trend|login_monitor|audit_log|network|service_health|error_logs|all
    """
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': '权限不足'}, status=403)

    section = request.GET.get('section', 'all')
    data = {}

    # ---- heartbeat: CPU/内存/磁盘实时数据 ----
    if section in ('heartbeat', 'all'):
        try:
            cpu_percent = psutil.cpu_percent(interval=0)
            mem = psutil.virtual_memory()
            disk_path = 'C:\\' if platform.system() == 'Windows' else '/'
            disk = psutil.disk_usage(disk_path)
            boot_time = psutil.boot_time()
            uptime_seconds = int(time.time() - boot_time)

            data['heartbeat'] = {
                'cpu_percent': cpu_percent,
                'cpu_count': psutil.cpu_count(),
                'memory_total': mem.total,
                'memory_used': mem.used,
                'memory_percent': mem.percent,
                'disk_total': disk.total,
                'disk_used': disk.used,
                'disk_percent': disk.percent,
                'uptime_seconds': uptime_seconds,
            }
        except Exception as e:
            logger.error(f"Dashboard heartbeat error: {e}")
            data['heartbeat'] = None

    # ---- assets: 笔记/文件夹/附件统计 + 7天趋势 ----
    if section in ('assets', 'all'):
        cached = cache.get('dashboard_assets')
        if cached:
            data['assets'] = cached
        else:
            from django.contrib.auth.models import User as AuthUser
            now = timezone.now()

            total_notes = Note.objects.filter(is_trashed=False).count()
            total_folders = Folder.objects.filter(is_trashed=False).count()
            total_assets = Asset.objects.count()
            total_users = AuthUser.objects.filter(is_active=True).count()
            public_notes = Note.objects.filter(
                is_public=True, is_trashed=False
            ).count()
            secret_notes = Note.objects.filter(
                is_secret=True, is_trashed=False
            ).count()

            # 7天笔记趋势
            days = _dashboard_days(now, 7)
            start = _aware_day_start(days[0])
            end = _aware_day_start(days[-1] + timedelta(days=1))
            note_counts = _daily_count_map(
                Note.objects.filter(is_trashed=False),
                'created_at',
                start,
                end,
            )
            trend = [
                {'date': day.strftime('%m-%d'), 'count': note_counts.get(day, 0)}
                for day in days
            ]

            assets_data = {
                'total_notes': total_notes,
                'total_folders': total_folders,
                'total_assets': total_assets,
                'total_users': total_users,
                'public_notes': public_notes,
                'secret_notes': secret_notes,
                'notes_trend': trend,
            }
            cache.set('dashboard_assets', assets_data, 300)
            data['assets'] = assets_data

    # ---- vault_alerts: 保密柜安全告警（从数据库持久化读取） ----
    if section in ('vault_alerts', 'all'):
        from ..models import AccessLog
        from ..decorators import get_vault_user_lock_key, get_vault_user_fail_key, VAULT_USER_FAIL_THRESHOLD
        from django.db.models import Sum, Max
        from datetime import timedelta

        alerts = []
        try:
            now = timezone.now()
            cutoff = now - timedelta(hours=24)

            # 从 AccessLog 聚合24小时内的 vault_fail 记录
            aggregated = AccessLog.objects.filter(
                action='vault_fail',
                created_at__gte=cutoff
            ).values('user_identifier', 'ip_address').annotate(
                total_count=Sum('count'),
                last_time=Max('updated_at')
            ).order_by('-total_count')

            for item in aggregated:
                total = item['total_count'] or 0
                ip = item['ip_address']
                username = item['user_identifier']

                if total > 0:
                    # 检查用户级锁定状态
                    user_locked = False
                    try:
                        from django.contrib.auth.models import User as AuthUser
                        user_obj = AuthUser.objects.filter(username=username).first()
                        if user_obj:
                            user_lock_key = get_vault_user_lock_key(user_obj.id)
                            user_lock_expire = cache.get(user_lock_key)
                            if user_lock_expire and user_lock_expire > int(time.time()):
                                user_locked = True
                    except:
                        pass

                    # 严重程度判断：用户级锁定 > 5次失败 > 3次失败
                    if user_locked:
                        severity = 'critical'
                    elif total >= VAULT_USER_FAIL_THRESHOLD:
                        severity = 'critical'
                    elif total >= 3:
                        severity = 'warning'
                    else:
                        severity = 'info'

                    alerts.append({
                        'user': username,
                        'ip': ip,
                        'fail_count': total,
                        'time': item['last_time'].strftime('%m-%d %H:%M') if item['last_time'] else '',
                        'severity': severity,
                        'is_banned': cache.get(f'banned_ip:{ip}') is not None,
                        'user_locked': user_locked,  # 新增：用户级锁定状态
                    })

            # 按严重程度排序
            alerts.sort(
                key=lambda x: (
                    0 if x['severity'] == 'critical' else (
                        1 if x['severity'] == 'warning' else 2
                    )
                )
            )
        except Exception as e:
            logger.error(f"Dashboard vault_alerts error: {e}")
        data['vault_alerts'] = alerts

    # ---- trash_backlog: 回收站积压 ----
    if section in ('trash_backlog', 'all'):
        try:
            now = timezone.now()
            trashed_notes = Note.objects.filter(is_trashed=True)
            trashed_folders = Folder.objects.filter(is_trashed=True)
            trashed_notes_count = trashed_notes.count()
            trashed_folders_count = trashed_folders.count()

            # 超过 30 天未清理的
            stale_cutoff = now - timedelta(days=30)
            stale_notes = trashed_notes.filter(trashed_at__lte=stale_cutoff).count()
            stale_folders = trashed_folders.filter(trashed_at__lte=stale_cutoff).count()

            # 按天统计最近 7 天删除量
            days = _dashboard_days(now, 7)
            start = _aware_day_start(days[0])
            end = _aware_day_start(days[-1] + timedelta(days=1))
            note_trash_counts = _daily_count_map(
                trashed_notes,
                'trashed_at',
                start,
                end,
            )
            folder_trash_counts = _daily_count_map(
                trashed_folders,
                'trashed_at',
                start,
                end,
            )
            trash_trend = [
                {
                    'date': day.strftime('%m-%d'),
                    'count': note_trash_counts.get(day, 0) + folder_trash_counts.get(day, 0),
                }
                for day in days
            ]

            data['trash_backlog'] = {
                'trashed_notes': trashed_notes_count,
                'trashed_folders': trashed_folders_count,
                'total_trashed': trashed_notes_count + trashed_folders_count,
                'stale_notes': stale_notes,
                'stale_folders': stale_folders,
                'total_stale': stale_notes + stale_folders,
                'trash_trend': trash_trend,
            }
        except Exception as e:
            logger.error(f"Dashboard trash_backlog error: {e}")
            data['trash_backlog'] = None

    # ---- content_trend: 30天内容增长趋势（含新增+修改） ----
    if section in ('content_trend', 'all'):
        try:
            now = timezone.now()

            days = _dashboard_days(now, 30)
            start = _aware_day_start(days[0])
            end = _aware_day_start(days[-1] + timedelta(days=1))
            visible_notes = Note.objects.filter(is_trashed=False)
            created_counts = _daily_count_map(visible_notes, 'created_at', start, end)
            modified_counts = {
                row['updated_day']: row['count']
                for row in (
                    visible_notes
                    .filter(updated_at__gte=start, updated_at__lt=end)
                    .annotate(
                        updated_day=TruncDate('updated_at'),
                        created_day=TruncDate('created_at'),
                    )
                    .exclude(created_day=F('updated_day'))
                    .values('updated_day')
                    .annotate(count=Count('id'))
                )
            }
            created_trend = [
                {'date': day.strftime('%m-%d'), 'count': created_counts.get(day, 0)}
                for day in days
            ]
            modified_trend = [
                {'date': day.strftime('%m-%d'), 'count': modified_counts.get(day, 0)}
                for day in days
            ]

            data['content_trend'] = {
                'created': created_trend,
                'modified': modified_trend,
            }
        except Exception as e:
            logger.error(f"Dashboard content_trend error: {e}")
            data['content_trend'] = None

    # ---- login_monitor: 登录 IP 监控 / 入侵检测 ----
    if section in ('login_monitor', 'all'):
        try:
            from ..models import LoginDevice, LoginNotification
            from datetime import timedelta
            now = timezone.now()
            seven_days_ago = now - timedelta(days=7)

            # 最近 7 天的登录设备
            recent_devices = LoginDevice.objects.filter(
                last_login_at__gte=seven_days_ago
            ).select_related('user').order_by('-last_login_at')[:50]

            devices_list = [{
                'user': d.user.username,
                'ip': d.ip_address,
                'location': d.ip_location or '未知',
                'device': d.device_info,
                'last_login': d.last_login_at.isoformat(),
                'login_count': d.login_count,
                'is_trusted': d.is_trusted,
            } for d in recent_devices]

            # 可疑登录通知
            suspicious = LoginNotification.objects.filter(
                sent_at__gte=seven_days_ago,
                reason__in=['suspicious', 'new_device', 'new_location']
            ).select_related('user', 'device').order_by('-sent_at')[:30]

            suspicious_list = [{
                'user': s.user.username,
                'ip': s.ip_address,
                'reason': s.get_reason_display(),
                'reason_code': s.reason,
                'device': s.device.device_info if s.device else '未知',
                'location': s.device.ip_location if s.device else '未知',
                'time': s.sent_at.isoformat(),
                'is_banned': cache.get(f'banned_ip:{s.ip_address}') is not None,
            } for s in suspicious]

            # IP 分布统计
            from django.db.models import Count
            ip_stats = LoginDevice.objects.filter(
                last_login_at__gte=seven_days_ago
            ).values('ip_location').annotate(
                count=Count('id')
            ).order_by('-count')[:10]

            data['login_monitor'] = {
                'recent_devices': devices_list,
                'suspicious_logins': suspicious_list,
                'ip_distribution': list(ip_stats),
                'total_devices': LoginDevice.objects.filter(
                    last_login_at__gte=seven_days_ago
                ).count(),
                'suspicious_count': len(suspicious_list),
            }
        except Exception as e:
            logger.error(f"Dashboard login_monitor error: {e}")
            data['login_monitor'] = None

    # ---- audit_log: 敏感操作审计 ----
    if section in ('audit_log', 'all'):
        try:
            from django.contrib.admin.models import LogEntry
            from datetime import timedelta
            now = timezone.now()
            seven_days_ago = now - timedelta(days=7)

            # Django admin LogEntry 记录
            admin_logs = LogEntry.objects.filter(
                action_time__gte=seven_days_ago
            ).select_related('user', 'content_type').order_by('-action_time')[:50]

            action_map = {1: '新增', 2: '修改', 3: '删除'}
            admin_log_list = [{
                'user': log.user.username,
                'action': action_map.get(log.action_flag, '未知'),
                'action_flag': log.action_flag,
                'target': log.object_repr,
                'model': log.content_type.model if log.content_type else '未知',
                'time': log.action_time.isoformat(),
                'message': log.change_message,
            } for log in admin_logs]

            # 补充：最近永久删除的笔记/文件夹（通过回收站清空时间推断）
            # 统计各类操作数量
            from django.db.models import Count
            action_summary = LogEntry.objects.filter(
                action_time__gte=seven_days_ago
            ).values('action_flag').annotate(count=Count('id'))

            summary = {'add': 0, 'change': 0, 'delete': 0}
            for item in action_summary:
                if item['action_flag'] == 1:
                    summary['add'] = item['count']
                elif item['action_flag'] == 2:
                    summary['change'] = item['count']
                elif item['action_flag'] == 3:
                    summary['delete'] = item['count']

            data['audit_log'] = {
                'logs': admin_log_list,
                'summary': summary,
                'total': len(admin_log_list),
            }
        except Exception as e:
            logger.error(f"Dashboard audit_log error: {e}")
            data['audit_log'] = None

    # ---- network: 网络流量（前端计算速率） ----
    if section in ('network', 'heartbeat', 'all'):
        try:
            net = psutil.net_io_counters()
            data.setdefault('heartbeat', {})
            data['heartbeat']['net_bytes_sent'] = net.bytes_sent
            data['heartbeat']['net_bytes_recv'] = net.bytes_recv
        except Exception as e:
            logger.error(f"Dashboard network error: {e}")

    # ---- service_health: 中间件健康检查 ----
    if section in ('service_health', 'all'):
        services = {}
        # Redis
        cache_health = _cache_health_details()
        if cache_health['ok']:
            if isinstance(cache_health['detail'], dict):
                services['redis'] = {'status': 'ok', **cache_health['detail']}
            else:
                services['redis'] = {'status': 'ok', 'detail': cache_health['detail']}
        else:
            services['redis'] = {'status': 'error', 'detail': cache_health['detail']}

        # Database
        database_health = _database_health_details()
        if database_health['ok']:
            services['database'] = {'status': 'ok'}
        else:
            services['database'] = {'status': 'error', 'detail': database_health['detail']}

        data['service_health'] = services

    # ---- error_logs: 系统异常日志流（优先从LogEntry读取最近10条） ----
    if section in ('error_logs', 'all'):
        try:
            import os
            from django.conf import settings
            from django.contrib.admin.models import LogEntry
            error_log_list = []
            source = 'logentry'

            # 优先从 LogEntry 读取最近10条操作记录
            action_labels = {1: 'ADD', 2: 'CHANGE', 3: 'DELETE'}
            recent = LogEntry.objects.select_related('user', 'content_type').order_by('-action_time')[:10]
            for log in recent:
                action = action_labels.get(log.action_flag, 'UNKNOWN')
                msg = log.change_message or log.object_repr
                user_name = log.user.username if log.user else 'system'
                error_log_list.append(
                    f"[{log.action_time.strftime('%m-%d %H:%M:%S')}] "
                    f"{action} by {user_name}: {msg}"
                )

            # 如果 LogEntry 为空，回退到错误日志文件
            if not error_log_list:
                log_file = os.path.join(settings.BASE_DIR, 'django_error.log')
                if os.path.exists(log_file):
                    source = 'file'
                    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                        lines = f.readlines()
                        last_lines = lines[-10:] if len(lines) > 10 else lines
                        for line in last_lines:
                            line = line.strip()
                            if line:
                                error_log_list.append(line)

            data['error_logs'] = {
                'logs': error_log_list,
                'total': len(error_log_list),
                'source': source,
            }
        except Exception as e:
            logger.error(f"Dashboard error_logs error: {e}")
            data['error_logs'] = None

    return JsonResponse({'status': 'success', **data})


@login_required
@require_http_methods(["POST"])
def ban_ip_api(request):
    """
    IP 封禁接口，仅超级管理员可用
    POST /api/ban_ip/  body: {"ip": "x.x.x.x"}
    将 IP 写入 Redis 黑名单，key = banned_ip:<ip>，永不过期
    """
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': '权限不足'}, status=403)

    try:
        body = json.loads(request.body)
        ip = body.get('ip', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'status': 'error', 'message': '请求格式错误'}, status=400)

    if not ip:
        return JsonResponse({'status': 'error', 'message': 'IP 不能为空'}, status=400)

    # 简单校验 IP 格式（IPv4）
    if not _re.match(r'^\d{1,3}(\.\d{1,3}){3}$', ip):
        return JsonResponse({'status': 'error', 'message': 'IP 格式无效'}, status=400)

    try:
        cache_key = f'banned_ip:{ip}'
        cache.set(cache_key, {
            'banned_by': request.user.username,
            'banned_at': timezone.now().isoformat(),
            'reason': body.get('reason', '战情室手动封禁'),
        }, timeout=None)  # 永不过期

        logger.info(f"IP {ip} banned by {request.user.username} from dashboard")
        return JsonResponse({'status': 'success', 'message': f'IP {ip} 已加入黑名单'})
    except Exception as e:
        logger.error(f"Ban IP error: {e}")
        return JsonResponse({'status': 'error', 'message': '封禁失败，请重试'}, status=500)
