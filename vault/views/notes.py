"""Vault notes views."""
from .common import *  # noqa: F401, F403


@login_required
@require_http_methods(["GET"])
def vault_notes_list(request):
    """
    获取保密柜中的笔记列表
    需要先通过2FA验证
    """
    user = request.user
    profile = getattr(user, 'profile', None)

    # 检查2FA验证状态
    if profile and profile.two_fa_enabled:
        if not check_vault_access(request):  # 【修复】传 request 而不是 user
            return JsonResponse({
                'status': 'require_vault_2fa',
                'code': 'require_vault_2fa',
                'message': '访问保密柜需要两因素认证验证',
                'method': profile.two_fa_method
            })

    # 获取保密笔记列表
    notes = Note.objects.filter(
        author=user,
        is_secret=True,
        is_trashed=False
    ).order_by('-updated_at')

    notes_data = [{
        'id': note.id,
        'title': note.title,
        'created_at': note.created_at.isoformat(),
        'updated_at': note.updated_at.isoformat(),
        'is_favorited': note.is_favorited,
        'is_secret': note.is_secret,  # 保密标志
        'folder_id': note.folder_id,
        'is_trashed': note.is_trashed
    } for note in notes]

    return JsonResponse({
        'status': 'success',
        'notes': notes_data,
        'remaining_seconds': get_vault_access_remaining(request) if profile and profile.two_fa_enabled else 0  # 【修复】传 request 而不是 user
    })

