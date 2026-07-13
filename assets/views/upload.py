"""Asset upload endpoints and legacy compatibility surface."""
from .common import *  # noqa: F401,F403
from . import common as _common
from .media import protected_media_view, public_profile_media_view  # noqa: F401
from django.db import transaction
from accounts.storage_quota import (
    StorageQuotaExceeded,
    ensure_storage_available,
    lock_user_storage_quota,
    quota_exceeded_payload,
)


def _validate_image_upload(uploaded_file, *, ckeditor=False):
    _common.IMAGE_UPLOAD_MAX_SIZE = IMAGE_UPLOAD_MAX_SIZE
    _common.IMAGE_UPLOAD_MAX_SIZE_MB = IMAGE_UPLOAD_MAX_SIZE_MB
    _common.IMAGE_UPLOAD_ALLOWED_EXTENSIONS = IMAGE_UPLOAD_ALLOWED_EXTENSIONS
    _common.IMAGE_UPLOAD_ALLOWED_MIME_TYPES = IMAGE_UPLOAD_ALLOWED_MIME_TYPES
    _common.IMAGE_UPLOAD_MAGIC_NUMBERS = IMAGE_UPLOAD_MAGIC_NUMBERS
    return _common._validate_image_upload(uploaded_file, ckeditor=ckeditor)


@login_required
@require_http_methods(["POST"])
def image_upload_view(request):
    """
    处理图片上传，并包含用户级去重功能。
    此版本已移除对 Project 的依赖。
    """
    if 'file' not in request.FILES:
        return JsonResponse({'error': '没有找到上传的文件。'}, status=400)

    image_file = request.FILES['file']
    allowed, _count = _check_image_upload_rate_limit(request)
    if not allowed:
        return _json_upload_error('上传过于频繁，请稍后再试。', status=429)

    validation_error = _validate_image_upload(image_file)
    if validation_error:
        return validation_error

    current_user = request.user

    # 1. 计算文件哈希值 (这部分逻辑与您原来的一样)
    try:
        file_hash = calculate_file_hash(image_file)
    except Exception as e:
        logger.error(f"为用户 {current_user.id} 计算哈希值时出错: {e}", exc_info=True)
        return JsonResponse({'error': '无法处理该文件。'}, status=500)

    # --- 核心去重逻辑在这里，完全保留 ---
    # 2. 检查当前用户是否已上传过相同内容的文件
    try:
        # 这个查询与您原始代码中的查询完全相同！
        existing_asset = Asset.objects.filter(uploader=current_user, image_hash=file_hash).first()

        # 如果找到了重复的文件，就直接返回现有文件的URL
        if existing_asset and existing_asset.file:
            logger.info(f"为用户 {current_user.id} 检测到重复图片。")
            return JsonResponse({'location': existing_asset.get_protected_url()})

    except Exception as e:
        logger.error(f"查询重复图片时出错: {e}", exc_info=True)
        # 即使查询出错，我们也可以继续尝试保存，而不是中断流程

    # --- 如果不是重复文件，则在同一事务和用户锁内检查配额并保存 ---
    try:
        with transaction.atomic():
            lock_user_storage_quota(current_user)
            ensure_storage_available(current_user, getattr(image_file, 'size', 0) or 0)
            # 创建一个不包含文件的实例，先取得稳定的用户路径。
            new_asset = Asset(
                uploader=current_user,
                asset_type='image',
                image_hash=file_hash,
                name=image_file.name,
            )
            new_asset.save()
            new_asset.file = image_file
            new_asset.save()
        logger.info(f"为用户 {current_user.id} 上传了新图片。")
        return JsonResponse({'location': new_asset.get_protected_url()})
    except StorageQuotaExceeded as exc:
        return JsonResponse(quota_exceeded_payload(exc.summary), status=413)
    except Exception as e:
        logger.error(f"为用户 {current_user.id} 保存新图片失败: {e}", exc_info=True)
        if 'new_asset' in locals() and new_asset.pk:
            new_asset.delete()
        return JsonResponse({'error': '服务器保存文件时出错。'}, status=500)

@login_required
@require_http_methods(["POST"])
def ckeditor_image_upload_view(request):
    """
    处理 django-ckeditor-5 的图片上传请求。
    【最终修复版】：
    - 强制使用“两阶段保存”，确保用户文件夹路径正确。
    - 返回受保护的 URL (get_protected_url)，确保前端能正确显示。
    """
    if 'upload' not in request.FILES:
        return JsonResponse({'error': {'message': '没有找到上传的文件。'}}, status=400)

    image_file = request.FILES['upload']
    allowed, _count = _check_image_upload_rate_limit(request)
    if not allowed:
        return _json_upload_error('上传过于频繁，请稍后再试。', status=429, ckeditor=True)

    validation_error = _validate_image_upload(image_file, ckeditor=True)
    if validation_error:
        return validation_error

    current_user = request.user

    # 1. 计算哈希值 (逻辑不变)
    try:
        file_hash = calculate_file_hash(image_file)
    except Exception as e:
        logger.error(f"[CKEditor] 为用户 {current_user.id} 计算哈希值时出错: {e}", exc_info=True)
        return JsonResponse({'error': {'message': '无法处理该文件。'}}, status=500)

    # 2. 检查重复 (逻辑不变，但返回的 URL 需要修改)
    try:
        existing_asset = Asset.objects.filter(uploader=current_user, image_hash=file_hash).first()
        if existing_asset and existing_asset.file:
            logger.info(f"[CKEditor] 为用户 {current_user.id} 检测到重复图片。")
            # 【核心修改】直接返回 get_protected_url() 生成的相对路径
            return JsonResponse({'url': existing_asset.get_protected_url()})
    except Exception as e:
        logger.error(f"[CKEditor] 查询重复图片时出错: {e}", exc_info=True)

    # 3. 同一事务和用户锁内检查配额并保存。
    try:
        with transaction.atomic():
            lock_user_storage_quota(current_user)
            ensure_storage_available(current_user, getattr(image_file, 'size', 0) or 0)
            new_asset = Asset(
                uploader=current_user,
                asset_type='image',
                image_hash=file_hash,
                name=image_file.name,
            )
            new_asset.save()
            new_asset.file = image_file
            new_asset.save()
        logger.info(f"[CKEditor] 为用户 {current_user.id} 上传了新图片。")
        return JsonResponse({'url': new_asset.get_protected_url()})
    except StorageQuotaExceeded as exc:
        return JsonResponse(quota_exceeded_payload(exc.summary), status=413)
    except Exception as e:
        logger.error(f"[CKEditor] 为用户 {current_user.id} 保存新图片失败: {e}", exc_info=True)
        if 'new_asset' in locals() and new_asset.pk:
            new_asset.delete()
        return JsonResponse({'error': {'message': '服务器保存文件时出错。'}}, status=500)


__all__ = [
    '_check_image_upload_rate_limit',
    '_json_upload_error',
    '_sniff_image_header',
    '_validate_image_upload',
    '_delayed_delete_file',
    'calculate_file_hash',
    'IMAGE_UPLOAD_MAX_SIZE',
    'IMAGE_UPLOAD_ALLOWED_EXTENSIONS',
    'IMAGE_UPLOAD_ALLOWED_MIME_TYPES',
    'IMAGE_UPLOAD_MAGIC_NUMBERS',
    'IMAGE_UPLOAD_MAX_SIZE_MB',
    'IMAGE_UPLOAD_RATE_LIMIT_COUNT',
    'IMAGE_UPLOAD_RATE_LIMIT_WINDOW',
    'Profile',
    'Asset',
    'NoteAsset',
    'image_upload_view',
    'ckeditor_image_upload_view',
    'protected_media_view',
    'public_profile_media_view',
]
