# knowledge_project/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html
from django.db import models
from django_json_widget.widgets import JSONEditorWidget
# 【修改点】从 models.py 导入更新后的模型
from .models import Project, ProjectMembership, Note, Asset, Profile

# ---------------------------------
#  Inlines (内联模型)
# ---------------------------------

class ProfileInline(admin.StackedInline):
    """在用户页面内联显示Profile信息"""
    model = Profile
    can_delete = False
    verbose_name_plural = '用户资料'
    readonly_fields = ('activation_code', 'code_created_at')

class NoteInline(admin.TabularInline):
    """在项目页面内联显示笔记，方便快速添加"""
    model = Note
    extra = 1
    # 【修改】添加 author 字段，并设为只读，因为我们会自动填充
    fields = ('title', 'author', 'created_at', 'is_public')
    readonly_fields = ('author', 'created_at',)
    show_change_link = True
    verbose_name = "知识笔记"
    verbose_name_plural = "关联的知识笔记"

    def save_model(self, request, obj, form, change):
        """【新增】在内联表单中保存时，自动设置作者"""
        if not obj.author_id:  # 只有在新建时才设置
            obj.author = request.user
        super().save_model(request, obj, form, change)

class AssetInline(admin.TabularInline):
    """在项目页面内联显示资产，方便快速上传"""
    model = Asset
    extra = 1
    fields = ('name', 'file', 'asset_type', 'uploader', 'uploaded_at')
    readonly_fields = ('uploaded_at',) # 上传者在保存时自动设置
    verbose_name = "项目资产"
    verbose_name_plural = "关联的项目资产"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # 自动将上传者设置为当前登录的管理员用户
        if db_field.name == "uploader":
            kwargs['initial'] = request.user.id
            # 将该字段设为只读，因为已经自动填充了
            kwargs['disabled'] = True 
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class ProjectMembershipInline(admin.TabularInline):
    """【新增】在项目页面内联管理项目成员"""
    model = ProjectMembership
    extra = 1
    # 推荐使用 autocomplete_fields 来搜索和选择用户，而不是下拉列表
    autocomplete_fields = ['user']
    verbose_name = "项目成员"
    verbose_name_plural = "项目成员"

# ---------------------------------
#  ModelAdmins (模型后台管理)
# ---------------------------------

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """【核心重构】项目模型的后台管理"""
    list_display = ('title', 'owner', 'status', 'is_personal_space', 'created_at')
    list_filter = ('status', 'is_personal_space')
    search_fields = ('title', 'description', 'members__username') # 可以通过成员用户名搜索项目
    ordering = ['-created_at']
    # 【修改点】将成员、笔记、资产的管理以内联方式加入
    inlines = [ProjectMembershipInline, NoteInline, AssetInline]

    @admin.display(description='所有者')
    def owner(self, obj):
        # 使用在模型中定义的 owner 属性
        project_owner = obj.owner
        if project_owner:
            # 创建一个指向用户后台编辑页的链接
            link = reverse("admin:auth_user_change", args=[project_owner.id])
            return format_html('<a href="{}">{}</a>', link, project_owner.username)
        return "N/A"

@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    """【新增】项目成员关系的独立后台管理界面"""
    list_display = ('project', 'user', 'role', 'joined_at')
    list_filter = ('role', 'project')
    search_fields = ('project__title', 'user__username')
    autocomplete_fields = ['project', 'user']


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    # 【修改】在列表页添加 author
    list_display = ('title', 'author', 'project', 'is_public', 'display_public_link', 'created_at')
    # 【修改】添加 author 作为筛选条件
    list_filter = ('is_public', 'project', 'author')
    # 【修改】添加 author__username 作为搜索字段
    search_fields = ('title', 'project__title', 'author__username', 'content')
    # 【修改】添加 author 作为自动完成字段
    autocomplete_fields = ['project', 'author']
    readonly_fields = ('public_id',)

    # 保持不变
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }

    def save_model(self, request, obj, form, change):
        """【新增】在后台创建笔记时，自动将作者设置为当前用户"""
        if not change:  # 如果是新建对象
            obj.author = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='公开链接')
    def display_public_link(self, obj):
        if obj.is_public:
            try:
                url = reverse('public_note_view', args=[obj.public_id])
                return format_html('<a href="{}" target="_blank">点击查看</a>', url)
            except:
                return "链接 (URL未配置)"
        return "未公开"


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'asset_type', 'uploader', 'uploaded_at')
    list_filter = ('asset_type', 'project')
    search_fields = ('name', 'project__title', 'uploader__username')
    autocomplete_fields = ['project', 'uploader']
    # 【修改点】将 'uploaded_at' 移到 readonly_fields 的基础设置中
    readonly_fields = ('uploaded_at',)

    def get_fields(self, request, obj=None):
        """
        【新增】动态控制表单显示的字段。
        - 在添加页面 (obj is None)，不显示 'name' 字段。
        - 在修改页面 (obj is not None)，显示 'name' 字段。
        """
        if obj is None:
            # 添加页面字段顺序
            return ('project', 'uploader', 'file', 'asset_type', 'description')
        else:
            # 修改页面字段顺序
            return ('name', 'project', 'uploader', 'file', 'asset_type', 'description', 'uploaded_at')

    def get_readonly_fields(self, request, obj=None):
        """
        【新增】动态设置只读字段。
        - 在修改页面，将 'name' 和 'uploaded_at' 设为只读。
        """
        if obj:  # 如果是修改页面
            return self.readonly_fields + ('name',)
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        """
        【新增】重写保存逻辑。
        """
        # 1. 自动设置上传者 (如果为空)
        if not obj.uploader:
            obj.uploader = request.user

        # 2. 如果 name 字段为空，则使用文件名填充
        #    注意：必须在 super().save_model 之前操作 obj，
        #    但在文件真正保存后，obj.file.name 才会有值。
        #    所以我们先调用 super().save_model 保存文件，再补充 name。

        # 先执行默认的保存，这会处理文件上传
        super().save_model(request, obj, form, change)

        # 此时 obj.file.name 已经有值了
        if not obj.name:
            # os.path.basename 可以去掉 Django 可能添加的路径前缀
            import os
            obj.name = os.path.basename(obj.file.name)
            # 再次保存以更新 name 字段
            obj.save()


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'activation_code', 'code_created_at')
    search_fields = ('user__username',)
    readonly_fields = ('user', 'activation_code', 'code_created_at')

# ---------------------------------
#  Custom User Admin (自定义用户后台)
# ---------------------------------

class ProjectMembershipInlineForUser(admin.TabularInline):
    """【新增】在用户页面内联显示他参与的项目"""
    model = ProjectMembership
    extra = 0 # 通常不在这里新增，只查看
    fields = ('project', 'role', 'joined_at')
    readonly_fields = ('project', 'role', 'joined_at')
    can_delete = False
    show_change_link = True
    verbose_name = "项目成员身份"
    verbose_name_plural = "参与的项目"


class CustomUserAdmin(BaseUserAdmin):
    """自定义的用户后台，集成了Profile和项目成员信息"""
    inlines = (ProfileInline, ProjectMembershipInlineForUser)

# 先取消注册默认的User admin
admin.site.unregister(User)
# 再注册我们自定义的增强版User admin
admin.site.register(User, CustomUserAdmin)