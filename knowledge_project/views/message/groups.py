# knowledge_project/views/message/groups.py
"""私信群组：创建资格 / 创建群组 / 群消息读取发送撤回举报。"""
import json
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ...moderation_utils import message_report_snapshot, notify_user
from ._constants import MESSAGE_CONTENT_MAX_LENGTH, RECALL_WINDOW_SECONDS
from ._helpers import (
    _body_string,
    _get_avatar_url,
    _message_searchable_text,
    _server_error_response,
)

logger = logging.getLogger(__name__)


def _policy_payload(policy, user):
    eligible, stats = policy.can_create_group(user)
    return {
        'enabled': policy.enabled,
        'min_public_notes': policy.min_public_notes,
        'min_followers': policy.min_followers,
        'stats': stats,
        'eligible': eligible,
        'reasons': {
            'public_notes': stats['public_notes'] >= policy.min_public_notes,
            'followers': stats['followers'] >= policy.min_followers,
        },
    }


def _group_avatar_url(group):
    return '/static/img/default-avatar.png'


def _get_active_membership(group, user):
    from ...models import MessageGroupMember
    return MessageGroupMember.objects.filter(group=group, user=user, left_at__isnull=True).first()


def _require_group_member(group, user):
    membership = _get_active_membership(group, user)
    if membership is None:
        return None, JsonResponse({'error': '你不是该群组成员'}, status=403)
    return membership, None


def _is_group_manager(membership):
    return membership is not None and membership.role in ('owner', 'admin')


def _require_group_manager(membership):
    if not _is_group_manager(membership):
        return JsonResponse({'error': '只有群主或管理员可以执行该操作'}, status=403)
    return None


def _group_settings_payload(membership):
    return {
        'is_pinned': membership.is_pinned,
        'pinned_at': membership.pinned_at.isoformat() if membership.pinned_at else None,
        'is_muted': membership.is_muted,
        'is_archived': membership.is_archived,
        'disappearing_enabled': False,
        'disappearing_ttl_seconds': 0,
        'force_unread': membership.force_unread,
        'cleared_before': membership.cleared_before.isoformat() if membership.cleared_before else None,
        'group_role': membership.role,
    }


def _group_message_payload(message, viewer=None):
    return {
        'id': message.id,
        'conversation_type': 'group',
        'group_id': message.group_id,
        'sender': message.sender.username,
        'sender_id': message.sender_id,
        'sender_avatar': _get_avatar_url(message.sender),
        'recipient': message.group.name,
        'recipient_id': None,
        'content': message.content,
        'content_preview': '',
        'merged_forward': None,
        'created_at': message.created_at.isoformat(),
        'is_edited': message.is_edited,
        'edited_at': message.edited_at.isoformat() if message.edited_at else None,
        'is_read': True,
        'read_at': None,
        'is_own': (viewer is not None and viewer.id == message.sender_id),
        'attachments': [],
    }


def _member_payload(membership):
    user = membership.user
    return {
        'user_id': user.id,
        'username': user.username,
        'avatar': _get_avatar_url(user),
        'role': membership.role,
        'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
        'is_self': False,
    }


def _group_detail_payload(group, viewer_membership=None):
    memberships = list(
        group.memberships
        .filter(left_at__isnull=True)
        .select_related('user')
        .order_by('role', 'joined_at')
    )
    members = [_member_payload(membership) for membership in memberships]
    if viewer_membership:
        for member in members:
            member['is_self'] = member['user_id'] == viewer_membership.user_id
    return {
        'id': group.id,
        'name': group.name,
        'avatar': _group_avatar_url(group),
        'owner_id': group.owner_id,
        'member_count': len(members),
        'created_at': group.created_at.isoformat() if group.created_at else None,
        'updated_at': group.updated_at.isoformat() if group.updated_at else None,
        'viewer_role': viewer_membership.role if viewer_membership else None,
        'members': members,
    }


def _visible_group_messages_qs(group, membership):
    from ...models import GroupMessage
    qs = GroupMessage.objects.filter(group=group, is_recalled=False).select_related('sender')
    if membership.cleared_before:
        qs = qs.filter(created_at__gt=membership.cleared_before)
    qs = qs.exclude(deletions__user=membership.user)
    return qs.order_by('created_at')


@require_http_methods(["GET"])
@login_required
def get_group_policy_api(request):
    from ...models import MessageGroupPolicy
    policy = MessageGroupPolicy.get_current()
    return JsonResponse({'status': 'success', 'policy': _policy_payload(policy, request.user)})


@require_http_methods(["POST"])
@login_required
def create_message_group_api(request):
    try:
        from ...models import MessageGroup, MessageGroupMember, MessageGroupPolicy

        data = json.loads(request.body)
        name = _body_string(data, 'name')[:80]
        raw_member_ids = data.get('member_ids') or []
        if not name:
            return JsonResponse({'error': '请输入群组名称'}, status=400)
        if not isinstance(raw_member_ids, list):
            return JsonResponse({'error': 'member_ids 必须是数组'}, status=400)

        policy = MessageGroupPolicy.get_current()
        eligible, stats = policy.can_create_group(request.user)
        if not eligible:
            return JsonResponse({
                'error': '你暂未满足创建群组条件',
                'policy': _policy_payload(policy, request.user),
            }, status=403)

        member_ids = []
        for value in raw_member_ids[:100]:
            try:
                member_id = int(value)
            except (TypeError, ValueError):
                continue
            if member_id > 0 and member_id != request.user.id and member_id not in member_ids:
                member_ids.append(member_id)
        if not member_ids:
            return JsonResponse({'error': '请至少选择一名群成员'}, status=400)

        users = list(User.objects.filter(id__in=member_ids, is_active=True))
        if len(users) != len(member_ids):
            return JsonResponse({'error': '部分群成员不存在或不可用'}, status=400)

        with transaction.atomic():
            group = MessageGroup.objects.create(
                name=name,
                owner=request.user,
                created_by=request.user,
            )
            MessageGroupMember.objects.create(group=group, user=request.user, role='owner')
            MessageGroupMember.objects.bulk_create([
                MessageGroupMember(group=group, user=user, role='member')
                for user in users
            ])

        return JsonResponse({
            'status': 'success',
            'group': {
                'id': group.id,
                'name': group.name,
                'member_count': len(users) + 1,
                'policy_stats': stats,
            },
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        return _server_error_response('创建群组错误', e)


@require_http_methods(["GET", "POST"])
@login_required
def message_group_detail_api(request, group_id):
    try:
        from ...models import MessageGroup
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        if request.method == "GET":
            return JsonResponse({
                'status': 'success',
                'group': _group_detail_payload(group, membership),
                'settings': _group_settings_payload(membership),
            })

        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        data = json.loads(request.body)
        name = _body_string(data, 'name')[:80]
        if not name:
            return JsonResponse({'error': '请输入群组名称'}, status=400)
        group.name = name
        group.updated_at = timezone.now()
        group.save(update_fields=['name', 'updated_at'])
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群组错误', e)


@require_http_methods(["POST"])
@login_required
def add_group_members_api(request, group_id):
    try:
        from ...models import MessageGroup, MessageGroupMember
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        data = json.loads(request.body)
        raw_member_ids = data.get('member_ids') or []
        if not isinstance(raw_member_ids, list):
            return JsonResponse({'error': 'member_ids 必须是数组'}, status=400)

        member_ids = []
        for value in raw_member_ids[:100]:
            try:
                member_id = int(value)
            except (TypeError, ValueError):
                continue
            if member_id > 0 and member_id != request.user.id and member_id not in member_ids:
                member_ids.append(member_id)
        if not member_ids:
            return JsonResponse({'error': '请选择要加入的成员'}, status=400)

        users = list(User.objects.filter(id__in=member_ids, is_active=True))
        if len(users) != len(member_ids):
            return JsonResponse({'error': '部分用户不存在或不可用'}, status=400)

        with transaction.atomic():
            for user in users:
                member, created = MessageGroupMember.objects.get_or_create(
                    group=group,
                    user=user,
                    defaults={'role': 'member'},
                )
                if not created and member.left_at is not None:
                    member.left_at = None
                    member.role = 'member'
                    member.joined_at = timezone.now()
                    member.save(update_fields=['left_at', 'role', 'joined_at'])
            group.updated_at = timezone.now()
            group.save(update_fields=['updated_at'])

        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('添加群成员错误', e)


@require_http_methods(["POST", "DELETE"])
@login_required
def remove_group_member_api(request, group_id, user_id):
    try:
        from ...models import MessageGroup, MessageGroupMember
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        target = get_object_or_404(MessageGroupMember, group=group, user_id=user_id, left_at__isnull=True)
        if target.role == 'owner':
            return JsonResponse({'error': '不能移除群主'}, status=400)
        if membership.role == 'admin' and target.role == 'admin':
            return JsonResponse({'error': '管理员不能移除其他管理员'}, status=403)

        target.left_at = timezone.now()
        target.save(update_fields=['left_at'])
        group.updated_at = timezone.now()
        group.save(update_fields=['updated_at'])
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('移除群成员错误', e)


@require_http_methods(["POST"])
@login_required
def leave_message_group_api(request, group_id):
    try:
        from ...models import MessageGroup
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        if membership.role == 'owner':
            return JsonResponse({'error': '群主不能直接退出，请先解散群组'}, status=400)

        membership.left_at = timezone.now()
        membership.save(update_fields=['left_at'])
        group.updated_at = timezone.now()
        group.save(update_fields=['updated_at'])
        return JsonResponse({'status': 'success'})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('退出群组错误', e)


@require_http_methods(["POST"])
@login_required
def dissolve_message_group_api(request, group_id):
    try:
        from ...models import MessageGroup
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        if membership.role != 'owner':
            return JsonResponse({'error': '只有群主可以解散群组'}, status=403)

        group.is_active = False
        group.updated_at = timezone.now()
        group.save(update_fields=['is_active', 'updated_at'])
        group.memberships.filter(left_at__isnull=True).update(left_at=timezone.now())
        return JsonResponse({'status': 'success'})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('解散群组错误', e)


@require_http_methods(["POST"])
@login_required
def toggle_group_setting_api(request, group_id, action):
    try:
        from ...models import MessageGroup
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        data = json.loads(request.body) if request.body else {}
        now = timezone.now()
        if action == 'pin':
            value = bool(data.get('value'))
            membership.is_pinned = value
            membership.pinned_at = now if value else None
            membership.save(update_fields=['is_pinned', 'pinned_at'])
        elif action == 'mute':
            membership.is_muted = bool(data.get('value'))
            membership.save(update_fields=['is_muted'])
        elif action == 'archive':
            value = bool(data.get('value'))
            membership.is_archived = value
            membership.archived_at = now if value else None
            membership.save(update_fields=['is_archived', 'archived_at'])
        elif action == 'mark-read':
            membership.last_read_at = now
            membership.force_unread = False
            membership.save(update_fields=['last_read_at', 'force_unread'])
        elif action == 'mark-unread':
            membership.force_unread = True
            membership.save(update_fields=['force_unread'])
        elif action == 'clear':
            membership.cleared_before = now
            membership.force_unread = False
            membership.save(update_fields=['cleared_before', 'force_unread'])
        else:
            return JsonResponse({'error': '不支持的群组设置操作'}, status=400)

        return JsonResponse({'status': 'success', 'settings': _group_settings_payload(membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群组设置错误', e)


@require_http_methods(["GET"])
@login_required
def get_group_messages_api(request, group_id):
    try:
        from ...models import MessageGroup
        query = request.GET.get('q', '').strip()
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        qs = _visible_group_messages_qs(group, membership)
        if query:
            qs = qs.filter(Q(content__icontains=query) | Q(searchable_text__icontains=query))
        messages = list(qs)

        membership.last_read_at = timezone.now()
        membership.force_unread = False
        membership.save(update_fields=['last_read_at', 'force_unread'])

        return JsonResponse({
            'status': 'success',
            'conversation_type': 'group',
            'group': {
                'id': group.id,
                'name': group.name,
                'avatar': _group_avatar_url(group),
            },
            'messages': [_group_message_payload(message, viewer=request.user) for message in messages],
            'settings': _group_settings_payload(membership),
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取群组消息错误', e)


@require_http_methods(["POST"])
@login_required
def send_group_message_api(request, group_id):
    try:
        from ...models import GroupMessage, MessageGroup, UserSanction
        data = json.loads(request.body)
        content = _body_string(data, 'content')
        if not content:
            return JsonResponse({'error': '消息内容不能为空'}, status=400)
        if len(content) > MESSAGE_CONTENT_MAX_LENGTH:
            return JsonResponse({'error': f'消息内容不能超过{MESSAGE_CONTENT_MAX_LENGTH}字'}, status=400)
        if data.get('attachment_ids'):
            return JsonResponse({'error': '群组暂不支持阅后即焚或附件消息'}, status=400)

        mute = UserSanction.is_muted(request.user)
        if mute is not None:
            return JsonResponse({'error': '你已被禁止发送私信'}, status=403)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        with transaction.atomic():
            message = GroupMessage.objects.create(
                group=group,
                sender=request.user,
                content=content,
                searchable_text=_message_searchable_text(content),
            )
            group.updated_at = timezone.now()
            group.save(update_fields=['updated_at'])
            membership.force_unread = False
            membership.last_read_at = timezone.now()
            membership.save(update_fields=['force_unread', 'last_read_at'])

        return JsonResponse({
            'status': 'success',
            'message': _group_message_payload(message, viewer=request.user),
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('发送群组消息错误', e)


@require_http_methods(["POST"])
@login_required
def edit_group_message_api(request, group_id, message_id):
    try:
        from ...models import GroupMessage, MessageGroup
        data = json.loads(request.body)
        content = _body_string(data, 'content')
        if not content:
            return JsonResponse({'error': '消息内容不能为空'}, status=400)
        if len(content) > MESSAGE_CONTENT_MAX_LENGTH:
            return JsonResponse({'error': f'消息内容不能超过{MESSAGE_CONTENT_MAX_LENGTH}字'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        message = get_object_or_404(GroupMessage, id=message_id, group=group, is_recalled=False)
        if message.sender_id != request.user.id:
            return JsonResponse({'error': '只能编辑自己发送的消息'}, status=403)

        message.content = content
        message.searchable_text = _message_searchable_text(content)
        message.is_edited = True
        message.edited_at = timezone.now()
        message.save(update_fields=['content', 'searchable_text', 'is_edited', 'edited_at'])
        group.updated_at = timezone.now()
        group.save(update_fields=['updated_at'])
        return JsonResponse({
            'status': 'success',
            'message': _group_message_payload(message, viewer=request.user),
            'settings': _group_settings_payload(membership),
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('编辑群组消息错误', e)


@require_http_methods(["POST", "DELETE"])
@login_required
def delete_group_message_api(request, group_id, message_id):
    try:
        from ...models import GroupMessage, GroupMessageDeletion, MessageGroup
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        scope = data.get('scope', 'self')
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        message = get_object_or_404(GroupMessage, id=message_id, group=group)

        if scope == 'both':
            if message.sender_id != request.user.id:
                return JsonResponse({'error': '只有发送者可以撤回'}, status=403)
            if message.created_at < timezone.now() - timedelta(seconds=RECALL_WINDOW_SECONDS):
                return JsonResponse({'error': f'发送超过 {RECALL_WINDOW_SECONDS // 60} 分钟的消息不能撤回'}, status=403)
            message.is_recalled = True
            message.recalled_at = timezone.now()
            message.save(update_fields=['is_recalled', 'recalled_at'])
            return JsonResponse({'status': 'success', 'scope': 'both'})

        GroupMessageDeletion.objects.get_or_create(message=message, user=request.user)
        return JsonResponse({'status': 'success', 'scope': 'self'})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('删除群组消息错误', e)


@require_http_methods(["POST"])
@login_required
def report_group_message_api(request, group_id, message_id):
    try:
        from ...models import GroupMessage, MessageGroup, MessageReport
        data = json.loads(request.body)
        reason = data.get('reason', 'other')
        detail = (data.get('detail') or '').strip()[:1000]
        if reason not in dict(MessageReport.REASON_CHOICES):
            return JsonResponse({'error': '无效的举报原因'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        _, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        message = get_object_or_404(GroupMessage, id=message_id, group=group)
        if message.sender_id == request.user.id:
            return JsonResponse({'error': '不能举报自己发送的消息'}, status=400)

        report = MessageReport.objects.create(
            reporter=request.user,
            reported_user=message.sender,
            group_message=message,
            reason=reason,
            detail=detail,
            evidence_snapshot=message_report_snapshot(group_message=message, request=request),
        )
        notify_user(
            request.user,
            'report_received',
            '举报已收到',
            '你的群消息举报已提交，管理员会尽快处理。',
            report_type='message',
            report_id=report.id,
        )
        if not message.was_reported:
            message.was_reported = True
            message.save(update_fields=['was_reported'])
        return JsonResponse({'status': 'success', 'message': '举报已提交，我们会尽快处理'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('举报群组消息错误', e)
