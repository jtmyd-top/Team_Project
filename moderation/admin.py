from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    AttachmentReport,
    CommentReport,
    MessageReport,
    ModerationAppeal,
    ModerationLog,
    ModerationTemplate,
    NoteReport,
    UserSanction,
)


@admin.register(MessageReport)
class MessageReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'reporter', 'reported_user', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('reporter__username', 'reported_user__username', 'detail')
    readonly_fields = ('reporter', 'reported_user', 'message', 'group_message', 'reason', 'detail', 'created_at')
    autocomplete_fields = ['reporter', 'reported_user', 'message', 'group_message']
    actions = ['mark_resolved', 'mark_dismissed']

    @admin.action(description='标记为已处理')
    def mark_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='resolved', resolved_at=timezone.now())

    @admin.action(description='标记为已驳回')
    def mark_dismissed(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='dismissed', resolved_at=timezone.now())


@admin.register(AttachmentReport)
class AttachmentReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'attachment', 'reporter', 'status', 'review_link', 'created_at', 'handled_at', 'handled_by')
    list_filter = ('status', 'created_at', 'handled_at')
    search_fields = ('attachment__original_name', 'reporter__username', 'reason', 'detail')
    readonly_fields = ('attachment', 'reporter', 'reason', 'detail', 'created_at', 'handled_at', 'handled_by', 'review_link')
    autocomplete_fields = ['attachment', 'reporter', 'handled_by']
    actions = ['mark_removed', 'mark_dismissed']

    def save_model(self, request, obj, form, change):
        if change and obj.status != 'pending':
            from django.utils import timezone

            previous_status = type(obj).objects.only('status').get(pk=obj.pk).status
            if previous_status == 'pending' and obj.handled_at is None:
                obj.handled_at = timezone.now()
                obj.handled_by = request.user
            obj.pending_dedup_key = 'pending' if obj.status == 'pending' else None
        super().save_model(request, obj, form, change)

    @admin.display(description='审查入口')
    def review_link(self, obj):
        if obj.status != 'pending':
            return format_html('<span style="color: #10b981; font-weight: 500;">工单已结案</span>')

        review_url = reverse('review_reported_attachment', args=[obj.attachment_id])
        return format_html(
            '<a href="{}" target="_blank" style="color: #ef4444; font-weight: bold;">点击审查附件</a>',
            review_url,
        )

    @admin.action(description='标记为违规删除')
    def mark_removed(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status='pending').update(
            status='removed',
            pending_dedup_key=None,
            handled_at=timezone.now(),
            handled_by=request.user,
        )

    @admin.action(description='标记为误报驳回')
    def mark_dismissed(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status='pending').update(
            status='dismissed',
            pending_dedup_key=None,
            handled_at=timezone.now(),
            handled_by=request.user,
        )


@admin.register(NoteReport)
class NoteReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'note', 'reporter', 'reported_user', 'reason', 'status', 'created_at', 'handled_at', 'handled_by')
    list_filter = ('status', 'created_at', 'handled_at')
    search_fields = ('note__title', 'reporter__username', 'reported_user__username', 'reason', 'detail')
    readonly_fields = ('note', 'reporter', 'reported_user', 'reason', 'detail', 'created_at', 'handled_at', 'handled_by')
    autocomplete_fields = ['note', 'reporter', 'reported_user', 'handled_by']


@admin.register(CommentReport)
class CommentReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'comment', 'note', 'reporter', 'reported_user', 'reason', 'status', 'created_at', 'handled_at', 'handled_by')
    list_filter = ('status', 'created_at', 'handled_at')
    search_fields = ('comment__content', 'note__title', 'reporter__username', 'reported_user__username', 'reason', 'detail')
    readonly_fields = ('comment', 'note', 'reporter', 'reported_user', 'reason', 'detail', 'created_at', 'handled_at', 'handled_by')
    autocomplete_fields = ['note', 'reporter', 'reported_user', 'handled_by']


@admin.register(UserSanction)
class UserSanctionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'sanction_type', 'expires_at', 'is_active', 'created_by', 'created_at')
    list_filter = ('sanction_type', 'is_active', 'created_at')
    search_fields = ('user__username', 'reason')
    readonly_fields = ('created_at', 'revoked_at')


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'report_type', 'report_id', 'action', 'moderator', 'target_user', 'created_at')
    list_filter = ('report_type', 'action', 'created_at')
    search_fields = ('moderator__username', 'target_user__username', 'note')
    readonly_fields = ('created_at',)


@admin.register(ModerationAppeal)
class ModerationAppealAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'sanction', 'status', 'created_at', 'handled_at', 'handled_by')
    list_filter = ('status', 'created_at', 'handled_at')
    search_fields = ('user__username', 'reason', 'resolution_note')
    readonly_fields = ('created_at', 'handled_at')


@admin.register(ModerationTemplate)
class ModerationTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'report_type', 'decision', 'is_active', 'updated_at')
    list_filter = ('report_type', 'decision', 'is_active')
    search_fields = ('title', 'content')
