"""knowledge_project.views.upload

文件 / 图片上传与受保护媒体访问。从 legacy.py 拆出的 5 个函数。
"""
import hashlib
import logging
import mimetypes
import os
import threading

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.views.decorators.http import require_http_methods

from ..models import Asset, NoteAsset, Profile
from ..utils.accelerated_media import media_file_response

logger = logging.getLogger(__name__)

# 文件上传限制配置
MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', 10 * 1024 * 1024))  # 默认10MB
ALLOWED_IMAGE_TYPES = {
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
    'image/svg+xml',
}
ALLOWED_FILE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.md', '.csv', '.zip', '.rar',
}


def validate_upload_file(uploaded_file, allowed_types=None, max_size=None):
    """
    验证上传文件的大小和类型

    Args:
        uploaded_file: Django UploadedFile 对象
        allowed_types: 允许的MIME类型集合，None表示允许所有图片类型
        max_size: 最大文件大小（字节），None表示使用默认值

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if max_size is None:
        max_size = MAX_UPLOAD_SIZE

    if allowed_types is None:
        allowed_types = ALLOWED_IMAGE_TYPES

    # 1. 检查文件大小
    if uploaded_file.size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        return False, f'文件大小超过限制（最大 {max_size_mb:.1f}MB）'

    # 2. 检查 MIME 类型
    content_type = uploaded_file.content_type
    if content_type not in allowed_types:
        return False, f'不支持的文件类型：{content_type}'

    # 3. 检查文件扩展名
    file_name = uploaded_file.name.lower()
    file_ext = os.path.splitext(file_name)[1]
    if file_ext not in ALLOWED_FILE_EXTENSIONS:
        return False, f'不支持的文件扩展名：{file_ext}'

    # 4. 基本的文件头验证（防止恶意文件伪装）
    try:
        uploaded_file.seek(0)
        file_header = uploaded_file.read(12)
        uploaded_file.seek(0)

        # 验证常见图片格式的文件头
        if content_type == 'image/jpeg' and not file_header.startswith(b'\xff\xd8\xff'):
            return False, '文件内容与声明的JPEG格式不符'
        elif content_type == 'image/png' and not file_header.startswith(b'\x89PNG\r\n\x1a\n'):
            return False, '文件内容与声明的PNG格式不符'
        elif content_type == 'image/gif' and not file_header.startswith((b'GIF87a', b'GIF89a')):
            return False, '文件内容与声明的GIF格式不符'
        elif content_type == 'image/webp' and not (b'RIFF' in file_header and b'WEBP' in uploaded_file.read(4)):
            uploaded_file.seek(0)
            return False, '文件内容与声明的WebP格式不符'

    except Exception as e:
        logger.warning(f"文件头验证失败: {e}")
        # 验证失败不阻止上传，但记录日志

    return True, ''


def _delayed_delete_file(file_path, delay=3):
    """
    延迟删除文件，避免 Windows 文件占用问题
    delay: 延迟秒数
    """
    def delete_file():
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"延迟删除文件成功: {file_path}")
        except OSError as e:
            logger.warning(f"延迟删除文件仍然失败: {file_path}, 错误: {e}")

    # 使用 Timer 延迟删除
    timer = threading.Timer(delay, delete_file)
    timer.daemon = True  # 设置为守护线程，主程序退出时自动结束
    timer.start()


# --- 【新增】哈希计算辅助函数 ---
def calculate_file_hash(file):
    """高效计算文件的 SHA256 哈希值"""
    hasher = hashlib.sha256()
    # 以块的形式读取，防止大文件撑爆内存
    for chunk in file.chunks():
        hasher.update(chunk)
    # 将文件指针移回开头，以便 Django 后续可以正常保存文件
    file.seek(0)
    return hasher.hexdigest()


# --- 【新增】TinyMCE 图片上传视图 ---
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
    current_user = request.user

    # 0. 验证文件
    is_valid, error_msg = validate_upload_file(image_file)
    if not is_valid:
        logger.warning(f"用户 {current_user.id} 上传验证失败: {error_msg}")
        return JsonResponse({'error': error_msg}, status=400)

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

    # --- 如果不是重复文件，则执行保存逻辑 ---
    # 3. 采用“两阶段保存”策略，保存新文件
    try:
        # 创建一个不包含文件的实例
        new_asset = Asset(
            uploader=current_user,
            asset_type='image',
            image_hash=file_hash,
            name=image_file.name
            # 注意：project=None 已经不再需要，因为模型里没有这个字段了
        )
        new_asset.save()  # 第一次保存

        # 关联并保存文件
        new_asset.file = image_file
        new_asset.save()  # 第二次保存

        logger.info(f"为用户 {current_user.id} 上传了新图片。")
        return JsonResponse({'location': new_asset.get_protected_url()})

    except Exception as e:
        logger.error(f"为用户 {current_user.id} 保存新图片失败: {e}", exc_info=True)
        # 清理可能产生的孤立记录
        if 'new_asset' in locals() and new_asset.pk:
            new_asset.delete()
        return JsonResponse({'error': '服务器保存文件时出错。'}, status=500)


def protected_media_view(request, file_path):
    """
    受保护的媒体文件视图，支持公开笔记的图片访问。
    权限规则：
    1. 上传者本人可以访问
    2. 如果请求来自公开笔记页面，允许匿名访问
    """
    try:
        asset = Asset.objects.get(file=file_path)
    except Asset.DoesNotExist:
        raise Http404

    # 检查用户是否已登录且是上传者
    is_authenticated = request.user.is_authenticated
    is_uploader = is_authenticated and asset.uploader == request.user

    # 仅当资源真实被公开笔记引用时，才允许匿名访问
    is_referenced_by_public_note = bool(
        NoteAsset.objects.filter(
            asset=asset,
            note__is_public=True,
            note__is_trashed=False,
        ).exists()
    )

    # 权限判断：上传者本人 或 资源被公开笔记显式引用
    if not is_uploader and not is_referenced_by_public_note:
        return HttpResponseForbidden("您无权访问此文件。")

    # 防路径穿越：确保最终路径始终在 MEDIA_ROOT 下
    normalized_file_path = os.path.normpath(file_path).lstrip('/\\')
    file_full_path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, normalized_file_path))
    media_root_norm = os.path.normpath(settings.MEDIA_ROOT)
    if file_full_path != media_root_norm and not file_full_path.startswith(media_root_norm + os.sep):
        raise Http404

    try:
        with open(file_full_path, 'rb') as f:
            content_type, _ = mimetypes.guess_type(file_full_path)
            return HttpResponse(f.read(), content_type=content_type or 'application/octet-stream')
    except FileNotFoundError:
        raise Http404


def public_profile_media_view(request, file_path):
    """
    Serve public profile media under MEDIA_URL without exposing arbitrary uploads.

    In production DEBUG=False, Django does not add the automatic MEDIA_URL route.
    Avatars and profile banners are intentionally public, but regular uploaded
    note/message files must keep using their permission-checked endpoints.
    """
    normalized_file_path = str(file_path or '').replace('\\', '/').lstrip('/')
    if not Profile.objects.filter(
        Q(avatar=normalized_file_path) | Q(banner_image=normalized_file_path)
    ).exists():
        raise Http404

    return media_file_response(normalized_file_path)


@login_required
@require_http_methods([“POST”])
def ckeditor_image_upload_view(request):
    “””
    处理 django-ckeditor-5 的图片上传请求。
    【最终修复版】：
    - 强制使用”两阶段保存”，确保用户文件夹路径正确。
    - 返回受保护的 URL (get_protected_url)，确保前端能正确显示。
    “””
    if 'upload' not in request.FILES:
        return JsonResponse({'error': {'message': '没有找到上传的文件。'}}, status=400)

    image_file = request.FILES['upload']
    current_user = request.user

    # 0. 验证文件
    is_valid, error_msg = validate_upload_file(image_file)
    if not is_valid:
        logger.warning(f”[CKEditor] 用户 {current_user.id} 上传验证失败: {error_msg}”)
        return JsonResponse({'error': {'message': error_msg}}, status=400)

    # 1. 计算哈希值 (逻辑不变)
    try:
        file_hash = calculate_file_hash(image_file)
    except Exception as e:
        logger.error(f”[CKEditor] 为用户 {current_user.id} 计算哈希值时出错: {e}”, exc_info=True)
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

    # 3. 采用“两阶段保存” (逻辑不变)
    try:
        # 阶段一：保存元数据
        new_asset = Asset(
            uploader=current_user,
            asset_type='image',
            image_hash=file_hash,
            name=image_file.name
        )
        new_asset.save()

        # 阶段二：关联并保存文件
        new_asset.file = image_file
        new_asset.save()

        logger.info(f"[CKEditor] 为用户 {current_user.id} 上传了新图片。")
        # 【核心修改】直接返回新建资产的、受保护的相对URL
        return JsonResponse({'url': new_asset.get_protected_url()})

    except Exception as e:
        logger.error(f"[CKEditor] 为用户 {current_user.id} 保存新图片失败: {e}", exc_info=True)
        if 'new_asset' in locals() and new_asset.pk:
            new_asset.delete()
        return JsonResponse({'error': {'message': '服务器保存文件时出错。'}}, status=500)
