"""Messaging app view exports.

私信 / 对话设置 / 屏蔽 / 用户搜索与公开资料相关视图。

原单文件 `views/message.py` (2044 行) 按职责拆分为:
- `_constants`    模块常量
- `_helpers`      跨子模块复用的工具函数(下划线前缀,不对外暴露)
- `conversation`  对话核心:发送/转发/读取/列表/删除/撤回/标记/置顶/免打扰/归档/阅后即焚/设置查询
- `attachment`    附件上传 / 受控访问 / 历史目录拦截
- `report`        附件举报 / 管理员审查 / 用户举报
- `preference`    私信偏好 / 屏蔽 / 账户可发现性
- `search`        全局消息搜索 / 对话导出
- `users`         公开资料 / 精准用户搜索 / 私信页 / 未读数 / 在线心跳

外部 (urls.py 等) 通过 `views.xxx` 访问的所有公开符号在此重新导出,
拆分对外部调用方零影响。
"""
# 兼容: views/profile.py 反向引用了原 message 模块的私有头像工具
from ._helpers import _get_avatar_url  # noqa: F401

from .attachment import (
    blocked_message_attachment_media_api,
    message_attachment_file_api,
    upload_message_attachment_api,
)
from .conversation import (
    bulk_delete_messages_api,
    clear_conversation_api,
    delete_message_api,
    forward_message_api,
    get_conversation_settings_api,
    get_message_conversations_api,
    get_messages_api,
    mark_conversation_read_api,
    mark_conversation_unread_api,
    send_message_api,
    set_disappearing_api,
    toggle_archive_api,
    toggle_mute_api,
    toggle_pin_api,
)
from .preference import (
    block_user_api,
    get_blocked_users_api,
    get_message_preference_api,
    unblock_user_api,
    update_discoverability_api,
    update_message_preference_api,
)
from .report import (
    report_message_attachment_api,
    report_user_api,
    review_reported_attachment,
)
from .search import export_conversation_api, search_messages_api
from .users import (
    get_unread_messages_count_api,
    get_user_public_profile_api,
    messages_view,
    search_users_api,
    touch_messages_page_api,
)

_GROUP_VIEW_EXPORTS = {
    'add_group_members_api',
    'check_transfer_eligibility_api',
    'create_message_group_api',
    'delete_group_message_api',
    'dissolve_message_group_api',
    'edit_group_message_api',
    'group_audit_logs_api',
    'group_announcement_detail_api',
    'group_announcement_reads_api',
    'group_bans_api',
    'group_invite_links_api',
    'group_join_requests_api',
    'group_shared_items_api',
    'get_group_messages_api',
    'get_group_policy_api',
    'join_group_by_invite_api',
    'leave_message_group_api',
    'message_group_detail_api',
    'mute_group_member_api',
    'preview_group_invite_api',
    'pin_group_message_api',
    'remove_group_member_api',
    'report_group_message_api',
    'request_join_group_api',
    'review_join_request_api',
    'revoke_group_ban_api',
    'revoke_group_invite_link_api',
    'send_group_message_api',
    'set_group_member_role_api',
    'set_group_mute_mode_api',
    'toggle_group_setting_api',
    'toggle_message_reaction_api',
    'transfer_group_ownership_api',
    'update_group_announcement_api',
    'update_group_profile_api',
}


def __getattr__(name):
    if name in _GROUP_VIEW_EXPORTS:
        from message_groups import views as group_views
        value = getattr(group_views, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # attachment
    'blocked_message_attachment_media_api',
    'message_attachment_file_api',
    'upload_message_attachment_api',
    # conversation
    'bulk_delete_messages_api',
    'clear_conversation_api',
    'delete_message_api',
    'forward_message_api',
    'get_conversation_settings_api',
    'get_message_conversations_api',
    'get_messages_api',
    'mark_conversation_read_api',
    'mark_conversation_unread_api',
    'send_message_api',
    'set_disappearing_api',
    'toggle_archive_api',
    'toggle_mute_api',
    'toggle_pin_api',
    # groups
    'add_group_members_api',
    'check_transfer_eligibility_api',
    'create_message_group_api',
    'delete_group_message_api',
    'dissolve_message_group_api',
    'edit_group_message_api',
    'group_audit_logs_api',
    'group_announcement_detail_api',
    'group_announcement_reads_api',
    'group_bans_api',
    'group_invite_links_api',
    'group_join_requests_api',
    'group_shared_items_api',
    'get_group_messages_api',
    'get_group_policy_api',
    'join_group_by_invite_api',
    'leave_message_group_api',
    'message_group_detail_api',
    'mute_group_member_api',
    'preview_group_invite_api',
    'pin_group_message_api',
    'remove_group_member_api',
    'report_group_message_api',
    'request_join_group_api',
    'review_join_request_api',
    'revoke_group_ban_api',
    'revoke_group_invite_link_api',
    'send_group_message_api',
    'set_group_member_role_api',
    'set_group_mute_mode_api',
    'toggle_group_setting_api',
    'toggle_message_reaction_api',
    'transfer_group_ownership_api',
    'update_group_announcement_api',
    'update_group_profile_api',
    # preference
    'block_user_api',
    'get_blocked_users_api',
    'get_message_preference_api',
    'unblock_user_api',
    'update_discoverability_api',
    'update_message_preference_api',
    # report
    'report_message_attachment_api',
    'report_user_api',
    'review_reported_attachment',
    # search
    'export_conversation_api',
    'search_messages_api',
    # users
    'get_unread_messages_count_api',
    'get_user_public_profile_api',
    'messages_view',
    'search_users_api',
    'touch_messages_page_api',
]
