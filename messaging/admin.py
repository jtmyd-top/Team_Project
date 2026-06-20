from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    ConversationSettings,
    Message,
    MessageAttachment,
    MessagePreference,
    NewConversationQuotaLog,
    UserBlocklist,
    UserFollow,
)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'recipient', 'short_content', 'is_read',
                    'is_recalled', 'deleted_for_sender', 'deleted_for_recipient', 'created_at')
    list_filter = ('is_read', 'is_recalled', 'created_at')
    search_fields = ('sender__username', 'recipient__username', 'content', 'searchable_text')
    readonly_fields = ('created_at', 'read_at', 'recalled_at')
    autocomplete_fields = ['sender', 'recipient']

    @admin.display(description='内容')
    def short_content(self, obj):
        return (obj.content or '')[:40]


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        'original_name',
        'attachment_status',
        'attachment_type',
        'uploader',
        'message',
        'group_message',
        'size',
        'created_at',
    )
    list_filter = ('attachment_type', 'created_at')
    search_fields = ('original_name', 'uploader__username', 'message__content', 'group_message__content')
    readonly_fields = ('attachment_status', 'created_at')
    autocomplete_fields = ['uploader', 'message', 'group_message']

    @admin.display(description='附件状态')
    def attachment_status(self, obj):
        if not obj.file:
            return format_html('<span style="color: #6b7280; font-weight: 500;">无附件文件</span>')

        if obj.reports.filter(status='pending').exists():
            review_url = reverse('review_reported_attachment', args=[obj.id])
            return format_html(
                '<a href="{}" target="_blank" style="color: #ef4444; font-weight: bold;">收到举报（点击审查）</a>',
                review_url,
            )

        return format_html('<span style="color: #10b981; font-weight: 500;">正常</span>')


@admin.register(MessagePreference)
class MessagePreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'allow_messages', 'message_mode',
                    'show_read_status', 'auto_reply_enabled', 'updated_at')
    list_filter = ('allow_messages', 'message_mode')
    search_fields = ('user__username',)
    autocomplete_fields = ['user', 'email_mention_groups']


@admin.register(UserBlocklist)
class UserBlocklistAdmin(admin.ModelAdmin):
    list_display = ('user', 'blocked_user', 'reason', 'created_at')
    search_fields = ('user__username', 'blocked_user__username')
    autocomplete_fields = ['user', 'blocked_user']


@admin.register(UserFollow)
class UserFollowAdmin(admin.ModelAdmin):
    list_display = ('follower', 'following', 'created_at')
    search_fields = ('follower__username', 'following__username')
    autocomplete_fields = ['follower', 'following']


@admin.register(NewConversationQuotaLog)
class NewConversationQuotaLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'peer', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'peer__username')
    autocomplete_fields = ['user', 'peer']


@admin.register(ConversationSettings)
class ConversationSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'peer', 'is_pinned', 'is_muted', 'is_archived',
                    'disappearing_enabled', 'force_unread', 'updated_at')
    list_filter = ('is_pinned', 'is_muted', 'is_archived', 'disappearing_enabled')
    search_fields = ('user__username', 'peer__username')
    autocomplete_fields = ['user', 'peer']
