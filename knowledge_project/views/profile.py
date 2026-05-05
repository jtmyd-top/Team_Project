"""knowledge_project.views.profile

用户资料 / 头像 / 邮箱 / 通知偏好 / 主题设置。从 legacy.py 拆出的 8 个视图。
"""
import json
import logging
import os

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from ..models import MessagePreference, Note, Profile, ProfileLike
from .upload import _delayed_delete_file

logger = logging.getLogger(__name__)


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
        "views_count": 0,  # 暂时默认为0，后续可以添加访问统计功能
        "is_liked": is_liked,
        # ✅ 添加 2FA 状态 - 现在 profile 一定存在
        "two_fa_enabled": profile.two_fa_enabled,
        "two_fa_method": profile.two_fa_method or 'totp',
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
            max_size = 1500 * 1024 * 1024 if is_video else 5 * 1024 * 1024
            max_size_mb = 1500 if is_video else 5

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
        if len(nickname) < 6:
            return JsonResponse({"status": "error", "message": "昵称至少6位"}, status=400)
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
            user.save(update_fields=["username"])
        if "bio" in updated_fields:
            profile.save(update_fields=["bio"])
        print(response_data)
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
    profile = getattr(request.user, 'profile', None)
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
    user.email = new_email
    user.save(update_fields=["email"])

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

        # 保存更新
        if update_fields:
            profile.save(update_fields=update_fields)
            logger.info(f"Updated notification preferences for user {user.id}: {update_fields}")
        if message_update_fields:
            message_pref.save(update_fields=message_update_fields + ["updated_at"])
            logger.info(f"Updated message notification preferences for user {user.id}: {message_update_fields}")

        if update_fields or message_update_fields:
            return JsonResponse({
                "status": "success",
                "message": "通知偏好设置已更新",
                "updated_fields": update_fields + message_update_fields
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
