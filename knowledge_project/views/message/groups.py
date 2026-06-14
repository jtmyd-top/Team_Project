# knowledge_project/views/message/groups.py
"""私信群组：创建资格 / 创建群组 / 群消息读取发送撤回举报。"""
import json
import logging
import re
from datetime import datetime, timedelta

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
    _attachment_payload,
    _body_string,
    _get_avatar_url,
    _load_message_attachments,
    _maybe_send_group_mention_email,
    _message_searchable_text,
    _normalize_attachment_ids,
    _server_error_response,
)

logger = logging.getLogger(__name__)

MAX_OWNED_MESSAGE_GROUPS = 3
MAX_MESSAGE_GROUP_MEMBERS = 200


def _active_owned_group_count(user, exclude_group_id=None):
    from ...models import MessageGroup
    qs = MessageGroup.objects.filter(owner=user, is_active=True)
    if exclude_group_id is not None:
        qs = qs.exclude(id=exclude_group_id)
    return qs.count()


def _owned_group_limit_payload(user, exclude_group_id=None):
    owned_count = _active_owned_group_count(user, exclude_group_id=exclude_group_id)
    return {
        'owned_group_count': owned_count,
        'max_owned_groups': MAX_OWNED_MESSAGE_GROUPS,
        'within_owned_group_limit': owned_count < MAX_OWNED_MESSAGE_GROUPS,
    }


def _active_group_member_count(group):
    return group.memberships.filter(left_at__isnull=True).count()


def _group_member_limit_payload(group, current_count=None):
    if current_count is None:
        current_count = _active_group_member_count(group)
    return {
        'member_count': current_count,
        'max_members': MAX_MESSAGE_GROUP_MEMBERS,
        'is_full': current_count >= MAX_MESSAGE_GROUP_MEMBERS,
    }


def _group_full_response(group, current_count=None):
    payload = _group_member_limit_payload(group, current_count=current_count)
    return JsonResponse({
        'error': f'群聊人数已达上限，最多 {MAX_MESSAGE_GROUP_MEMBERS} 人',
        **payload,
    }, status=409)


def _announcement_read_payload(group, announcement=None):
    from ...models import MessageGroupAnnouncementRead

    if announcement is None:
        announcement = group.announcement_history.order_by('-created_at').first()

    total_members = group.memberships.filter(left_at__isnull=True).count()
    if not announcement:
        return {
            'announcement_id': None,
            'read_count': 0,
            'unread_count': total_members,
            'total_members': total_members,
            'read_users': [],
        }

    read_qs = (
        MessageGroupAnnouncementRead.objects
        .filter(group=group, announcement=announcement)
        .select_related('user')
        .order_by('-read_at')
    )
    read_users = [
        {
            'id': item.user_id,
            'username': item.user.username,
            'avatar': _get_avatar_url(item.user),
            'read_at': item.read_at.isoformat() if item.read_at else None,
        }
        for item in read_qs[:50]
    ]
    read_count = read_qs.count()
    return {
        'announcement_id': announcement.id,
        'read_count': read_count,
        'unread_count': max(total_members - read_count, 0),
        'total_members': total_members,
        'read_users': read_users,
    }


def _policy_payload(policy, user, exclude_group_id=None):
    policy_eligible, stats = policy.can_create_group(user)
    owned_limit = _owned_group_limit_payload(user, exclude_group_id=exclude_group_id)
    eligible = policy_eligible and owned_limit['within_owned_group_limit']
    return {
        'enabled': policy.enabled,
        'min_public_notes': policy.min_public_notes,
        'min_followers': policy.min_followers,
        'stats': stats,
        'eligible': eligible,
        'policy_eligible': policy_eligible,
        'owned_group_count': owned_limit['owned_group_count'],
        'max_owned_groups': owned_limit['max_owned_groups'],
        'can_manage': user.is_staff or user.is_superuser,
        'reasons': {
            'public_notes': stats['public_notes'] >= policy.min_public_notes,
            'followers': stats['followers'] >= policy.min_followers,
            'owned_groups': owned_limit['within_owned_group_limit'],
        },
    }


def _group_avatar_url(group):
    if getattr(group, 'avatar', None):
        try:
            return group.avatar.url
        except Exception:
            logger.debug('无法获取群头像 URL', exc_info=True)
    return '/static/img/default-avatar.png'


def _user_payload(user):
    if user is None:
        return None
    return {
        'id': user.id,
        'username': user.username,
        'avatar': _get_avatar_url(user),
    }


def _get_active_group_ban(group, user):
    from ...models import MessageGroupBan
    now = timezone.now()
    return (
        MessageGroupBan.objects
        .filter(group=group, user=user, revoked_at__isnull=True)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .select_related('banned_by')
        .first()
    )


def _active_group_ban_payload(ban):
    if ban is None:
        return None
    return {
        'id': ban.id,
        'user': _user_payload(ban.user),
        'reason': ban.reason,
        'expires_at': ban.expires_at.isoformat() if ban.expires_at else None,
        'created_at': ban.created_at.isoformat() if ban.created_at else None,
        'banned_by': _user_payload(ban.banned_by),
    }


def _create_group_audit_log(group, actor, action, target_user=None, metadata=None):
    try:
        from ...models import MessageGroupAuditLog
        MessageGroupAuditLog.objects.create(
            group=group,
            actor=actor if getattr(actor, 'is_authenticated', False) else None,
            target_user=target_user,
            action=action,
            metadata=metadata or {},
        )
    except Exception:
        logger.warning('写入群组审计日志失败: group=%s action=%s', getattr(group, 'id', None), action, exc_info=True)


def _parse_expires_at(value):
    if value in (None, '', False):
        return None
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed
    return None


def _can_send_group_message(group, membership):
    if _is_member_muted(membership):
        return JsonResponse({
            'error': '你已被群内禁言',
            'muted_until': membership.muted_until.isoformat() if membership.muted_until else None,
        }, status=403)
    if _get_active_group_ban(group, membership.user):
        return JsonResponse({'error': '你已被该群组封禁，无法发言'}, status=403)
    if getattr(group, 'mute_mode', 'none') == 'admins_only' and membership.role not in ('owner', 'admin'):
        return JsonResponse({'error': '当前群已开启全员禁言，仅群主或管理员可以发言'}, status=403)
    return None


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


def _require_group_owner(membership):
    if membership is None or membership.role != 'owner':
        return JsonResponse({'error': '只有群主可以执行该操作'}, status=403)
    return None


def _can_manage_target(actor_membership, target_membership):
    if actor_membership is None or target_membership is None:
        return False
    if target_membership.role == 'owner':
        return False
    if actor_membership.role == 'owner':
        return actor_membership.user_id != target_membership.user_id
    if actor_membership.role == 'admin':
        return target_membership.role == 'member'
    return False


def _parse_mute_until(data):
    value = data.get('duration') if isinstance(data, dict) else None
    if value in ('none', 'off', 'unmute', False):
        return None
    if value in ('forever', 'permanent', 0, '0'):
        return timezone.now() + timedelta(days=3650)

    minutes = data.get('duration_minutes') if isinstance(data, dict) else None
    if minutes is None:
        minutes = value
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        minutes = 60
    minutes = max(1, min(minutes, 60 * 24 * 30))
    return timezone.now() + timedelta(minutes=minutes)


def _is_member_muted(membership):
    if not membership or not membership.muted_until:
        return False
    now = timezone.now()
    if membership.muted_until <= now:
        membership.muted_until = None
        membership.save(update_fields=['muted_until'])
        return False
    return True


def _invite_link_payload(link, request=None):
    path = f"/messages/?group_invite={link.token}"
    use_records = getattr(link, 'prefetched_use_records', None)
    if use_records is None:
        use_records = list(
            link.use_records.select_related('user').order_by('-created_at')[:10]
        ) if getattr(link, 'id', None) else []
    return {
        'id': link.id,
        'token': link.token,
        'url': request.build_absolute_uri(path) if request else path,
        'created_by': link.created_by.username if link.created_by else None,
        'created_at': link.created_at.isoformat() if link.created_at else None,
        'expires_at': link.expires_at.isoformat() if link.expires_at else None,
        'max_uses': link.max_uses,
        'uses_count': link.uses_count,
        'revoked_at': link.revoked_at.isoformat() if link.revoked_at else None,
        'is_active': link.is_valid(),
        'recent_uses': [_invite_use_payload(record) for record in use_records],
    }


def _invite_use_payload(record):
    return {
        'id': record.id,
        'user': _user_payload(record.user),
        'created_at': record.created_at.isoformat() if record.created_at else None,
    }


def _announcement_history_payload(item):
    return {
        'id': item.id,
        'editor': _user_payload(item.editor),
        'content': item.content,
        'pinned': item.pinned,
        'created_at': item.created_at.isoformat() if item.created_at else None,
    }


def _pinned_group_message_payload(group, viewer=None):
    message = getattr(group, 'pinned_message', None)
    if not message or getattr(message, 'is_recalled', False):
        return None
    return _group_message_payload(message, viewer=viewer)


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
    # Phase 2: 获取回复消息信息
    reply_to_data = None
    if message.reply_to:
        reply_to_data = {
            'id': message.reply_to.id,
            'sender': message.reply_to.sender.username,
            'sender_id': message.reply_to.sender_id,
            'content': message.reply_to.content[:100],  # 只显示前100字符
            'created_at': message.reply_to.created_at.isoformat(),
        }

    # Phase 2: 获取转发消息信息
    forwarded_from_data = None
    if message.forwarded_from:
        forwarded_from_data = {
            'id': message.forwarded_from.id,
            'sender': message.forwarded_from.sender.username,
            'sender_id': message.forwarded_from.sender_id,
            'content': message.forwarded_from.content,
            'created_at': message.forwarded_from.created_at.isoformat(),
            'group_name': message.forwarded_from.group.name if message.forwarded_from.group else None,
        }

    # Phase 2: 获取@提及的用户列表
    mentions = []
    if hasattr(message, 'mentions'):
        mentions = [
            {
                'user_id': mention.mentioned_user_id,
                'username': mention.mentioned_user.username,
            }
            for mention in message.mentions.select_related('mentioned_user').all()
        ]

    # Phase 2: 获取表情回应统计
    reactions = {}
    if hasattr(message, 'reactions'):
        from django.db.models import Count
        reaction_stats = message.reactions.values('emoji').annotate(count=Count('id'))
        for stat in reaction_stats:
            emoji = stat['emoji']
            count = stat['count']
            # 获取使用该表情的用户列表（最多显示3个）
            users = list(message.reactions.filter(emoji=emoji).select_related('user')[:3])
            reactions[emoji] = {
                'count': count,
                'users': [{'user_id': r.user_id, 'username': r.user.username} for r in users],
                'reacted_by_me': viewer and any(r.user_id == viewer.id for r in users) if viewer else False,
            }

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
        'attachments': [_attachment_payload(a) for a in message.attachments.all()],
        # Phase 2: 新增字段
        'reply_to': reply_to_data,
        'forwarded_from': forwarded_from_data,
        'mentions': mentions,
        'reactions': reactions,
        'is_pinned': bool(
            getattr(message.group, 'pinned_message_id', None) == message.id
        ) if getattr(message, 'group_id', None) else False,
    }


def _member_payload(membership):
    user = membership.user
    muted = _is_member_muted(membership)
    return {
        'user_id': user.id,
        'username': user.username,
        'avatar': _get_avatar_url(user),
        'role': membership.role,
        'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
        'muted_until': membership.muted_until.isoformat() if membership.muted_until else None,
        'is_group_muted': muted,
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
        'description': group.description,
        'announcement': group.announcement,
        'announcement_pinned_at': group.announcement_pinned_at.isoformat() if group.announcement_pinned_at else None,
        'announcement_updated_by': _user_payload(group.announcement_updated_by),
        'announcement_history': [
            _announcement_history_payload(item)
            for item in group.announcement_history.select_related('editor').order_by('-created_at')[:8]
        ],
        'mute_mode': group.mute_mode,
        'require_approval': group.require_approval,
        'allow_member_mention_all': group.allow_member_mention_all,
        'pinned_message': _pinned_group_message_payload(group, viewer_membership.user if viewer_membership else None),
        'owner_id': group.owner_id,
        'member_count': len(members),
        'max_members': MAX_MESSAGE_GROUP_MEMBERS,
        'is_full': len(members) >= MAX_MESSAGE_GROUP_MEMBERS,
        'pending_join_request_count': group.join_requests.filter(status='pending').count() if viewer_membership and _is_group_manager(viewer_membership) else 0,
        'created_at': group.created_at.isoformat() if group.created_at else None,
        'updated_at': group.updated_at.isoformat() if group.updated_at else None,
        'viewer_role': viewer_membership.role if viewer_membership else None,
        'members': members,
    }


def _visible_group_messages_qs(group, membership):
    from ...models import GroupMessage
    qs = GroupMessage.objects.filter(group=group, is_recalled=False).select_related('sender', 'group').prefetch_related('attachments')
    if membership.cleared_before:
        qs = qs.filter(created_at__gt=membership.cleared_before)
    qs = qs.exclude(deletions__user=membership.user)
    return qs.order_by('created_at')


def _extract_links_from_text(text):
    pattern = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
    links = []
    for match in pattern.finditer(text or ''):
        url = match.group(0).rstrip('.,;!?)]}')
        if url and url not in links:
            links.append(url)
    return links


@require_http_methods(["GET", "POST"])
@login_required
def get_group_policy_api(request):
    from ...models import MessageGroupPolicy
    policy = MessageGroupPolicy.get_current()

    if request.method == 'POST':
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({'error': '只有管理员可以调整群组创建条件'}, status=403)
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'error': '请求格式错误'}, status=400)

        try:
            min_public_notes = int(data.get('min_public_notes', policy.min_public_notes))
            min_followers = int(data.get('min_followers', policy.min_followers))
        except (TypeError, ValueError):
            return JsonResponse({'error': '门槛值必须是数字'}, status=400)

        if min_public_notes < 0 or min_followers < 0:
            return JsonResponse({'error': '门槛值不能小于 0'}, status=400)

        policy.enabled = bool(data.get('enabled', policy.enabled))
        policy.min_public_notes = min_public_notes
        policy.min_followers = min_followers
        policy.save(update_fields=['enabled', 'min_public_notes', 'min_followers', 'updated_at'])

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
        policy_payload = _policy_payload(policy, request.user)
        if not policy_payload['eligible']:
            return JsonResponse({
                'error': '你暂未满足创建群组条件',
                'policy': policy_payload,
            }, status=403)

        member_ids = []
        for value in raw_member_ids:
            try:
                member_id = int(value)
            except (TypeError, ValueError):
                continue
            if member_id > 0 and member_id != request.user.id and member_id not in member_ids:
                member_ids.append(member_id)
        if not member_ids:
            return JsonResponse({'error': '请至少选择一名群成员'}, status=400)
        if len(member_ids) + 1 > MAX_MESSAGE_GROUP_MEMBERS:
            return JsonResponse({
                'error': f'群聊人数已达上限，最多 {MAX_MESSAGE_GROUP_MEMBERS} 人',
                'member_count': len(member_ids) + 1,
                'max_members': MAX_MESSAGE_GROUP_MEMBERS,
            }, status=400)

        users = list(User.objects.filter(id__in=member_ids, is_active=True))
        if len(users) != len(member_ids):
            return JsonResponse({'error': '部分群成员不存在或不可用'}, status=400)

        with transaction.atomic():
            User.objects.select_for_update().get(id=request.user.id)
            owned_limit = _owned_group_limit_payload(request.user)
            if not owned_limit['within_owned_group_limit']:
                return JsonResponse({
                    'error': f'你已创建 {MAX_OWNED_MESSAGE_GROUPS} 个群聊，暂不能继续创建',
                    'policy': _policy_payload(policy, request.user),
                    **owned_limit,
                }, status=403)

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
            _create_group_audit_log(group, request.user, 'group_create', metadata={'member_count': len(users) + 1})

        return JsonResponse({
            'status': 'success',
            'group': {
                'id': group.id,
                'name': group.name,
                'member_count': len(users) + 1,
                'max_members': MAX_MESSAGE_GROUP_MEMBERS,
                'policy_stats': policy_payload['stats'],
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
        _create_group_audit_log(group, request.user, 'group_rename', metadata={'name': name})
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群组错误', e)


@require_http_methods(["POST", "PATCH"])
@login_required
def update_group_profile_api(request, group_id):
    try:
        from ...models import MessageGroup
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        if request.content_type and request.content_type.startswith('multipart/form-data'):
            data = request.POST
            avatar = request.FILES.get('avatar')
        else:
            data = json.loads(request.body or '{}')
            avatar = None

        changed_fields = []
        metadata = {}
        if 'name' in data:
            name = _body_string(data, 'name')[:80]
            if not name:
                return JsonResponse({'error': '请输入群组名称'}, status=400)
            if group.name != name:
                metadata['old_name'] = group.name
                metadata['name'] = name
                group.name = name
                changed_fields.append('name')
        if 'description' in data:
            group.description = _body_string(data, 'description')[:1000]
            changed_fields.append('description')
        if 'announcement' in data:
            group.announcement = _body_string(data, 'announcement')[:2000]
            changed_fields.append('announcement')
        if 'require_approval' in data:
            group.require_approval = bool(data.get('require_approval'))
            changed_fields.append('require_approval')
            metadata['require_approval'] = group.require_approval
        if 'allow_member_mention_all' in data:
            group.allow_member_mention_all = bool(data.get('allow_member_mention_all'))
            changed_fields.append('allow_member_mention_all')
            metadata['allow_member_mention_all'] = group.allow_member_mention_all
        if avatar is not None:
            group.avatar = avatar
            changed_fields.append('avatar')

        if changed_fields:
            changed_fields.append('updated_at')
            group.updated_at = timezone.now()
            group.save(update_fields=list(dict.fromkeys(changed_fields)))
            action = 'group_announcement_update' if changed_fields == ['announcement', 'updated_at'] else 'group_update_profile'
            _create_group_audit_log(group, request.user, action, metadata=metadata or {'fields': changed_fields})

        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群资料错误', e)


@require_http_methods(["POST"])
@login_required
def transfer_group_ownership_api(request, group_id):
    try:
        from ...models import MessageGroup, MessageGroupMember, MessageGroupPolicy
        data = json.loads(request.body or '{}')
        # 支持 user_id 和 new_owner_id 两种参数名
        target_user_id = int(data.get('new_owner_id') or data.get('user_id'))
        password = data.get('password', '')

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        owner_error = _require_group_owner(membership)
        if owner_error is not None:
            return owner_error

        # 验证密码（可选，增强安全性）
        if password and not request.user.check_password(password):
            return JsonResponse({'error': '密码验证失败'}, status=403)

        with transaction.atomic():
            current_owner = MessageGroupMember.objects.select_for_update().get(
                group=group, user=request.user, left_at__isnull=True
            )
            target = get_object_or_404(
                MessageGroupMember.objects.select_for_update().select_related('user'),
                group=group,
                user_id=target_user_id,
                left_at__isnull=True,
            )
            if target.user_id == request.user.id:
                return JsonResponse({'error': '不能转让给自己'}, status=400)
            User.objects.select_for_update().get(id=target.user_id)

            # 【新增】验证新群主是否满足开群条件
            policy = MessageGroupPolicy.get_current()
            eligible, stats = policy.can_create_group(target.user)

            if not eligible:
                return JsonResponse({
                    'error': '新群主不满足创建群组条件',
                    'policy': _policy_payload(policy, target.user),
                    'stats': stats,
                    'message': f'新群主需满足以下任一条件：公开文章数 ≥ {policy.min_public_notes} 或 关注者数 ≥ {policy.min_followers}。'
                               f'当前状态：公开文章 {stats["public_notes"]} 篇，关注者 {stats["followers"]} 人。',
                }, status=403)
            owned_limit = _owned_group_limit_payload(target.user, exclude_group_id=group.id)
            if not owned_limit['within_owned_group_limit']:
                return JsonResponse({
                    'error': f'新群主已拥有 {MAX_OWNED_MESSAGE_GROUPS} 个群聊，无法继续接收转让',
                    **owned_limit,
                }, status=403)

            current_owner.role = 'admin'
            target.role = 'owner'
            current_owner.save(update_fields=['role'])
            target.save(update_fields=['role'])
            group.owner = target.user
            group.updated_at = timezone.now()
            group.save(update_fields=['owner', 'updated_at'])
            _create_group_audit_log(
                group,
                request.user,
                'ownership_transfer',
                target_user=target.user,
                metadata={'old_owner_id': request.user.id, 'new_owner_id': target.user_id},
            )
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, target)})
    except (TypeError, ValueError):
        return JsonResponse({'error': '请选择新的群主'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('转让群主错误', e)


@require_http_methods(["POST"])
@login_required
def set_group_mute_mode_api(request, group_id):
    try:
        from ...models import MessageGroup
        data = json.loads(request.body or '{}')
        mute_mode = data.get('mute_mode')
        if mute_mode not in ('none', 'admins_only'):
            return JsonResponse({'error': '不支持的发言模式'}, status=400)
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error
        old_mode = group.mute_mode
        group.mute_mode = mute_mode
        group.updated_at = timezone.now()
        group.save(update_fields=['mute_mode', 'updated_at'])
        _create_group_audit_log(
            group,
            request.user,
            'group_mute_change',
            metadata={'old_mode': old_mode, 'mute_mode': mute_mode},
        )
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('设置群发言模式错误', e)


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
        for value in raw_member_ids:
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
        banned_users = [user.username for user in users if _get_active_group_ban(group, user)]
        if banned_users:
            return JsonResponse({'error': f"以下用户已被本群封禁，无法加入：{', '.join(banned_users)}"}, status=403)

        with transaction.atomic():
            locked_group = MessageGroup.objects.select_for_update().get(id=group.id)
            active_member_ids = set(
                MessageGroupMember.objects
                .select_for_update()
                .filter(group=locked_group, left_at__isnull=True)
                .values_list('user_id', flat=True)
            )
            joining_count = sum(1 for user in users if user.id not in active_member_ids)
            if len(active_member_ids) + joining_count > MAX_MESSAGE_GROUP_MEMBERS:
                return _group_full_response(locked_group, current_count=len(active_member_ids))

            for user in users:
                member, created = MessageGroupMember.objects.get_or_create(
                    group=locked_group,
                    user=user,
                    defaults={'role': 'member'},
                )
                if not created and member.left_at is not None:
                    member.left_at = None
                    member.role = 'member'
                    member.joined_at = timezone.now()
                    member.save(update_fields=['left_at', 'role', 'joined_at'])
                _create_group_audit_log(locked_group, request.user, 'member_add', target_user=user)
            locked_group.updated_at = timezone.now()
            locked_group.save(update_fields=['updated_at'])
            group = locked_group

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
        _create_group_audit_log(group, request.user, 'member_remove', target_user=target.user)
        group.updated_at = timezone.now()
        group.save(update_fields=['updated_at'])
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('移除群成员错误', e)


@require_http_methods(["POST"])
@login_required
def set_group_member_role_api(request, group_id, user_id):
    try:
        from ...models import MessageGroup, MessageGroupMember
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        owner_error = _require_group_owner(membership)
        if owner_error is not None:
            return owner_error

        data = json.loads(request.body or '{}')
        role = data.get('role')
        if role not in ('admin', 'member'):
            return JsonResponse({'error': '角色只能设置为管理员或成员'}, status=400)

        target = get_object_or_404(MessageGroupMember, group=group, user_id=user_id, left_at__isnull=True)
        if target.role == 'owner':
            return JsonResponse({'error': '不能修改群主角色'}, status=400)
        old_role = target.role
        target.role = role
        target.save(update_fields=['role'])
        _create_group_audit_log(
            group,
            request.user,
            'member_role_change',
            target_user=target.user,
            metadata={'old_role': old_role, 'role': role},
        )
        group.updated_at = timezone.now()
        group.save(update_fields=['updated_at'])
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群成员角色错误', e)


@require_http_methods(["POST"])
@login_required
def mute_group_member_api(request, group_id, user_id):
    try:
        from ...models import MessageGroup, MessageGroupMember
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        data = json.loads(request.body or '{}')
        target = get_object_or_404(MessageGroupMember, group=group, user_id=user_id, left_at__isnull=True)
        if not _can_manage_target(membership, target):
            return JsonResponse({'error': '无权操作该成员'}, status=403)

        if data.get('action') == 'unmute':
            target.muted_until = None
            audit_action = 'member_unmute'
        else:
            target.muted_until = _parse_mute_until(data)
            audit_action = 'member_mute'
        target.save(update_fields=['muted_until'])
        _create_group_audit_log(
            group,
            request.user,
            audit_action,
            target_user=target.user,
            metadata={'muted_until': target.muted_until.isoformat() if target.muted_until else None},
        )
        group.updated_at = timezone.now()
        group.save(update_fields=['updated_at'])
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群成员禁言错误', e)


@require_http_methods(["GET", "POST"])
@login_required
def group_invite_links_api(request, group_id):
    try:
        from ...models import MessageGroup, MessageGroupInviteLink
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        if request.method == 'POST':
            data = json.loads(request.body or '{}')
            expires_at = None
            expires_in_minutes = data.get('expires_in_minutes')
            if expires_in_minutes not in (None, '', 0, '0'):
                try:
                    minutes = int(expires_in_minutes)
                except (TypeError, ValueError):
                    return JsonResponse({'error': '过期时间必须是分钟数'}, status=400)
                if minutes < 1:
                    return JsonResponse({'error': '过期时间必须大于 0'}, status=400)
                expires_at = timezone.now() + timedelta(minutes=min(minutes, 60 * 24 * 30))

            max_uses = data.get('max_uses')
            if max_uses in ('', 0, '0'):
                max_uses = None
            elif max_uses is not None:
                try:
                    max_uses = int(max_uses)
                except (TypeError, ValueError):
                    return JsonResponse({'error': '使用次数必须是数字'}, status=400)
                if max_uses < 1:
                    return JsonResponse({'error': '使用次数必须大于 0'}, status=400)
                max_uses = min(max_uses, 1000)

            with transaction.atomic():
                locked_group = MessageGroup.objects.select_for_update().get(id=group.id)
                if MessageGroupInviteLink.objects.filter(group=locked_group).exists():
                    return JsonResponse({'error': '每个群组仅能创建一个邀请链接'}, status=409)

                link = MessageGroupInviteLink.objects.create(
                    group=locked_group,
                    created_by=request.user,
                    expires_at=expires_at,
                    max_uses=max_uses,
                )
                _create_group_audit_log(
                    locked_group,
                    request.user,
                    'invite_link_create',
                    metadata={'invite_id': link.id, 'expires_at': expires_at.isoformat() if expires_at else None, 'max_uses': max_uses},
                )
            return JsonResponse({
                'status': 'success',
                'invite': _invite_link_payload(link, request),
            }, status=201)

        links = group.invite_links.select_related('created_by').order_by('-created_at')[:20]
        return JsonResponse({
            'status': 'success',
            'invites': [_invite_link_payload(link, request) for link in links],
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('处理群邀请链接错误', e)


@require_http_methods(["GET", "POST"])
@login_required
def group_bans_api(request, group_id):
    try:
        from ...models import MessageGroup, MessageGroupBan, MessageGroupMember
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        if request.method == 'GET':
            bans = (
                MessageGroupBan.objects
                .filter(group=group, revoked_at__isnull=True)
                .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
                .select_related('user', 'banned_by')
                .order_by('-created_at')[:100]
            )
            return JsonResponse({'status': 'success', 'bans': [_active_group_ban_payload(ban) for ban in bans]})

        data = json.loads(request.body or '{}')
        try:
            user_id = int(data.get('user_id'))
        except (TypeError, ValueError):
            return JsonResponse({'error': '请选择要封禁的用户'}, status=400)
        if user_id == request.user.id:
            return JsonResponse({'error': '不能封禁自己'}, status=400)

        target_user = get_object_or_404(User, id=user_id, is_active=True)
        target_membership = MessageGroupMember.objects.filter(
            group=group,
            user=target_user,
            left_at__isnull=True,
        ).first()
        if target_membership and not _can_manage_target(membership, target_membership):
            return JsonResponse({'error': '无权封禁该成员'}, status=403)

        reason = _body_string(data, 'reason')[:1000]
        try:
            expires_at = _parse_expires_at(data.get('expires_at'))
        except (TypeError, ValueError):
            return JsonResponse({'error': '过期时间格式错误'}, status=400)
        if expires_at and expires_at <= timezone.now():
            return JsonResponse({'error': '过期时间必须晚于当前时间'}, status=400)

        with transaction.atomic():
            existing = _get_active_group_ban(group, target_user)
            if existing:
                ban = existing
                ban.reason = reason
                ban.expires_at = expires_at
                ban.banned_by = request.user
                ban.save(update_fields=['reason', 'expires_at', 'banned_by'])
            else:
                ban = MessageGroupBan.objects.create(
                    group=group,
                    user=target_user,
                    banned_by=request.user,
                    reason=reason,
                    expires_at=expires_at,
                )
            if target_membership and data.get('remove_member', True):
                target_membership.left_at = timezone.now()
                target_membership.save(update_fields=['left_at'])
            group.updated_at = timezone.now()
            group.save(update_fields=['updated_at'])
            _create_group_audit_log(
                group,
                request.user,
                'member_ban',
                target_user=target_user,
                metadata={'reason': reason, 'expires_at': expires_at.isoformat() if expires_at else None},
            )

        return JsonResponse({'status': 'success', 'ban': _active_group_ban_payload(ban), 'group': _group_detail_payload(group, membership)}, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('处理群封禁错误', e)


@require_http_methods(["POST", "DELETE"])
@login_required
def revoke_group_ban_api(request, group_id, ban_id):
    try:
        from ...models import MessageGroup, MessageGroupBan
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error
        ban = get_object_or_404(MessageGroupBan.objects.select_related('user'), id=ban_id, group=group)
        if ban.revoked_at is None:
            ban.revoked_at = timezone.now()
            ban.revoked_by = request.user
            ban.save(update_fields=['revoked_at', 'revoked_by'])
            _create_group_audit_log(group, request.user, 'member_unban', target_user=ban.user)
        return JsonResponse({'status': 'success'})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('解除群封禁错误', e)


@require_http_methods(["GET"])
@login_required
def group_audit_logs_api(request, group_id):
    try:
        from ...models import MessageGroup, MessageGroupAuditLog
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error
        try:
            page = max(1, int(request.GET.get('page', '1')))
            page_size = min(100, max(1, int(request.GET.get('page_size', '30'))))
        except ValueError:
            return JsonResponse({'error': '分页参数错误'}, status=400)
        qs = MessageGroupAuditLog.objects.filter(group=group).select_related('actor', 'target_user').order_by('-created_at')
        count = qs.count()
        start = (page - 1) * page_size
        logs = qs[start:start + page_size]
        return JsonResponse({
            'status': 'success',
            'count': count,
            'results': [
                {
                    'id': log.id,
                    'actor': _user_payload(log.actor),
                    'target_user': _user_payload(log.target_user),
                    'action': log.action,
                    'metadata': log.metadata,
                    'created_at': log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取群审计日志错误', e)


@require_http_methods(["GET"])
@login_required
def preview_group_invite_api(request, token):
    try:
        from ...models import MessageGroupInviteLink, MessageGroupMember
        link = get_object_or_404(
            MessageGroupInviteLink.objects.select_related('group', 'created_by'),
            token=token,
        )
        group = link.group
        valid = link.is_valid()
        reason = ''
        if link.revoked_at is not None:
            reason = 'revoked'
        elif link.expires_at and link.expires_at <= timezone.now():
            reason = 'expired'
        elif link.max_uses is not None and link.uses_count >= link.max_uses:
            reason = 'max_uses_reached'
        elif not group.is_active:
            reason = 'group_inactive'

        member_limit = _group_member_limit_payload(group)
        membership = MessageGroupMember.objects.filter(group=group, user=request.user, left_at__isnull=True).first()
        ban = _get_active_group_ban(group, request.user)
        if member_limit['is_full'] and not reason:
            reason = 'group_full'
        can_join = bool(valid and membership is None and ban is None and not member_limit['is_full'])
        return JsonResponse({
            'status': 'success',
            'valid': valid,
            'reason': reason,
            'group': {
                'id': group.id,
                'name': group.name,
                'avatar': _group_avatar_url(group),
                'description': group.description,
                'require_approval': group.require_approval,
                **member_limit,
            },
            'link': {
                'expires_at': link.expires_at.isoformat() if link.expires_at else None,
                'max_uses': link.max_uses,
                'uses_count': link.uses_count,
                'remaining_uses': None if link.max_uses is None else max(0, link.max_uses - link.uses_count),
            },
            'viewer': {
                'is_member': membership is not None,
                'is_banned': ban is not None,
                'ban': _active_group_ban_payload(ban),
                'can_join': can_join,
            },
        })
    except Http404:
        return JsonResponse({'error': '邀请链接不存在'}, status=404)
    except Exception as e:
        return _server_error_response('预览群邀请错误', e)


@require_http_methods(["POST", "DELETE"])
@login_required
def revoke_group_invite_link_api(request, group_id, invite_id):
    try:
        from ...models import MessageGroup, MessageGroupInviteLink
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        link = get_object_or_404(MessageGroupInviteLink, id=invite_id, group=group)
        if link.revoked_at is None:
            link.revoked_at = timezone.now()
            link.save(update_fields=['revoked_at'])
            _create_group_audit_log(group, request.user, 'invite_link_revoke', metadata={'invite_id': link.id})
        return JsonResponse({'status': 'success', 'invite': _invite_link_payload(link, request)})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('撤销群邀请链接错误', e)


@require_http_methods(["POST"])
@login_required
def join_group_by_invite_api(request, token):
    try:
        from ...models import GroupJoinRequest, MessageGroupInviteLink, MessageGroupInviteUse, MessageGroupMember
        with transaction.atomic():
            link = get_object_or_404(
                MessageGroupInviteLink.objects.select_for_update().select_related('group'),
                token=token,
            )
            locked_group = link.group
            locked_group = locked_group.__class__.objects.select_for_update().get(id=locked_group.id)
            link.group = locked_group
            if not link.is_valid():
                return JsonResponse({'error': '邀请链接已失效'}, status=400)
            active_ban = _get_active_group_ban(link.group, request.user)
            if active_ban:
                return JsonResponse({
                    'error': '你已被该群组封禁，无法通过邀请链接加入',
                    'ban': _active_group_ban_payload(active_ban),
                }, status=403)

            membership = MessageGroupMember.objects.filter(group=link.group, user=request.user).first()
            if membership and membership.left_at is None:
                return JsonResponse({
                    'status': 'success',
                    'already_member': True,
                    'group': _group_detail_payload(link.group, membership),
                })

            current_count = _active_group_member_count(link.group)
            if current_count >= MAX_MESSAGE_GROUP_MEMBERS:
                return _group_full_response(link.group, current_count=current_count)

            if link.group.require_approval:
                request_message = ''
                try:
                    request_message = _body_string(json.loads(request.body or '{}'), 'request_message')[:200]
                except json.JSONDecodeError:
                    request_message = ''
                join_request, created_request = GroupJoinRequest.objects.get_or_create(
                    group=link.group,
                    user=request.user,
                    status='pending',
                    defaults={'request_message': request_message},
                )
                if not created_request and request_message and join_request.request_message != request_message:
                    join_request.request_message = request_message
                    join_request.save(update_fields=['request_message'])
                _create_group_audit_log(
                    link.group,
                    request.user,
                    'join_request_create',
                    target_user=request.user,
                    metadata={'via': 'invite', 'invite_id': link.id, 'request_id': join_request.id},
                )
                return JsonResponse({
                    'status': 'pending',
                    'pending_approval': True,
                    'message': '入群申请已提交，请等待管理员审批',
                    'request_id': join_request.id,
                    'group': {
                        'id': link.group.id,
                        'name': link.group.name,
                        'avatar': _group_avatar_url(link.group),
                    },
                }, status=202)

            if membership is None:
                membership = MessageGroupMember(group=link.group, user=request.user, role='member')
            membership.left_at = None
            membership.role = 'member'
            membership.muted_until = None
            membership.joined_at = timezone.now()
            membership.save()
            link.uses_count += 1
            link.save(update_fields=['uses_count'])
            MessageGroupInviteUse.objects.create(
                invite=link,
                group=link.group,
                user=request.user,
            )
            link.group.updated_at = timezone.now()
            link.group.save(update_fields=['updated_at'])
            _create_group_audit_log(link.group, request.user, 'member_add', target_user=request.user, metadata={'via': 'invite', 'invite_id': link.id})

        return JsonResponse({
            'status': 'success',
            'already_member': False,
            'group': _group_detail_payload(link.group, membership),
        })
    except Http404:
        return JsonResponse({'error': '邀请链接不存在'}, status=404)
    except Exception as e:
        return _server_error_response('加入群组错误', e)


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
        _create_group_audit_log(group, request.user, 'group_leave', target_user=request.user)
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
        _create_group_audit_log(group, request.user, 'group_dissolve')
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
                'description': group.description,
                'announcement': group.announcement,
                'mute_mode': group.mute_mode,
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
        from ...models import GroupMessage, GroupMessageMention, MessageAttachment, MessageGroup, MessageGroupMember, UserSanction
        data = json.loads(request.body)
        content = _body_string(data, 'content')
        try:
            attachment_ids = _normalize_attachment_ids(data.get('attachment_ids'))
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        if not content and not attachment_ids:
            return JsonResponse({'error': '消息内容不能为空'}, status=400)
        if len(content) > MESSAGE_CONTENT_MAX_LENGTH:
            return JsonResponse({'error': f'消息内容不能超过{MESSAGE_CONTENT_MAX_LENGTH}字'}, status=400)
        if False and data.get('attachment_ids'):
            return JsonResponse({'error': '群组暂不支持阅后即焚或附件消息'}, status=400)

        # Phase 2: 获取回复和转发参数
        reply_to_id = data.get('reply_to')
        forwarded_from_id = data.get('forwarded_from')
        mentioned_usernames = data.get('mentions', [])  # @提及的用户名列表
        mention_everyone = bool(data.get('mention_all')) or '@全体' in content or '@all' in content.lower()

        mute = UserSanction.is_muted(request.user)
        if mute is not None:
            return JsonResponse({'error': '你已被禁止发送私信'}, status=403)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        send_error = _can_send_group_message(group, membership)
        if send_error is not None:
            return send_error
        if mention_everyone and membership.role not in ('owner', 'admin') and not group.allow_member_mention_all:
            return JsonResponse({'error': '当前群组仅群主或管理员可以 @全体成员'}, status=403)

        # Phase 2: 验证回复消息
        reply_to_message = None
        if reply_to_id:
            try:
                reply_to_message = GroupMessage.objects.get(id=reply_to_id, group=group, is_recalled=False)
            except GroupMessage.DoesNotExist:
                return JsonResponse({'error': '回复的消息不存在或已撤回'}, status=400)

        # Phase 2: 验证转发消息
        forwarded_message = None
        try:
            attachments = _load_message_attachments(request.user, attachment_ids)
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        if forwarded_from_id:
            try:
                forwarded_message = GroupMessage.objects.get(id=forwarded_from_id, is_recalled=False)
            except GroupMessage.DoesNotExist:
                return JsonResponse({'error': '转发的消息不存在或已撤回'}, status=400)

        with transaction.atomic():
            message = GroupMessage.objects.create(
                group=group,
                sender=request.user,
                content=content,
                searchable_text=_message_searchable_text(content, attachments),
                reply_to=reply_to_message,
                forwarded_from=forwarded_message,
            )
            if attachments:
                updated_count = MessageAttachment.objects.filter(
                    id__in=attachment_ids,
                    uploader=request.user,
                    message__isnull=True,
                    group_message__isnull=True,
                ).update(group_message=message)
                if updated_count != len(attachment_ids):
                    raise ValueError('附件不存在、已发送或无权使用')

            if mention_everyone:
                mentioned_members = (
                    MessageGroupMember.objects
                    .filter(group=group, left_at__isnull=True)
                    .exclude(user=request.user)
                    .select_related('user')[:200]
                )
                for member in mentioned_members:
                    try:
                        notify_user(
                            member.user,
                            'group_mention_all',
                            f'{request.user.username} 在群组中 @全体成员',
                            f'在 {group.name} 中：{content[:80]}',
                            group_id=group.id,
                            message_id=message.id,
                        )
                    except Exception as e:
                        logger.warning(f'发送@全体通知失败: {e}')
                    transaction.on_commit(
                        lambda recipient=member.user, group=group, content=content: _maybe_send_group_mention_email(
                            request.user,
                            recipient,
                            group,
                            content,
                        )
                    )
                _create_group_audit_log(
                    group,
                    request.user,
                    'mention_all',
                    metadata={'message_id': message.id},
                )

            # Phase 2: 创建@提及记录
            if mentioned_usernames:
                # 获取群成员中被提及的用户
                mentioned_members = MessageGroupMember.objects.filter(
                    group=group,
                    user__username__in=mentioned_usernames,
                    left_at__isnull=True
                ).select_related('user')

                for member in mentioned_members:
                    GroupMessageMention.objects.create(
                        message=message,
                        mentioned_user=member.user
                    )
                    # 可选：发送通知给被提及的用户
                    if member.user.id != request.user.id:  # 不通知自己
                        try:
                            notify_user(
                                member.user,
                                'group_mention',
                                f'{request.user.username} 在群组中提到了你',
                                f'在 {group.name} 中: {content[:50]}...' if len(content) > 50 else content,
                                group_id=group.id,
                                message_id=message.id,
                            )
                        except Exception as e:
                            logger.warning(f'发送提及通知失败: {e}')
                        transaction.on_commit(
                            lambda recipient=member.user, group=group, content=content: _maybe_send_group_mention_email(
                                request.user,
                                recipient,
                                group,
                                content,
                            )
                        )

            group.updated_at = timezone.now()
            group.save(update_fields=['updated_at'])
            membership.force_unread = False
            membership.last_read_at = timezone.now()
            membership.save(update_fields=['force_unread', 'last_read_at'])

        message = GroupMessage.objects.select_related('sender', 'group').prefetch_related('attachments').get(id=message.id)
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
def pin_group_message_api(request, group_id, message_id):
    try:
        from ...models import GroupMessage, MessageGroup
        data = json.loads(request.body or '{}')
        action = data.get('action', 'pin')
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        message = get_object_or_404(GroupMessage, id=message_id, group=group, is_recalled=False)
        if action == 'unpin' or group.pinned_message_id == message.id:
            group.pinned_message = None
            audit_action = 'group_message_unpin'
        else:
            group.pinned_message = message
            audit_action = 'group_message_pin'
        group.updated_at = timezone.now()
        group.save(update_fields=['pinned_message', 'updated_at'])
        _create_group_audit_log(
            group,
            request.user,
            audit_action,
            target_user=message.sender,
            metadata={'message_id': message.id},
        )
        return JsonResponse({
            'status': 'success',
            'group': _group_detail_payload(group, membership),
            'message': _group_message_payload(message, viewer=request.user),
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群消息置顶错误', e)


@require_http_methods(["GET"])
@login_required
def group_shared_items_api(request, group_id):
    try:
        from ...models import MessageGroup
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        links = []
        seen = set()
        qs = _visible_group_messages_qs(group, membership).order_by('-created_at')[:200]
        for message in qs:
            for url in _extract_links_from_text(message.content):
                if url in seen:
                    continue
                seen.add(url)
                links.append({
                    'url': url,
                    'sender': _user_payload(message.sender),
                    'message_id': message.id,
                    'created_at': message.created_at.isoformat() if message.created_at else None,
                })
                if len(links) >= 50:
                    break
            if len(links) >= 50:
                break

        return JsonResponse({
            'status': 'success',
            'links': links,
            'files': [],
            'images': [],
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取群资料聚合错误', e)


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


@require_http_methods(["GET"])
@login_required
def check_transfer_eligibility_api(request, group_id, user_id):
    """检查指定用户是否满足群主转让条件"""
    try:
        from ...models import MessageGroup, MessageGroupMember, MessageGroupPolicy

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        # 只有群主可以查询转让资格
        owner_error = _require_group_owner(membership)
        if owner_error is not None:
            return owner_error

        # 验证目标用户是群成员
        target_membership = get_object_or_404(
            MessageGroupMember,
            group=group,
            user_id=user_id,
            left_at__isnull=True,
        )

        # 获取群组创建策略
        policy = MessageGroupPolicy.get_current()
        policy_eligible, stats = policy.can_create_group(target_membership.user)
        owned_limit = _owned_group_limit_payload(target_membership.user, exclude_group_id=group.id)
        eligible = policy_eligible and owned_limit['within_owned_group_limit']

        return JsonResponse({
            'status': 'success',
            'eligible': eligible,
            'policy_eligible': policy_eligible,
            'stats': stats,
            'policy': {
                'enabled': policy.enabled,
                'min_public_notes': policy.min_public_notes,
                'min_followers': policy.min_followers,
            },
            'owned_group_count': owned_limit['owned_group_count'],
            'max_owned_groups': owned_limit['max_owned_groups'],
            'reasons': {
                'public_notes': stats['public_notes'] >= policy.min_public_notes,
                'followers': stats['followers'] >= policy.min_followers,
                'owned_groups': owned_limit['within_owned_group_limit'],
            },
            'user': {
                'id': target_membership.user.id,
                'username': target_membership.user.username,
            },
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('检查转让资格错误', e)


# ==================== Phase 2: 表情回应 API ====================

@require_http_methods(["POST"])
@login_required
def toggle_message_reaction_api(request, group_id, message_id):
    """切换消息表情回应（添加或移除）"""
    try:
        from ...models import GroupMessage, GroupMessageReaction, MessageGroup

        data = json.loads(request.body)
        emoji = data.get('emoji', '').strip()

        if not emoji:
            return JsonResponse({'error': '表情符号不能为空'}, status=400)

        if len(emoji) > 20:
            return JsonResponse({'error': '表情符号过长'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        message = get_object_or_404(GroupMessage, id=message_id, group=group, is_recalled=False)

        # 尝试移除已有的反应
        existing = GroupMessageReaction.objects.filter(
            message=message,
            user=request.user,
            emoji=emoji
        ).first()

        if existing:
            existing.delete()
            action = 'removed'
        else:
            # 添加新反应
            GroupMessageReaction.objects.create(
                message=message,
                user=request.user,
                emoji=emoji
            )
            action = 'added'

        # 返回更新后的反应统计
        from django.db.models import Count
        reaction_stats = message.reactions.values('emoji').annotate(count=Count('id'))
        reactions = {}
        for stat in reaction_stats:
            e = stat['emoji']
            count = stat['count']
            users = list(message.reactions.filter(emoji=e).select_related('user')[:3])
            reactions[e] = {
                'count': count,
                'users': [{'user_id': r.user_id, 'username': r.user.username} for r in users],
                'reacted_by_me': any(r.user_id == request.user.id for r in users),
            }

        return JsonResponse({
            'status': 'success',
            'action': action,
            'reactions': reactions,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('切换表情回应错误', e)


# ==================== Phase 3: 入群审批 API ====================

@require_http_methods(["POST"])
@login_required
def request_join_group_api(request, group_id):
    """申请加入群组（需要审批时使用）"""
    try:
        from ...models import GroupJoinRequest, MessageGroup

        data = json.loads(request.body)
        request_message = data.get('message', '').strip()

        if len(request_message) > 200:
            return JsonResponse({'error': '申请留言不能超过200字'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)

        # 检查是否需要审批
        if not group.require_approval:
            return JsonResponse({'error': '此群组无需审批，请直接通过邀请链接加入'}, status=400)

        # 检查是否已经是成员
        from ...models import MessageGroupMember
        existing_membership = MessageGroupMember.objects.filter(
            group=group,
            user=request.user,
            left_at__isnull=True
        ).first()

        if existing_membership:
            return JsonResponse({'error': '你已经是群成员'}, status=400)

        member_limit = _group_member_limit_payload(group)
        if member_limit['is_full']:
            return _group_full_response(group, current_count=member_limit['member_count'])

        # 检查是否有待处理的申请
        pending_request = GroupJoinRequest.objects.filter(
            group=group,
            user=request.user,
            status='pending'
        ).first()

        if pending_request:
            return JsonResponse({'error': '你已有待处理的入群申请'}, status=400)

        # 创建申请
        join_request = GroupJoinRequest.objects.create(
            group=group,
            user=request.user,
            request_message=request_message,
            status='pending'
        )

        # 通知群主和管理员
        admins = MessageGroupMember.objects.filter(
            group=group,
            role__in=['owner', 'admin'],
            left_at__isnull=True
        ).select_related('user')

        for admin_member in admins:
            try:
                notify_user(
                    admin_member.user,
                    'group_join_request',
                    f'{request.user.username} 申请加入群组',
                    f'群组：{group.name}\n留言：{request_message}',
                    group_id=group.id,
                    request_id=join_request.id,
                )
            except Exception as e:
                logger.warning(f'发送入群申请通知失败: {e}')

        return JsonResponse({
            'status': 'success',
            'message': '申请已提交，请等待管理员审批',
            'request_id': join_request.id,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('申请加入群组错误', e)


@require_http_methods(["GET"])
@login_required
def group_join_requests_api(request, group_id):
    """获取群组的入群申请列表（群主和管理员可查看）"""
    try:
        from ...models import GroupJoinRequest, MessageGroup

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        # 只有群主和管理员可以查看
        if membership.role not in ['owner', 'admin']:
            return JsonResponse({'error': '权限不足'}, status=403)

        status_filter = request.GET.get('status', 'pending')
        requests = GroupJoinRequest.objects.filter(
            group=group,
            status=status_filter
        ).select_related('user', 'reviewed_by').order_by('-created_at')

        results = []
        for req in requests:
            results.append({
                'id': req.id,
                'user': {
                    'id': req.user.id,
                    'username': req.user.username,
                    'avatar': _get_avatar_url(req.user),
                },
                'request_message': req.request_message,
                'status': req.status,
                'reviewed_by': {
                    'id': req.reviewed_by.id,
                    'username': req.reviewed_by.username,
                } if req.reviewed_by else None,
                'rejection_reason': req.rejection_reason,
                'created_at': req.created_at.isoformat(),
                'reviewed_at': req.reviewed_at.isoformat() if req.reviewed_at else None,
            })

        return JsonResponse({
            'status': 'success',
            'requests': results,
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取入群申请列表错误', e)


@require_http_methods(["POST"])
@login_required
def review_join_request_api(request, group_id, request_id):
    """审批入群申请"""
    try:
        from ...models import GroupJoinRequest, MessageGroup, MessageGroupAuditLog, MessageGroupMember

        data = json.loads(request.body)
        action = data.get('action')  # 'approve' 或 'reject'
        rejection_reason = data.get('rejection_reason', '').strip()

        if action not in ['approve', 'reject']:
            return JsonResponse({'error': '无效的审批操作'}, status=400)

        if action == 'reject' and not rejection_reason:
            return JsonResponse({'error': '拒绝申请需要填写原因'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        # 只有群主和管理员可以审批
        if membership.role not in ['owner', 'admin']:
            return JsonResponse({'error': '权限不足'}, status=403)

        join_request = get_object_or_404(GroupJoinRequest, id=request_id, group=group)

        if join_request.status != 'pending':
            return JsonResponse({'error': '该申请已被处理'}, status=400)

        with transaction.atomic():
            if action == 'approve':
                locked_group = MessageGroup.objects.select_for_update().get(id=group.id)
                current_count = _active_group_member_count(locked_group)
                existing_active = MessageGroupMember.objects.filter(
                    group=locked_group,
                    user=join_request.user,
                    left_at__isnull=True,
                ).exists()
                if not existing_active and current_count >= MAX_MESSAGE_GROUP_MEMBERS:
                    return _group_full_response(locked_group, current_count=current_count)

                target_member, created_member = MessageGroupMember.objects.get_or_create(
                    group=locked_group,
                    user=join_request.user,
                    defaults={'role': 'member'},
                )
                if not created_member:
                    target_member.left_at = None
                    target_member.role = 'member'
                    target_member.muted_until = None
                    target_member.joined_at = timezone.now()
                    target_member.save(update_fields=['left_at', 'role', 'muted_until', 'joined_at'])
                join_request.status = 'approved'
                join_request.reviewed_by = request.user
                join_request.reviewed_at = timezone.now()
                join_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

                # 记录审计日志
                MessageGroupAuditLog.objects.create(
                    group=locked_group,
                    actor=request.user,
                    target_user=join_request.user,
                    action='member_add',
                    metadata={'via': 'join_request_approval', 'request_id': request_id}
                )

                # 通知申请人
                notify_user(
                    join_request.user,
                    'group_join_approved',
                    '入群申请已通过',
                    f'你的加入 {group.name} 的申请已通过',
                    group_id=locked_group.id,
                )

                message = '申请已通过'
            else:
                # 拒绝申请
                join_request.status = 'rejected'
                join_request.reviewed_by = request.user
                join_request.reviewed_at = timezone.now()
                join_request.rejection_reason = rejection_reason
                join_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason'])

                # 通知申请人
                notify_user(
                    join_request.user,
                    'group_join_rejected',
                    '入群申请被拒绝',
                    f'你的加入 {group.name} 的申请被拒绝\n原因：{rejection_reason}',
                    group_id=group.id,
                )

                message = '申请已拒绝'

            group.updated_at = timezone.now()
            group.save(update_fields=['updated_at'])

        return JsonResponse({
            'status': 'success',
            'message': message,
            'group': _group_detail_payload(group, membership),
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('审批入群申请错误', e)


# ==================== Phase 3: 群公告管理 API ====================

@require_http_methods(["POST"])
@login_required
def update_group_announcement_api(request, group_id):
    """更新群公告"""
    try:
        from ...models import (
            MessageGroup,
            MessageGroupAnnouncementHistory,
            MessageGroupAnnouncementRead,
            MessageGroupAuditLog,
        )

        data = json.loads(request.body)
        announcement = data.get('announcement', '').strip()
        pin = data.get('pin', False)  # 是否置顶

        if len(announcement) > 2000:
            return JsonResponse({'error': '群公告不能超过2000字'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        # 只有群主和管理员可以修改公告
        if membership.role not in ['owner', 'admin']:
            return JsonResponse({'error': '权限不足'}, status=403)

        with transaction.atomic():
            group.announcement = announcement
            group.announcement_updated_by = request.user
            if pin:
                group.announcement_pinned_at = timezone.now()
            else:
                group.announcement_pinned_at = None
            group.save(update_fields=['announcement', 'announcement_updated_by', 'announcement_pinned_at', 'updated_at'])
            history = MessageGroupAnnouncementHistory.objects.create(
                group=group,
                editor=request.user,
                content=announcement,
                pinned=bool(pin),
            )
            MessageGroupAnnouncementRead.objects.update_or_create(
                group=group,
                user=request.user,
                announcement=history,
                defaults={'read_at': timezone.now()},
            )

            # 记录审计日志
            MessageGroupAuditLog.objects.create(
                group=group,
                actor=request.user,
                action='group_announcement_update',
                metadata={'pinned': pin}
            )

        return JsonResponse({
            'status': 'success',
            'group': _group_detail_payload(group, membership),
            'announcement': announcement,
            'pinned_at': group.announcement_pinned_at.isoformat() if group.announcement_pinned_at else None,
            'read_stats': _announcement_read_payload(group, history),
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群公告错误', e)


@require_http_methods(["GET", "POST"])
@login_required
def group_announcement_reads_api(request, group_id):
    try:
        from ...models import MessageGroup, MessageGroupAnnouncementRead

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        announcement = group.announcement_history.order_by('-created_at').first()
        if request.method == "POST" and announcement:
            MessageGroupAnnouncementRead.objects.update_or_create(
                group=group,
                user=request.user,
                announcement=announcement,
                defaults={'read_at': timezone.now()},
            )

        return JsonResponse({
            'status': 'success',
            'read_stats': _announcement_read_payload(group, announcement),
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('Group announcement read status error', e)
