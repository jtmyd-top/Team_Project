# knowledge_project/message_views.py
"""私信 / 用户屏蔽 / 用户搜索与公开资料相关视图

原属于 views.py 5416-5865 段。抽出后 views.py 底部 re-export 兼容。
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import Note, ProfileLike

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
@login_required
def send_message_api(request):
    """发送私信"""
    try:
        from ..models import Message, MessagePreference, UserBlocklist

        data = json.loads(request.body)
        recipient_id = data.get('recipient_id')
        content = data.get('content', '').strip()

        # 验证参数
        if not recipient_id or not content:
            return JsonResponse({'error': '缺少必需参数'}, status=400)

        if len(content) > 5000:
            return JsonResponse({'error': '消息内容不能超过5000字'}, status=400)

        recipient = get_object_or_404(User, id=recipient_id)

        # 检查发送者是否被屏蔽
        is_blocked = UserBlocklist.objects.filter(
            user=recipient,
            blocked_user=request.user
        ).exists()

        if is_blocked:
            return JsonResponse({'error': '无法向此用户发送私信'}, status=403)

        # 检查接收者的私信设置（默认关闭，需用户手动开启）
        pref, _ = MessagePreference.objects.get_or_create(user=recipient)
        if not pref.allow_messages or pref.message_mode == 'disabled':
            return JsonResponse({'error': '此用户未开启私信功能'}, status=403)

        # 创建私信
        message = Message.objects.create(
            sender=request.user,
            recipient=recipient,
            content=content
        )

        def get_avatar(user):
            try:
                if user.profile.avatar:
                    return user.profile.avatar.url
            except:
                pass
            return '/static/img/default-avatar.png'

        return JsonResponse({
            'status': 'success',
            'message': {
                'id': message.id,
                'sender': message.sender.username,
                'sender_id': message.sender.id,
                'sender_avatar': get_avatar(message.sender),
                'recipient': message.recipient.username,
                'recipient_id': message.recipient.id,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
                'is_read': message.is_read,
            }
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        logger.error(f"发送私信错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def get_messages_api(request):
    """获取私信对话列表（与某个用户的所有私信）"""
    try:
        from ..models import Message

        other_user_id = request.GET.get('user_id')
        if not other_user_id:
            return JsonResponse({'error': '缺少user_id参数'}, status=400)

        other_user = get_object_or_404(User, id=other_user_id)

        # 获取与指定用户的所有私信（双向）
        messages = Message.objects.filter(
            (Q(sender=request.user) & Q(recipient=other_user)) |
            (Q(sender=other_user) & Q(recipient=request.user))
        ).order_by('created_at')

        # 标记接收到的消息为已读
        unread_messages = messages.filter(recipient=request.user, is_read=False)
        for msg in unread_messages:
            msg.is_read = True
            msg.read_at = timezone.now()
            msg.save()

        def get_avatar(user):
            try:
                if user.profile.avatar:
                    return user.profile.avatar.url
            except:
                pass
            return '/static/img/default-avatar.png'

        data = [
            {
                'id': m.id,
                'sender': m.sender.username,
                'sender_id': m.sender.id,
                'sender_avatar': get_avatar(m.sender),
                'recipient': m.recipient.username,
                'recipient_id': m.recipient.id,
                'content': m.content,
                'created_at': m.created_at.isoformat(),
                'is_read': m.is_read,
                'read_at': m.read_at.isoformat() if m.read_at else None,
            }
            for m in messages
        ]

        return JsonResponse({
            'status': 'success',
            'messages': data,
            'other_user': {
                'id': other_user.id,
                'username': other_user.username,
                'avatar': get_avatar(other_user),
            }
        })
    except Exception as e:
        logger.error(f"获取私信列表错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def get_message_conversations_api(request):
    """获取私信对话列表（用于消息列表页面）"""
    try:
        from ..models import Message

        # 获取与当前用户相关的所有消息
        messages = Message.objects.filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).order_by('-created_at')

        # 按对方用户分组获取最新消息
        conversations = {}
        for msg in messages:
            other_user = msg.recipient if msg.sender == request.user else msg.sender
            if other_user.id not in conversations:
                conversations[other_user.id] = {
                    'user_id': other_user.id,
                    'username': other_user.username,
                    'last_message': msg.content,
                    'last_message_time': msg.created_at,
                    'unread_count': 0,
                }
                # 计算未读消息数
                unread = Message.objects.filter(
                    sender=other_user,
                    recipient=request.user,
                    is_read=False
                ).count()
                conversations[other_user.id]['unread_count'] = unread

        def get_avatar(user):
            try:
                if user.profile.avatar:
                    return user.profile.avatar.url
            except:
                pass
            return '/static/img/default-avatar.png'

        data = sorted(
            [
                {
                    **conv,
                    'avatar': get_avatar(User.objects.get(id=conv['user_id'])),
                    'last_message_time': conv['last_message_time'].isoformat(),
                }
                for conv in conversations.values()
            ],
            key=lambda x: x['last_message_time'],
            reverse=True
        )

        return JsonResponse({
            'status': 'success',
            'conversations': data
        })
    except Exception as e:
        logger.error(f"获取对话列表错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def get_message_preference_api(request):
    """获取用户的私信偏好设置"""
    try:
        from ..models import MessagePreference

        target_user_id = request.GET.get('user_id')

        if target_user_id:
            # 获取其他用户的公开设置
            target_user = get_object_or_404(User, id=target_user_id)
            pref, _ = MessagePreference.objects.get_or_create(user=target_user)
        else:
            # 获取当前用户的所有设置
            pref, _ = MessagePreference.objects.get_or_create(user=request.user)

        return JsonResponse({
            'status': 'success',
            'preference': {
                'allow_messages': pref.allow_messages,
                'message_mode': pref.message_mode,
                'show_read_status': pref.show_read_status,
                'auto_reply_enabled': pref.auto_reply_enabled,
                'auto_reply_text': pref.auto_reply_text,
                'notify_new_message': pref.notify_new_message,
            }
        })
    except Exception as e:
        logger.error(f"获取私信设置错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
@login_required
def update_message_preference_api(request):
    """更新用户的私信偏好设置"""
    try:
        from ..models import MessagePreference

        data = json.loads(request.body)
        pref, _ = MessagePreference.objects.get_or_create(user=request.user)

        # 更新允许的字段
        if 'allow_messages' in data:
            pref.allow_messages = data['allow_messages']
        if 'message_mode' in data:
            if data['message_mode'] in ['all', 'followers_only', 'disabled']:
                pref.message_mode = data['message_mode']
        if 'show_read_status' in data:
            pref.show_read_status = data['show_read_status']
        if 'auto_reply_enabled' in data:
            pref.auto_reply_enabled = data['auto_reply_enabled']
        if 'auto_reply_text' in data:
            pref.auto_reply_text = data['auto_reply_text'][:500]  # 限制长度
        if 'notify_new_message' in data:
            pref.notify_new_message = data['notify_new_message']

        pref.save()

        return JsonResponse({
            'status': 'success',
            'message': '设置已更新'
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except MessagePreference.DoesNotExist:
        return JsonResponse({'error': '私信设置未找到'}, status=404)
    except Exception as e:
        logger.error(f"更新私信设置错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
@login_required
def block_user_api(request):
    """屏蔽用户"""
    try:
        from ..models import UserBlocklist

        data = json.loads(request.body)
        blocked_user_id = data.get('user_id')
        reason = data.get('reason', '')

        if not blocked_user_id:
            return JsonResponse({'error': '缺少user_id参数'}, status=400)

        blocked_user = get_object_or_404(User, id=blocked_user_id)

        if blocked_user == request.user:
            return JsonResponse({'error': '无法屏蔽自己'}, status=400)

        # 创建或更新屏蔽记录
        blocklist, created = UserBlocklist.objects.get_or_create(
            user=request.user,
            blocked_user=blocked_user,
            defaults={'reason': reason}
        )

        if not created:
            blocklist.reason = reason
            blocklist.save()

        return JsonResponse({
            'status': 'success',
            'message': '已屏蔽用户'
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        logger.error(f"屏蔽用户错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
@login_required
def unblock_user_api(request):
    """取消屏蔽用户"""
    try:
        from ..models import UserBlocklist

        data = json.loads(request.body)
        blocked_user_id = data.get('user_id')

        if not blocked_user_id:
            return JsonResponse({'error': '缺少user_id参数'}, status=400)

        UserBlocklist.objects.filter(
            user=request.user,
            blocked_user_id=blocked_user_id
        ).delete()

        return JsonResponse({
            'status': 'success',
            'message': '已取消屏蔽'
        })
    except Exception as e:
        logger.error(f"取消屏蔽错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def get_blocked_users_api(request):
    """获取当前用户的屏蔽列表"""
    try:
        from ..models import UserBlocklist

        blocked = UserBlocklist.objects.filter(user=request.user).select_related('blocked_user')
        blocked_list = []
        for item in blocked:
            avatar_url = '/static/img/default-avatar.png'
            try:
                if item.blocked_user.profile.avatar:
                    avatar_url = item.blocked_user.profile.avatar.url
            except:
                pass
            blocked_list.append({
                'id': item.blocked_user.id,
                'username': item.blocked_user.username,
                'avatar_url': avatar_url,
                'blocked_at': item.created_at.strftime('%Y-%m-%d') if hasattr(item, 'created_at') and item.created_at else None,
            })

        return JsonResponse({
            'status': 'success',
            'blocked_users': blocked_list
        })
    except Exception as e:
        logger.error(f"获取屏蔽列表错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_user_public_profile_api(request, user_id):
    """获取用户的公开信息"""
    try:
        user = get_object_or_404(User, id=user_id)
        profile = user.profile

        def get_avatar(user):
            try:
                if user.profile.avatar:
                    return user.profile.avatar.url
            except:
                pass
            return '/static/img/default-avatar.png'

        # 获取用户统计信息
        notes_count = Note.objects.filter(author=user, is_public=True).count()
        views_count = Note.objects.filter(author=user, is_public=True).aggregate(
            total_views=models.Sum('views')
        )['total_views'] or 0
        likes_count = ProfileLike.objects.filter(profile=profile).count()

        return JsonResponse({
            'status': 'success',
            'id': user.id,
            'username': user.username,
            'avatar': get_avatar(user),
            'bio': profile.bio or '',
            'notes_count': notes_count,
            'views_count': views_count,
            'likes_count': likes_count,
        })
    except Exception as e:
        logger.error(f"获取用户信息错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def search_users_api(request):
    """搜索用户"""
    try:
        query = request.GET.get('q', '').strip()

        if not query or len(query) < 2:
            return JsonResponse({'users': []})

        # 搜索用户名
        users = User.objects.filter(
            username__icontains=query
        ).exclude(
            id=request.user.id if request.user.is_authenticated else None
        )[:10]

        def get_avatar(user):
            try:
                if user.profile.avatar:
                    return user.profile.avatar.url
            except:
                pass
            return '/static/img/default-avatar.png'

        data = [
            {
                'id': u.id,
                'username': u.username,
                'avatar': get_avatar(u),
                'bio': u.profile.bio or '',
            }
            for u in users
        ]

        return JsonResponse({'users': data})
    except Exception as e:
        logger.error(f"搜索用户错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def messages_view(request):
    """私信页面"""
    return render(request, 'messages/messages.html')
