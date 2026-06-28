from django.contrib import admin

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
)


@admin.register(MessageGroupPolicy)
class MessageGroupPolicyAdmin(admin.ModelAdmin):
    list_display = ('enabled', 'min_public_notes', 'min_followers', 'updated_at')
    fields = ('enabled', 'min_public_notes', 'min_followers')

    def has_add_permission(self, request):
        return not MessageGroupPolicy.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class MessageGroupMemberInline(admin.TabularInline):
    model = MessageGroupMember
    extra = 0
    autocomplete_fields = ['user']
    fields = ('user', 'role', 'muted_until', 'joined_at', 'left_at', 'is_muted')
    readonly_fields = ('joined_at',)


@admin.register(MessageGroup)
class MessageGroupAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'owner',
        'mute_mode',
        'allow_new_members_view_history',
        'is_active',
        'created_at',
        'updated_at',
    )
    list_filter = ('is_active', 'mute_mode', 'allow_new_members_view_history', 'created_at')
    search_fields = ('name', 'description', 'announcement', 'owner__username')
    autocomplete_fields = ['owner', 'created_by']
    inlines = [MessageGroupMemberInline]


@admin.register(MessageGroupInviteLink)
class MessageGroupInviteLinkAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'created_by', 'uses_count', 'max_uses', 'expires_at', 'revoked_at', 'created_at')
    list_filter = ('created_at', 'expires_at', 'revoked_at')
    search_fields = ('group__name', 'token', 'created_by__username')
    readonly_fields = ('token', 'created_at', 'uses_count')
    autocomplete_fields = ['group', 'created_by']


@admin.register(MessageGroupInviteUse)
class MessageGroupInviteUseAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'invite', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('group__name', 'invite__token', 'user__username')
    autocomplete_fields = ['group', 'invite', 'user']
    readonly_fields = ('created_at',)


@admin.register(MessageGroupAnnouncementHistory)
class MessageGroupAnnouncementHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'editor', 'pinned', 'created_at')
    list_filter = ('pinned', 'created_at')
    search_fields = ('group__name', 'editor__username', 'content')
    autocomplete_fields = ['group', 'editor', 'message']
    readonly_fields = ('created_at',)


@admin.register(MessageGroupAnnouncementRead)
class MessageGroupAnnouncementReadAdmin(admin.ModelAdmin):
    list_display = ('announcement', 'user', 'read_at')
    list_filter = ('read_at',)
    search_fields = ('announcement__group__name', 'user__username')
    autocomplete_fields = ['announcement', 'user']


@admin.register(GroupMessage)
class GroupMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'sender', 'short_content', 'is_recalled', 'was_reported', 'created_at')
    list_filter = ('is_recalled', 'was_reported', 'created_at')
    search_fields = ('group__name', 'sender__username', 'content', 'searchable_text')
    readonly_fields = ('created_at', 'recalled_at')
    autocomplete_fields = ['group', 'sender', 'reply_to', 'forwarded_from']

    @admin.display(description='内容')
    def short_content(self, obj):
        return (obj.content or '')[:40]


@admin.register(GroupMessageDeletion)
class GroupMessageDeletionAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('message__content', 'user__username')
    autocomplete_fields = ['message', 'user']


@admin.register(MessageGroupBan)
class MessageGroupBanAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'user', 'banned_by', 'expires_at', 'revoked_at', 'created_at')
    list_filter = ('created_at', 'expires_at', 'revoked_at')
    search_fields = ('group__name', 'user__username', 'banned_by__username', 'reason')
    autocomplete_fields = ['group', 'user', 'banned_by', 'revoked_by']
    readonly_fields = ('created_at',)


@admin.register(MessageGroupAuditLog)
class MessageGroupAuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'actor', 'target_user', 'action', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('group__name', 'actor__username', 'target_user__username')
    autocomplete_fields = ['group', 'actor', 'target_user']
    readonly_fields = ('created_at', 'metadata')


@admin.register(GroupMessageMention)
class GroupMessageMentionAdmin(admin.ModelAdmin):
    list_display = ('message', 'mentioned_user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('message__content', 'mentioned_user__username')
    autocomplete_fields = ['message', 'mentioned_user']


@admin.register(GroupMessageReaction)
class GroupMessageReactionAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'emoji', 'created_at')
    list_filter = ('emoji', 'created_at')
    search_fields = ('message__content', 'user__username', 'emoji')
    autocomplete_fields = ['message', 'user']


@admin.register(GroupJoinRequest)
class GroupJoinRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'user', 'status', 'reviewed_by', 'created_at', 'reviewed_at')
    list_filter = ('status', 'created_at', 'reviewed_at')
    search_fields = ('group__name', 'user__username', 'request_message')
    autocomplete_fields = ['group', 'user', 'reviewed_by']


@admin.register(GroupTag)
class GroupTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'created_at')
    search_fields = ('name',)


@admin.register(GroupTagRelation)
class GroupTagRelationAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'tag', 'created_at')
    list_filter = ('tag', 'created_at')
    search_fields = ('user__username', 'group__name', 'tag__name')
    autocomplete_fields = ['user', 'group', 'tag']
