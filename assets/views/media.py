"""Asset media serving endpoints."""
from .common import *  # noqa: F401,F403


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

