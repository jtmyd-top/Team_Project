"""Shared upload and media helpers."""
import hashlib
import logging
import mimetypes
import os
import threading
from pathlib import Path

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

from accounts.models import Profile
from assets.models import Asset, NoteAsset
from core.utils.accelerated_media import media_file_response
from core.utils.request_utils import check_rate_limit_atomic, get_client_ip

logger = logging.getLogger(__name__)

IMAGE_UPLOAD_MAX_SIZE = getattr(settings, 'IMAGE_UPLOAD_MAX_SIZE', 10 * 1024 * 1024)
IMAGE_UPLOAD_ALLOWED_EXTENSIONS = {
    ext.lower()
    for ext in getattr(settings, 'IMAGE_UPLOAD_ALLOWED_EXTENSIONS', ['.jpg', '.jpeg', '.png', '.gif', '.webp'])
}
IMAGE_UPLOAD_ALLOWED_MIME_TYPES = set(getattr(settings, 'IMAGE_UPLOAD_ALLOWED_MIME_TYPES', [
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
]))
IMAGE_UPLOAD_MAGIC_NUMBERS = {
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.gif': (b'GIF87a', b'GIF89a'),
    '.webp': (b'RIFF',),
}
IMAGE_UPLOAD_MAX_SIZE_MB = max(1, IMAGE_UPLOAD_MAX_SIZE // (1024 * 1024))
IMAGE_UPLOAD_RATE_LIMIT_COUNT = getattr(settings, 'IMAGE_UPLOAD_RATE_LIMIT_COUNT', 20)
IMAGE_UPLOAD_RATE_LIMIT_WINDOW = getattr(settings, 'IMAGE_UPLOAD_RATE_LIMIT_WINDOW', 3600)


def _check_image_upload_rate_limit(request):
    user_part = f'user:{request.user.id}' if request.user.is_authenticated else f'ip:{get_client_ip(request)}'
    key = f'image_upload_rate:{user_part}'
    allowed, count = check_rate_limit_atomic(key, IMAGE_UPLOAD_RATE_LIMIT_COUNT, IMAGE_UPLOAD_RATE_LIMIT_WINDOW)
    return allowed, count

def _json_upload_error(message, status=400, ckeditor=False):
    if ckeditor:
        return JsonResponse({'error': {'message': message}}, status=status)
    return JsonResponse({'error': message}, status=status)

def _sniff_image_header(uploaded_file, read_size=16):
    current_position = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        return uploaded_file.read(read_size)
    finally:
        uploaded_file.seek(current_position)

def _validate_image_upload(uploaded_file, *, ckeditor=False):
    """
    Validate rich-text image uploads before hashing/saving.

    Checks are intentionally layered because MIME headers and file extensions can
    be forged independently. The final magic-number check verifies the actual
    file signature for the image formats this project allows.
    """
    if not uploaded_file:
        return _json_upload_error('没有找到上传的文件。', ckeditor=ckeditor)

    size = getattr(uploaded_file, 'size', 0) or 0
    if size <= 0:
        return _json_upload_error('上传文件不能为空。', ckeditor=ckeditor)
    if size > IMAGE_UPLOAD_MAX_SIZE:
        return _json_upload_error(f'图片大小不能超过 {IMAGE_UPLOAD_MAX_SIZE_MB}MB。', ckeditor=ckeditor)

    original_name = uploaded_file.name or ''
    extension = Path(original_name).suffix.lower()
    if extension not in IMAGE_UPLOAD_ALLOWED_EXTENSIONS:
        return _json_upload_error('只支持 JPG、PNG、GIF、WebP 图片格式。', ckeditor=ckeditor)

    declared_mime = uploaded_file.content_type or mimetypes.guess_type(original_name)[0] or ''
    if declared_mime not in IMAGE_UPLOAD_ALLOWED_MIME_TYPES:
        return _json_upload_error('文件 MIME 类型不受支持。', ckeditor=ckeditor)

    header = _sniff_image_header(uploaded_file)
    magic_numbers = IMAGE_UPLOAD_MAGIC_NUMBERS.get(extension, ())
    if extension == '.webp':
        is_valid_magic = header.startswith(b'RIFF') and header[8:12] == b'WEBP'
    else:
        is_valid_magic = any(header.startswith(signature) for signature in magic_numbers)
    if not is_valid_magic:
        return _json_upload_error('文件内容与图片格式不匹配。', ckeditor=ckeditor)

    return None

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

def calculate_file_hash(file):
    """高效计算文件的 SHA256 哈希值"""
    hasher = hashlib.sha256()
    # 以块的形式读取，防止大文件撑爆内存
    for chunk in file.chunks():
        hasher.update(chunk)
    # 将文件指针移回开头，以便 Django 后续可以正常保存文件
    file.seek(0)
    return hasher.hexdigest()


__all__ = [
    'hashlib',
    'logging',
    'mimetypes',
    'os',
    'threading',
    'Path',
    'settings',
    'login_required',
    'Q',
    'Http404',
    'HttpResponse',
    'HttpResponseForbidden',
    'JsonResponse',
    'require_http_methods',
    'Profile',
    'Asset',
    'NoteAsset',
    'media_file_response',
    'check_rate_limit_atomic',
    'get_client_ip',
    'logger',
    'IMAGE_UPLOAD_MAX_SIZE',
    'IMAGE_UPLOAD_ALLOWED_EXTENSIONS',
    'IMAGE_UPLOAD_ALLOWED_MIME_TYPES',
    'IMAGE_UPLOAD_MAGIC_NUMBERS',
    'IMAGE_UPLOAD_MAX_SIZE_MB',
    'IMAGE_UPLOAD_RATE_LIMIT_COUNT',
    'IMAGE_UPLOAD_RATE_LIMIT_WINDOW',
    '_check_image_upload_rate_limit',
    '_json_upload_error',
    '_sniff_image_header',
    '_validate_image_upload',
    '_delayed_delete_file',
    'calculate_file_hash',
]
