from django.contrib import admin
from django.contrib.admin.models import LogEntry


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('action_time', 'user', 'content_type', 'object_repr', 'action_flag_display', 'change_message')
    list_filter = ('action_flag', 'action_time', 'content_type')
    search_fields = ('object_repr', 'change_message', 'user__username')
    readonly_fields = ('action_time', 'user', 'content_type', 'object_id', 'object_repr', 'action_flag', 'change_message')
    ordering = ('-action_time',)

    def action_flag_display(self, obj):
        flags = {1: '鏂板', 2: '淇敼', 3: '鍒犻櫎'}
        return flags.get(obj.action_flag, '鏈煡')
    action_flag_display.short_description = '鎿嶄綔绫诲瀷'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
