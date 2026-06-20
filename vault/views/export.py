"""Vault export views."""
from .common import *  # noqa: F401, F403


@login_required
@require_http_methods(["POST"])
def vault_export(request):
    """
    导出保险柜备份（加密的笔记数据）

    逻辑：
    1. 获取用户所有 is_secret=True 的笔记
    2. 导出为 JSON 文件（包含加密的内容）
    3. 返回下载链接
    """
    try:
        user = request.user

        # 获取用户的所有保密笔记
        secret_notes = Note.objects.filter(
            author=user,
            is_secret=True,
            is_trashed=False
        ).values('id', 'title', 'content', 'created_at', 'updated_at', 'folder_id')

        # 转换为列表
        notes_data = list(secret_notes)

        # 创建备份数据
        backup_data = {
            'user_id': user.id,
            'username': user.username,
            'exported_at': timezone.now().isoformat(),
            'notes_count': len(notes_data),
            'notes': notes_data
        }

        # 序列化为 JSON
        json_bytes = json.dumps(
            backup_data,
            ensure_ascii=False,
            indent=2,
            default=str
        ).encode('utf-8')

        # 创建文件响应
        file_obj = BytesIO(json_bytes)
        filename = f"vault_export_{user.username}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"

        return FileResponse(
            file_obj,
            as_attachment=True,
            filename=filename,
            content_type='application/json'
        )

    except Exception as e:
        logger.error(f"Vault export error: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': '导出失败，请稍后重试'
        }, status=500)

