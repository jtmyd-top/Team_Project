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
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.views.decorators.http import require_http_methods

from ..models import Asset, NoteAsset

logger = logging.getLogger(__name__)


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
