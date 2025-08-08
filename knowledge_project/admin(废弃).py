# knowledge_project/admin.py

from django.contrib import admin
from .models import Team, TeamMembership, Project, Note

# 1. 定义一个 Project 的内联类
# TabularInline 让关联的项目以紧凑的表格形式显示
class ProjectInline(admin.TabularInline):
    model = Project  # 指定要内联的模型是 Project
    extra = 1        # 默认额外显示1个空的表单，方便快速添加新项目
    fields = ('title', 'status', 'created_at') # 在内联中显示哪些字段
    readonly_fields = ('created_at',) # 创建时间只读

# 对Team模型的后台管理界面进行定制
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_personal_space', 'created_at')
    list_filter = ('is_personal_space',)
    search_fields = ('name', 'owner__username')
    # 2. 将上面定义的 ProjectInline 添加到 TeamAdmin 中
    inlines = [ProjectInline]

# ... TeamMembershipAdmin, ProjectAdmin, NoteAdmin 保持不变 ...
@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'team', 'role', 'joined_at')
    list_filter = ('role', 'team')
    search_fields = ('user__username', 'team__name')
    autocomplete_fields = ['user', 'team']

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'team', 'status', 'created_at')
    list_filter = ('status', 'team')
    search_fields = ('title', 'team__name')
    autocomplete_fields = ['team']
    ordering = ['-created_at']

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'created_at')
    search_fields = ('title', 'project__title')
    autocomplete_fields = ['project']