"""Group common announcements helpers."""
from .base import *  # noqa: F401,F403
from .users import _user_payload

def _announcement_read_payload(group, announcement=None):
    from messaging.models import MessageGroupAnnouncementRead

    if announcement is None:
        announcement = _latest_active_announcement(group)

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

def _latest_active_announcement(group):
    return (
        group.announcement_history
        .filter(deleted_at__isnull=True)
        .order_by('-pinned', '-updated_at', '-created_at')
        .first()
    )

def _announcement_history_payload(item):
    return {
        'id': item.id,
        'editor': _user_payload(item.editor),
        'content': item.content,
        'pinned': item.pinned,
        'message_id': item.message_id,
        'created_at': item.created_at.isoformat() if item.created_at else None,
        'updated_at': item.updated_at.isoformat() if getattr(item, 'updated_at', None) else None,
        'deleted_at': item.deleted_at.isoformat() if getattr(item, 'deleted_at', None) else None,
    }

def _announcement_message_content(content):
    return f"@全体成员 - {content.strip()}"

def _sync_group_announcement_summary(group):
    latest = _latest_active_announcement(group)
    group.announcement = latest.content if latest else ''
    group.announcement_updated_by = latest.editor if latest else None
    group.announcement_pinned_at = timezone.now() if latest and latest.pinned else None
    return latest

def _notify_announcement_everyone(group, sender, content, message=None):
    """
    通知群组所有成员关于新公告

    改进：
    - 分批处理通知，避免大群组性能问题
    - 记录跳过的成员数量
    - 改进错误处理和日志

    Args:
        group: MessageGroup 实例
        sender: 发送者 User 实例
        content: 公告内容
        message: GroupMessage 实例（可选，用于关联通知）
    """
    from messaging.models import MessageGroupMember

    # 获取所有活跃成员（排除发送者）
    all_members = (
        MessageGroupMember.objects
        .filter(group=group, left_at__isnull=True)
        .exclude(user=sender)
        .select_related('user')
    )

    total_count = all_members.count()
    batch_size = 200
    notified_count = 0
    failed_count = 0

    # 分批处理
    members_to_notify = all_members[:batch_size]
    skipped_count = max(0, total_count - batch_size)

    if skipped_count > 0:
        logger.warning(
            f'群公告通知: 群组 {group.id} ({group.name}) 有 {total_count} 名成员，'
            f'仅通知前 {batch_size} 名，跳过 {skipped_count} 名'
        )

    for member in members_to_notify:
        try:
            notify_user(
                member.user,
                'group_mention_all',
                f'{sender.username} 发布了群公告',
                f'在 {group.name} 中：{content[:80]}',
                group_id=group.id,
                message_id=message.id if message else None,
            )
            notified_count += 1

            # 邮件通知
            transaction.on_commit(
                lambda recipient=member.user, group=group, content=content: _maybe_send_group_mention_email(
                    sender,
                    recipient,
                    group,
                    content,
                )
            )
        except Exception as e:
            failed_count += 1
            logger.warning(f'发送群公告通知失败 (用户 {member.user_id}): {e}')

    logger.info(
        f'群公告通知完成: 群组 {group.id} ({group.name}), '
        f'成功 {notified_count}/{total_count}, 失败 {failed_count}, 跳过 {skipped_count}'
    )

__all__ = [
    '_announcement_read_payload',
    '_latest_active_announcement',
    '_announcement_history_payload',
    '_announcement_message_content',
    '_sync_group_announcement_summary',
    '_notify_announcement_everyone',
]
