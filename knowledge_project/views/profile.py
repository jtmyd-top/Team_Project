"""knowledge_project.views.profile

用户资料 / 头像 / 邮箱 / 通知偏好 / 主题设置。从 legacy.py 拆出的 8 个视图。
"""
import json
import logging
import os
import re
from datetime import time, timedelta

from django.contrib.sessions.models import Session
from django.contrib.staticfiles import finders
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import (
    LoginDevice,
    MessageGroup,
    MessagePreference,
    Note,
    Profile,
    ProfileLike,
    ProfileVisit,
    SecurityAuditLog,
)
from ..utils.request_utils import get_client_ip
from .upload import _delayed_delete_file

logger = logging.getLogger(__name__)
USERNAME_REGEX = re.compile(r'^[a-z][a-z0-9_]{5,}$')


def _available_email_mention_groups(user):
    return (
        MessageGroup.objects
        .filter(is_active=True)
        .filter(
            Q(owner=user) |
            Q(memberships__user=user, memberships__left_at__isnull=True)
        )
        .distinct()
        .order_by('name', 'id')
    )


def _email_mention_group_payload(group):
    return {
        "id": group.id,
        "name": group.name,
    }


def _parse_quiet_time(value):
    if value in (None, ''):
        return None
    if not isinstance(value, str):
        raise ValueError('time must be a string')
    parsed = time.fromisoformat(value)
    return parsed.replace(second=0, microsecond=0)


def _static_asset_version(*paths):
    mtimes = []
    for path in paths:
        found = finders.find(path)
        candidates = found if isinstance(found, (list, tuple)) else [found]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                mtimes.append(os.path.getmtime(candidate))
    return str(int(max(mtimes))) if mtimes else "20260611-group-policy-fix2"


def _record_profile_visit(request, profile):
    if request.user.is_authenticated and request.user.id == profile.user_id:
        return
    if not request.session.session_key:
        request.session.save()
    ProfileVisit.objects.create(
        profile=profile,
        viewer=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or '',
        ip_address=get_client_ip(request),
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:255],
    )


def _device_payload(device, current_session_key=''):
    return {
        'id': device.id,
        'device_info': device.device_info,
        'ip_address': device.ip_address,
        'ip_location': device.ip_location,
        'user_agent': device.user_agent,
        'first_login_at': device.first_login_at.isoformat() if device.first_login_at else None,
        'last_login_at': device.last_login_at.isoformat() if device.last_login_at else None,
        'login_count': device.login_count,
        'is_trusted': device.is_trusted,
        'is_active': device.is_active,
        'revoked_at': device.revoked_at.isoformat() if device.revoked_at else None,
        'is_current': bool(current_session_key and device.session_key == current_session_key),
    }


@login_required
@require_http_methods(["GET"])
def security_devices_api(request):
    if not request.session.session_key:
        request.session.save()
    current_session_key = request.session.session_key or ''
    devices = (
        LoginDevice.objects
        .filter(user=request.user)
        .select_related('revoked_by')
        .order_by('-last_login_at', '-id')[:50]
    )
    return JsonResponse({
        'status': 'success',
        'devices': [_device_payload(device, current_session_key) for device in devices],
    })


@login_required
@require_http_methods(["POST"])
def revoke_security_device_api(request, device_id):
    if not request.session.session_key:
        request.session.save()
    current_session_key = request.session.session_key or ''
    try:
        device = LoginDevice.objects.get(id=device_id, user=request.user)
    except LoginDevice.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Device not found'}, status=404)

    if current_session_key and device.session_key == current_session_key:
        return JsonResponse({'status': 'error', 'message': 'Cannot revoke current session'}, status=400)

    now = timezone.now()
    if device.session_key:
        Session.objects.filter(session_key=device.session_key).delete()
    device.is_active = False
    device.revoked_at = now
    device.revoked_by = request.user
    device.save(update_fields=['is_active', 'revoked_at', 'revoked_by'])

    SecurityAuditLog.objects.create(
        user=request.user,
        actor=request.user,
        action=SecurityAuditLog.ACTION_DEVICE_REVOKED,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata={'device_id': device.id, 'device_info': device.device_info},
    )
    return JsonResponse({'status': 'success', 'device': _device_payload(device, current_session_key)})


@login_required
def settings_view(request):
    """
    用户个人设置页面
    """
    user = request.user

    # 确保 profile 存在
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        # 如果 profile 不存在，创建一个
        profile = Profile.objects.create(user=user)
        logger.info(f"Created profile for user {user.id} in settings_view")

    # 获取当前用户的笔记数量
    notes_count = Note.objects.filter(author=user, is_secret=False, is_trashed=False).count()

    # 检查当前用户是否已经点赞过自己的资料
    is_liked = ProfileLike.objects.filter(liker=user, profile=profile).exists()

    context = {
        "avatar_url": profile.avatar.url if profile.avatar else "/static/img/default-avatar.png",
        "nickname": user.username,
        "email": user.email,
        "bio": profile.bio if profile.bio else "",
        "likes_count": profile.likes_count,
        "notes_count": notes_count,
        "views_count": ProfileVisit.objects.filter(profile=profile).count(),
        "is_liked": is_liked,
        # ✅ 添加 2FA 状态 - 现在 profile 一定存在
        "two_fa_enabled": profile.two_fa_enabled,
        "two_fa_method": profile.two_fa_method or 'totp',
        "timestamp": _static_asset_version("dist/settings.js", "dist/assets/settings.css"),
    }

    # 添加调试日志
    logger.info(f"Settings view for user {user.id}: 2FA enabled={profile.two_fa_enabled}, method={profile.two_fa_method}")

    return render(request, "settings/setting.html", context)


@login_required
@require_http_methods(["POST"])
def upload_avatar(request):
    """上传并更新用户头像或横幅图"""
    # 检测是头像还是横幅
    avatar_file = request.FILES.get("avatar")
    banner_file = request.FILES.get("banner")

    user = request.user

    try:
        # 横幅图/视频上传
        if banner_file:
            # 验证文件类型（支持图片和视频）
            allowed_image_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
            allowed_video_types = ['video/mp4', 'video/webm']
            allowed_types = allowed_image_types + allowed_video_types

            if banner_file.content_type not in allowed_types:
                return JsonResponse({
                    "status": "error",
                    "message": "只支持 JPG、PNG、WebP、GIF、MP4 和 WebM 格式"
                }, status=400)

            # 验证文件大小（图片最大 5MB，视频最大 15MB）
            is_video = banner_file.content_type in allowed_video_types
            max_size = 15 * 1024 * 1024 if is_video else 5 * 1024 * 1024
            max_size_mb = 15 if is_video else 5

            if banner_file.size > max_size:
                return JsonResponse({
                    "status": "error",
                    "message": f"{'视频' if is_video else '图片'}大小不能超过 {max_size_mb}MB"
                }, status=400)

            # 【修复】先保存旧文件的路径，然后删除
            old_banner_path = None
            if user.profile.banner_image:
                try:
                    # 获取旧文件的完整路径
                    old_banner_path = user.profile.banner_image.path
                except (ValueError, AttributeError):
                    pass  # 如果文件不存在，忽略错误

            # 保存新横幅（先保存）
            user.profile.banner_image.save(banner_file.name, banner_file, save=True)

            # 【修复】获取新文件路径，只删除路径不同的旧文件
            try:
                new_banner_path = user.profile.banner_image.path
                # 只有当旧文件路径存在且与新文件路径不同时，才延迟删除
                if old_banner_path and old_banner_path != new_banner_path and os.path.exists(old_banner_path):
                    _delayed_delete_file(old_banner_path, delay=5)
            except (ValueError, AttributeError):
                pass

            return JsonResponse({
                "status": "success",
                "message": "横幅上传成功",
                "banner_url": request.build_absolute_uri(user.profile.banner_image.url),
                "is_video": is_video
            })

        # 头像上传
        elif avatar_file:
            # 验证文件类型（仅允许图片）
            allowed_avatar_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
            if avatar_file.content_type not in allowed_avatar_types:
                return JsonResponse({
                    "status": "error",
                    "message": "头像只支持 JPG、PNG、WebP、GIF 图片格式"
                }, status=400)

            # 验证文件大小（最大 5MB）
            if avatar_file.size > 5 * 1024 * 1024:
                return JsonResponse({
                    "status": "error",
                    "message": "头像图片大小不能超过 5MB"
                }, status=400)

            # 【修复】先保存旧文件的路径，然后删除
            old_avatar_path = None
            if user.profile.avatar:
                try:
                    # 获取旧文件的完整路径
                    old_avatar_path = user.profile.avatar.path
                except (ValueError, AttributeError):
                    pass  # 如果文件不存在，忽略错误

            # 保存新头像（先保存）
            user.profile.avatar.save(avatar_file.name, avatar_file, save=True)

            # 【修复】获取新文件路径，只删除路径不同的旧文件
            try:
                new_avatar_path = user.profile.avatar.path
                # 只有当旧文件路径存在且与新文件路径不同时，才延迟删除
                if old_avatar_path and old_avatar_path != new_avatar_path and os.path.exists(old_avatar_path):
                    _delayed_delete_file(old_avatar_path, delay=5)
            except (ValueError, AttributeError):
                pass

            return JsonResponse({
                "status": "success",
                "message": "头像上传成功",
                "avatar_url": request.build_absolute_uri(user.profile.avatar.url)
            })

        else:
            return JsonResponse({
                "status": "error",
                "message": "未选择文件"
            }, status=400)

    except Exception as e:
        logger.error(f"上传文件失败: {str(e)}", exc_info=True)
        return JsonResponse({"status": "error", "message": "上传失败，请稍后重试"}, status=500)


@login_required
@require_http_methods(["POST"])
def update_profile(request):
    """
    通用更新接口：可以单独更新昵称或 bio。
    前端通过发送不同字段决定更新内容。
    """
    try:
        data = json.loads(request.body)
        profile = request.user.profile
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "请求格式错误"}, status=400)

    user = request.user
    profile = getattr(user, "profile", None)

    updated_fields = []
    response_data = {"status": "success"}

    # 更新昵称
    nickname = data.get("nickname")
    if nickname is not None:
        nickname = nickname.strip()
        if not USERNAME_REGEX.fullmatch(nickname):
            return JsonResponse({
                "status": "error",
                "message": "用户名至少6位，以小写字母开头，只能包含字母、数字和下划线"
            }, status=400)
        if User.objects.filter(username__iexact=nickname).exclude(pk=user.pk).exists():
            return JsonResponse({"status": "error", "message": "用户名已被占用"}, status=400)
        user.username = nickname
        updated_fields.append("username")
        response_data["nickname"] = nickname

    # 更新个性签名
    bio = data.get("bio")

    if bio is not None:
        if len(bio) > 160:
            return JsonResponse({"status": "error", "message": "个性签名不能超过160字"}, status=400)
        profile.bio = bio
        updated_fields.append("bio")
        response_data["bio"] = bio

    if updated_fields:
        if "username" in updated_fields:
            try:
                user.save(update_fields=["username"])
            except IntegrityError:
                return JsonResponse({"status": "error", "message": "用户名已被占用"}, status=400)
        if "bio" in updated_fields:
            profile.save(update_fields=["bio"])
        return JsonResponse(response_data)

    return JsonResponse({"status": "error", "message": "没有任何更新字段"}, status=400)


@login_required
@require_http_methods(["POST"])
def update_email(request):
    """
    修改邮箱 (安全分步验证版)
    1. 验证密码 + 新邮箱验证码
    2. 如果需要，再验证 2FA
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    current_password = data.get("password", "")
    new_email = data.get("new_email", "").strip()
    code = data.get("code", "").strip()
    two_fa_code = data.get("two_fa_code", "").strip()
    use_backup = data.get("use_backup", False)

    if not current_password or not new_email or not code:
        return JsonResponse({"status": "error", "message": "缺少必要参数"}, status=400)

    # 1) 校验当前密码
    if not request.user.check_password(current_password):
        return JsonResponse({"status": "error", "message": "密码错误"}, status=400)

    # 2) 校验新邮箱的验证码
    info = request.session.get("email_change_verification")
    if not info or info.get("email") != new_email or info.get("code") != code:
        return JsonResponse({"status": "error", "message": "新邮箱的验证码错误或已过期"}, status=400)

    # 3) 检查邮箱是否已被占用
    if User.objects.filter(email__iexact=new_email).exclude(pk=request.user.pk).exists():
        return JsonResponse({"status": "error", "message": "该邮箱已被绑定"}, status=400)

    # 4) 检查并执行 2FA 验证
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.email_last_changed_at:
        cooldown_until = profile.email_last_changed_at + timedelta(hours=24)
        if cooldown_until > timezone.now():
            return JsonResponse({
                "status": "error",
                "message": "Email can only be changed once every 24 hours",
                "cooldown_until": cooldown_until.isoformat(),
            }, status=429)
    if profile and profile.two_fa_enabled:
        if not two_fa_code:
            # 如果需要 2FA 但未提供验证码，则要求输入
            # 【修复】不在这里发送邮件，由前端决定是否需要发送
            # 这样可以避免重复发送，并且让前端控制倒计时
            return JsonResponse({
                'status': 'require_2fa',
                'message': '需要两因素认证以完成操作',
                'method': profile.two_fa_method
            })

        # 如果提供了 2FA 验证码，则进行验证
        from ..decorators import verify_2fa_for_request
        success, message = verify_2fa_for_request(request, two_fa_code, use_backup)
        if not success:
            return JsonResponse({
                'status': 'error',
                'code': 'invalid_2fa',
                'message': message
            }, status=400)
        # 2FA 验证通过，继续执行

    # 5) 所有验证通过，更新邮箱
    user = request.user
    old_email = user.email
    user.email = new_email
    user.save(update_fields=["email"])
    profile.email_last_changed_at = timezone.now()
    profile.save(update_fields=["email_last_changed_at"])

    SecurityAuditLog.objects.create(
        user=user,
        actor=user,
        action=SecurityAuditLog.ACTION_EMAIL_CHANGED,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata={'old_email': old_email, 'new_email': new_email},
    )

    # 作废新邮箱的验证码 session
    if "email_change_verification" in request.session:
        del request.session["email_change_verification"]

    return JsonResponse({"status": "success", "email": user.email, "message": "邮箱修改成功"})


# ==================== 点赞功能 API ====================
@login_required
@require_http_methods(["POST"])
def toggle_profile_like(request):
    """
    切换对当前用户资料的点赞状态
    - 如果已点赞，则取消点赞
    - 如果未点赞，则添加点赞
    """
    user = request.user
    profile = user.profile

    try:
        # 检查是否已经点赞过
        like_record = ProfileLike.objects.filter(liker=user, profile=profile).first()

        if like_record:
            # 已点赞，执行取消点赞操作
            like_record.delete()
            profile.likes_count = max(0, profile.likes_count - 1)  # 确保不会小于0
            profile.save(update_fields=['likes_count'])
            is_liked = False
        else:
            # 未点赞，执行点赞操作
            ProfileLike.objects.create(liker=user, profile=profile)
            profile.likes_count += 1
            profile.save(update_fields=['likes_count'])
            is_liked = True

        return JsonResponse({
            "status": "success",
            "is_liked": is_liked,
            "likes_count": profile.likes_count
        })

    except Exception as e:
        logger.error(f"点赞操作失败 (用户: {user.id}): {str(e)}", exc_info=True)
        return JsonResponse({"status": "error", "message": "操作失败，请稍后重试"}, status=500)


# ==================== 通知偏好设置 API ====================
@login_required
@require_http_methods(["GET", "POST"])
def notification_preferences(request):
    """
    获取或更新用户的通知偏好设置
    GET: 返回当前通知偏好
    POST: 更新通知偏好
    """
    user = request.user

    # 确保profile存在
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=user)
        logger.info(f"Created profile for user {user.id} in notification_preferences")
    message_pref, _ = MessagePreference.objects.get_or_create(user=user)
    available_groups = list(_available_email_mention_groups(user))
    available_group_ids = [group.id for group in available_groups]
    selected_group_ids = list(
        message_pref.email_mention_groups
        .filter(id__in=available_group_ids)
        .values_list('id', flat=True)
    )

    if request.method == "GET":
        # 返回当前的通知偏好设置
        return JsonResponse({
            "status": "success",
            "preferences": {
                "notify_login": profile.notify_login,
                "notify_password_change": profile.notify_password_change,
                "notify_password_reset": profile.notify_password_reset,
                "notify_note_activities": profile.notify_note_activities,
                "notify_profile_likes": profile.notify_profile_likes,
                "email_messages": message_pref.notify_new_message,
                "notify_group_mentions_email": message_pref.notify_group_mentions_email,
                "email_mention_group_ids": selected_group_ids,
                "available_email_mention_groups": [
                    _email_mention_group_payload(group)
                    for group in available_groups
                ],
                "quiet_hours_enabled": message_pref.quiet_hours_enabled,
                "quiet_hours_start": message_pref.quiet_hours_start.strftime('%H:%M') if message_pref.quiet_hours_start else '',
                "quiet_hours_end": message_pref.quiet_hours_end.strftime('%H:%M') if message_pref.quiet_hours_end else '',
                "browser_enabled": message_pref.browser_new_message,
                "browser_messages": message_pref.browser_new_message,
            }
        })

    elif request.method == "POST":
        # 更新通知偏好设置
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

        # 更新各个通知选项（只更新前端传递的字段）
        update_fields = []

        if "notify_login" in data:
            profile.notify_login = bool(data["notify_login"])
            update_fields.append("notify_login")

        if "notify_password_change" in data:
            profile.notify_password_change = bool(data["notify_password_change"])
            update_fields.append("notify_password_change")

        if "notify_password_reset" in data:
            profile.notify_password_reset = bool(data["notify_password_reset"])
            update_fields.append("notify_password_reset")

        if "notify_note_activities" in data:
            profile.notify_note_activities = bool(data["notify_note_activities"])
            update_fields.append("notify_note_activities")

        if "notify_profile_likes" in data:
            profile.notify_profile_likes = bool(data["notify_profile_likes"])
            update_fields.append("notify_profile_likes")

        message_update_fields = []
        group_ids_changed = False
        group_ids = set()
        if "email_messages" in data:
            message_pref.notify_new_message = bool(data["email_messages"])
            message_update_fields.append("notify_new_message")
        if "notify_new_message" in data:
            message_pref.notify_new_message = bool(data["notify_new_message"])
            if "notify_new_message" not in message_update_fields:
                message_update_fields.append("notify_new_message")
        if "browser_enabled" in data:
            message_pref.browser_new_message = bool(data["browser_enabled"])
            message_update_fields.append("browser_new_message")
        if "browser_messages" in data:
            message_pref.browser_new_message = bool(data["browser_messages"])
            if "browser_new_message" not in message_update_fields:
                message_update_fields.append("browser_new_message")
        if "notify_group_mentions_email" in data:
            message_pref.notify_group_mentions_email = bool(data["notify_group_mentions_email"])
            message_update_fields.append("notify_group_mentions_email")
        if "quiet_hours_enabled" in data:
            message_pref.quiet_hours_enabled = bool(data["quiet_hours_enabled"])
            message_update_fields.append("quiet_hours_enabled")
        if "quiet_hours_start" in data:
            try:
                message_pref.quiet_hours_start = _parse_quiet_time(data.get("quiet_hours_start"))
            except ValueError:
                return JsonResponse({"status": "error", "message": "quiet_hours_start must be HH:MM"}, status=400)
            message_update_fields.append("quiet_hours_start")
        if "quiet_hours_end" in data:
            try:
                message_pref.quiet_hours_end = _parse_quiet_time(data.get("quiet_hours_end"))
            except ValueError:
                return JsonResponse({"status": "error", "message": "quiet_hours_end must be HH:MM"}, status=400)
            message_update_fields.append("quiet_hours_end")
        if "email_mention_group_ids" in data:
            raw_group_ids = data.get("email_mention_group_ids") or []
            if not isinstance(raw_group_ids, list):
                return JsonResponse({"status": "error", "message": "email_mention_group_ids must be a list"}, status=400)
            try:
                group_ids = {int(group_id) for group_id in raw_group_ids}
            except (TypeError, ValueError):
                return JsonResponse({"status": "error", "message": "email_mention_group_ids contains invalid group ids"}, status=400)
            if not group_ids.issubset(available_group_ids):
                return JsonResponse({"status": "error", "message": "Only joined or owned groups can be selected"}, status=400)
            group_ids_changed = True

        # 保存更新
        if update_fields:
            profile.save(update_fields=update_fields)
            logger.info(f"Updated notification preferences for user {user.id}: {update_fields}")
        if message_update_fields:
            message_pref.save(update_fields=message_update_fields + ["updated_at"])
            logger.info(f"Updated message notification preferences for user {user.id}: {message_update_fields}")
        if group_ids_changed:
            message_pref.email_mention_groups.set(group_ids)
            logger.info(f"Updated group mention email groups for user {user.id}: {sorted(group_ids)}")

        if update_fields or message_update_fields or group_ids_changed:
            updated_fields = update_fields + message_update_fields
            if group_ids_changed:
                updated_fields.append("email_mention_group_ids")
            return JsonResponse({
                "status": "success",
                "message": "通知偏好设置已更新",
                "updated_fields": updated_fields
            })
        return JsonResponse({
            "status": "warning",
            "message": "没有需要更新的字段"
        })


# ==================== 主题设置 API ====================
@login_required
@require_http_methods(["GET", "POST"])
def theme_settings(request):
    """
    获取或更新用户的主题设置
    GET: 返回当前主题设置
    POST: 更新主题设置
    """
    user = request.user

    # 确保profile存在
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=user)
        logger.info(f"Created profile for user {user.id} in theme_settings")

    if request.method == "GET":
        # 返回当前的主题设置
        return JsonResponse({
            "status": "success",
            "settings": {  # 改为 settings 以匹配前端期望
                "mode": profile.theme.get('mode', 'light'),
                "primary_color": profile.theme.get('primary_color', '#409EFF'),
                "font_size": profile.theme.get('font_size', 14),
                "compact_mode": profile.theme.get('compact_mode', False),
                "animations": profile.theme.get('animations', True),
                "layout": profile.layout_mode,
            }
        })

    elif request.method == "POST":
        # 更新主题设置
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

        # 更新theme字段（JSONField）- 支持所有主题相关字段
        theme_updated = False

        # 处理模式设置
        if "mode" in data:
            profile.theme['mode'] = data['mode']
            theme_updated = True

        # 处理主题色 - 支持两种命名方式
        if "primary_color" in data:
            profile.theme['primary_color'] = data['primary_color']
            theme_updated = True
        elif "primaryColor" in data:  # 兼容旧版本
            profile.theme['primary_color'] = data['primaryColor']
            theme_updated = True

        # 处理字体大小
        if "font_size" in data:
            profile.theme['font_size'] = int(data['font_size'])
            theme_updated = True

        # 处理紧凑模式
        if "compact_mode" in data:
            profile.theme['compact_mode'] = bool(data['compact_mode'])
            theme_updated = True

        # 处理动画设置
        if "animations" in data:
            profile.theme['animations'] = bool(data['animations'])
            theme_updated = True

        # 更新layout_mode字段
        layout_updated = False
        if "layout" in data:
            profile.layout_mode = data['layout']
            layout_updated = True

        # 保存更新
        update_fields = []
        if theme_updated:
            update_fields.append('theme')
            update_fields.append('last_theme_update')
        if layout_updated:
            update_fields.append('layout_mode')

        if update_fields:
            profile.save(update_fields=update_fields)
            logger.info(f"Updated theme settings for user {user.id}: {data}")

            return JsonResponse({
                "status": "success",
                "message": "主题设置已保存",
                "settings": {  # 返回更新后的设置
                    "mode": profile.theme.get('mode', 'light'),
                    "primary_color": profile.theme.get('primary_color', '#409EFF'),
                    "font_size": profile.theme.get('font_size', 14),
                    "compact_mode": profile.theme.get('compact_mode', False),
                    "animations": profile.theme.get('animations', True),
                    "layout": profile.layout_mode,
                }
            })
        else:
            return JsonResponse({
                "status": "warning",
                "message": "没有需要更新的字段"
            })


# ==================== 主题测试页面 ====================
def theme_test_view(request):
    """
    主题功能测试页面
    """
    # 不需要登录，方便测试
    return render(request, 'theme_test.html')


# ==================== 用户公开主页 ====================
@require_http_methods(["GET"])
def user_public_profile_view(request, user_id):
    """用户公开主页：展示用户的公开笔记、统计与简介"""
    from django.db.models import Count
    from django.shortcuts import get_object_or_404
    from ..models import UserFollow, UserBlocklist
    from .message import _get_avatar_url

    target = get_object_or_404(User, id=user_id)
    profile = target.profile
    is_self = request.user.is_authenticated and request.user.id == target.id
    _record_profile_visit(request, profile)

    public_notes_qs = Note.objects.filter(
        author=target, is_public=True
    ).select_related('author').prefetch_related('tags').annotate(
        comments_count=Count('comments')
    ).order_by('-updated_at')

    notes_count = public_notes_qs.count()
    views_count = ProfileVisit.objects.filter(profile=profile).count()
    likes_count = ProfileLike.objects.filter(profile=profile).count()
    followers_count = UserFollow.objects.filter(following=target).count()
    following_count = UserFollow.objects.filter(follower=target).count()

    is_following = False
    is_blocked = False
    blocked_me = False
    if request.user.is_authenticated and not is_self:
        is_following = UserFollow.objects.filter(
            follower=request.user, following=target
        ).exists()
        is_blocked = UserBlocklist.objects.filter(
            user=request.user, blocked_user=target
        ).exists()
        blocked_me = UserBlocklist.objects.filter(
            user=target, blocked_user=request.user
        ).exists()

    banner_url = profile.banner_image.url if profile.banner_image else ''
    banner_is_video = bool(banner_url.lower().split('?', 1)[0].endswith(('.mp4', '.webm', '.ogg')))

    notes_data = []
    for note in public_notes_qs[:50]:
        notes_data.append({
            'id': note.id,
            'public_id': str(note.public_id) if note.public_id else None,
            'title': note.title,
            'views': note.views or 0,
            'comments_count': note.comments_count,
            'created_at': note.created_at,
            'updated_at': note.updated_at,
            'tags': [t.name for t in note.tags.all()][:8],
        })

    context = {
        'profile_user': target,
        'avatar_url': _get_avatar_url(target),
        'banner_url': banner_url,
        'banner_is_video': banner_is_video,
        'bio': profile.bio or '',
        'notes': notes_data,
        'notes_count': notes_count,
        'views_count': views_count,
        'likes_count': likes_count,
        'followers_count': followers_count,
        'following_count': following_count,
        'is_self': is_self,
        'is_authenticated': request.user.is_authenticated,
        'is_following': is_following,
        'is_blocked': is_blocked,
        'blocked_me': blocked_me,
    }
    return render(request, 'profile/user_public_profile.html', context)
