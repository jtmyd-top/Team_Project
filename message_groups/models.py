"""Compatibility model exports for the message group domain.

The database models still live in ``messaging.models`` for now. This module
gives new group code a domain-specific import path without changing app_label,
content types, permissions, or database tables.
"""
from messaging.models import (
    GroupJoinRequest,
    GroupMessage,
    GroupMessageDeletion,
    GroupMessageMention,
    GroupMessageReaction,
    GroupTag,
    GroupTagRelation,
    MessageGroup,
    MessageGroupAnnouncementHistory,
    MessageGroupAnnouncementRead,
    MessageGroupAuditLog,
    MessageGroupBan,
    MessageGroupInviteLink,
    MessageGroupInviteUse,
    MessageGroupMember,
    MessageGroupPolicy,
    generate_group_invite_token,
)

__all__ = [
    'GroupJoinRequest',
    'GroupMessage',
    'GroupMessageDeletion',
    'GroupMessageMention',
    'GroupMessageReaction',
    'GroupTag',
    'GroupTagRelation',
    'MessageGroup',
    'MessageGroupAnnouncementHistory',
    'MessageGroupAnnouncementRead',
    'MessageGroupAuditLog',
    'MessageGroupBan',
    'MessageGroupInviteLink',
    'MessageGroupInviteUse',
    'MessageGroupMember',
    'MessageGroupPolicy',
    'generate_group_invite_token',
]
