import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import BackupRecord


def _serialize(record):
    return {
        'id': record.id,
        'kind': record.kind,
        'status': record.status,
        'started_at': record.started_at.isoformat(),
        'completed_at': record.completed_at.isoformat() if record.completed_at else None,
        'size_bytes': record.size_bytes,
        'metadata': record.metadata or {},
        'error_message': record.error_message,
    }


def _require_superuser(request):
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': '权限不足'}, status=403)
    return None


@login_required
@require_http_methods(['GET', 'POST'])
def backup_status_api(request):
    error = _require_superuser(request)
    if error:
        return error

    if request.method == 'POST':
        try:
            payload = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': '无效的 JSON 数据'}, status=400)
        notes = str(payload.get('notes') or '').strip()
        if len(notes) > 2000:
            return JsonResponse({'status': 'error', 'message': '演练说明不能超过 2000 个字符'}, status=400)
        record = BackupRecord.objects.create(
            kind=BackupRecord.KIND_RECOVERY_DRILL,
            status=BackupRecord.STATUS_SUCCEEDED,
            completed_at=timezone.now(),
            metadata={'notes': notes, 'recorded_via': 'dashboard'},
            created_by=request.user,
        )
        return JsonResponse({'status': 'success', 'record': _serialize(record)}, status=201)

    records = BackupRecord.objects.select_related('created_by')[:20]
    latest_snapshot = BackupRecord.objects.filter(
        kind=BackupRecord.KIND_SNAPSHOT,
        status=BackupRecord.STATUS_SUCCEEDED,
    ).first()
    latest_drill = BackupRecord.objects.filter(
        kind=BackupRecord.KIND_RECOVERY_DRILL,
        status=BackupRecord.STATUS_SUCCEEDED,
    ).first()
    return JsonResponse({
        'status': 'success',
        'latest_snapshot': _serialize(latest_snapshot) if latest_snapshot else None,
        'latest_recovery_drill': _serialize(latest_drill) if latest_drill else None,
        'records': [_serialize(record) for record in records],
        'run_command': 'python manage.py run_backup --include-media',
    })
