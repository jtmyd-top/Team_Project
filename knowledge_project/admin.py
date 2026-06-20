# knowledge_project/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
# 【修改点】从 models.py 导入更新后的模型，移除了 Project 和 ProjectMembership
from .models import Profile
from django.contrib.admin.models import LogEntry

# ---------------------------------
#  Inlines (内联模型)
# ---------------------------------

# 辅助函数，保持不变
class ProfileInline(admin.StackedInline):
    """在用户页面内联显示Profile信息"""
    model = Profile
    can_delete = False
    verbose_name_plural = '用户资料'
    readonly_fields = ('activation_code', 'code_created_at')

# 【已移除】NoteInline 和 AssetInline，因为它们是用于 ProjectAdmin 的，而 ProjectAdmin 已被删除。

# 【已移除】ProjectMembershipInline，因为它依赖于已删除的 ProjectMembership 模型。

# ---------------------------------
#  ModelAdmins (??????)
# ---------------------------------

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'activation_code', 'code_created_at')
    search_fields = ('user__username',)
    readonly_fields = ('user', 'activation_code', 'code_created_at')

# ---------------------------------
#  Custom User Admin (自定义用户后台)
# ---------------------------------

# 【已移除】ProjectMembershipInlineForUser，因为它依赖已删除的模型

class CustomUserAdmin(BaseUserAdmin):
    """自定义的用户后台，现在只集成了Profile"""
    # 【修改点】移除了 ProjectMembershipInlineForUser
    inlines = (ProfileInline,)

# 先取消注册默认的User admin
admin.site.unregister(User)
# 再注册我们自定义的增强版User admin
admin.site.register(User, CustomUserAdmin)

# ---------------------------------
#  安全日志管理
# ---------------------------------

@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('action_time', 'user', 'content_type', 'object_repr', 'action_flag_display', 'change_message')
    list_filter = ('action_flag', 'action_time', 'content_type')
    search_fields = ('object_repr', 'change_message', 'user__username')
    readonly_fields = ('action_time', 'user', 'content_type', 'object_id', 'object_repr', 'action_flag', 'change_message')
    ordering = ('-action_time',)

    def action_flag_display(self, obj):
        flags = {1: '新增', 2: '修改', 3: '删除'}
        return flags.get(obj.action_flag, '未知')
    action_flag_display.short_description = '操作类型'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ---------------------------------
#  安全审计日志管理
# ---------------------------------

# ---------------------------------
#  私信 / 会话设置 / 举报
# ---------------------------------
