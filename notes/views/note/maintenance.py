"""User-confirmed cleanup APIs for detached note assets."""

import os

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .common import login_required
from notes.models import Asset


def _asset_size(asset):
    try:
        return int(asset.file.size or 0)
    except (OSError, ValueError):
        return 0


def _orphan_assets_for_user(user):
    # Keep assets referenced by trashed notes as well: those notes can be restored.
    return (
        Asset.objects.filter(uploader=user)
        .exclude(file='')
        .filter(note_links__isnull=True)
        .order_by('-uploaded_at')
    )


def _asset_payload(asset):
    return {
        'id': asset.id,
        'name': asset.name or os.path.basename(asset.file.name or '') or '未命名文件',
        'type': asset.asset_type,
        'size': _asset_size(asset),
        'uploaded_at': asset.uploaded_at.isoformat() if asset.uploaded_at else None,
    }


@login_required
@require_http_methods(['GET'])
def orphan_note_assets_api(request):
    assets = list(_orphan_assets_for_user(request.user)[:500])
    return JsonResponse({
        'assets': [_asset_payload(asset) for asset in assets],
        'total': len(assets),
        'total_bytes': sum(_asset_size(asset) for asset in assets),
        'truncated': _orphan_assets_for_user(request.user).count() > len(assets),
    })


@login_required
@require_http_methods(['POST'])
def delete_orphan_note_assets_api(request):
    try:
        import json

        data = json.loads(request.body or '{}')
        raw_ids = data.get('asset_ids')
        if not isinstance(raw_ids, list) or not raw_ids:
            return JsonResponse({'error': '请选择要删除的待清理资源'}, status=400)
        asset_ids = sorted({int(item) for item in raw_ids if int(item) > 0})
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': '资源列表格式无效'}, status=400)

    deleted_ids = []
    freed_bytes = 0
    files_to_delete = []
    with transaction.atomic():
        assets = list(
            Asset.objects.select_for_update()
            .filter(id__in=asset_ids, uploader=request.user, note_links__isnull=True)
        )
        for asset in assets:
            freed_bytes += _asset_size(asset)
            if asset.file:
                files_to_delete.append(asset.file)
            deleted_ids.append(asset.id)
            asset.delete()
        transaction.on_commit(
            lambda: [file_field.delete(save=False) for file_field in files_to_delete]
        )

    return JsonResponse({
        'status': 'deleted',
        'deleted_ids': deleted_ids,
        'freed_bytes': freed_bytes,
    })
