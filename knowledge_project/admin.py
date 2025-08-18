# knowledge_project/admin.py
import hashlib
import os

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html
from django.db import models
from django_json_widget.widgets import JSONEditorWidget
# 【修改点】从 models.py 导入更新后的模型
from .models import Project, ProjectMembership, Note, Asset, Profile
from django_ckeditor_5.widgets import CKEditor5Widget
from django import forms
from django.contrib import messages
# ---------------------------------
#  Inlines (内联模型)
# ---------------------------------
# 辅助函数，可以放在文件顶部
def calculate_file_hash_for_admin(file):
    """一个独立的、用于Admin的哈希计算函数，能处理多种上传文件类型"""
    hasher = hashlib.sha256()
    # 使用 file.chunks() 可以安全地处理内存中的文件和磁盘上的大文件
    for chunk in file.chunks():
        hasher.update(chunk)
    # 计算完毕后，将文件指针移回开头，以便Django可以正常保存它
    file.seek(0)
    return hasher.hexdigest()
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

class NoteAdminForm(forms.ModelForm):
    # 【核心】在这里，我们强制 content 字段使用 CKEditor5Widget
    # 并指定使用我们之前在 settings.py 中定义的 'full' 配置
    content = forms.CharField(
        label="笔记内容",
        widget=CKEditor5Widget(config_name='full'),
        required=False  # 根据你的模型字段设置，如果允许为空则设为False
    )

    class Meta:
        model = Note
        fields = '__all__'
        # 如果你的 Note 模型中有 JSONField，并且仍想使用 JSONEditorWidget，
        # 请在这里配置，这是比 formfield_overrides 更好的方式。
        # 例如，如果你的JSON字段名叫 'extra_data':
        # widgets = {
        #     'extra_data': JSONEditorWidget,
        # }


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    # 【新增】告诉 Admin 使用我们自定义的表单
    form = NoteAdminForm

    list_display = ('title', 'author', 'project', 'is_public', 'display_public_link', 'created_at')
    list_filter = ('is_public', 'project', 'author')
    search_fields = ('title', 'project__title', 'author__username', 'content')
    autocomplete_fields = ['project', 'author']
    readonly_fields = ('public_id',)

    # 【删除】删除这行，它的功能已经被我们移到 NoteAdminForm 的 Meta.widgets 中了
    # formfield_overrides = {
    #     models.JSONField: {'widget': JSONEditorWidget},
    # }

    def save_model(self, request, obj, form, change):
        if not change:
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

    # 【基础只读字段】将 image_hash 加入，方便在修改页面查看
    readonly_fields = ('uploaded_at', 'image_hash')

    def get_fields(self, request, obj=None):
        """
        【保留】动态控制表单显示的字段。
        - 在“增加”页面 (obj is None)，不显示 'name' 和 'image_hash'。
        - 在“修改”页面 (obj is not None)，显示所有相关字段。
        """
        if obj is None:
            # “增加”页面的字段顺序
            return ('project', 'uploader', 'file', 'asset_type', 'description')
        else:
            # “修改”页面的字段顺序
            return ('name', 'project', 'uploader', 'file', 'asset_type', 'description', 'uploaded_at', 'image_hash')

    def get_readonly_fields(self, request, obj=None):
        """
        【保留并完善】动态设置只读字段。
        - 基础只读字段是 ('uploaded_at', 'image_hash')。
        - 在“修改”页面，额外将 'name' 字段也设为只读。
        """
        # 从类属性获取基础的只读字段列表
        base_readonly = list(self.readonly_fields)
        if obj:  # 如果是“修改”页面
            # 将 'name' 添加到只读列表中
            base_readonly.append('name')
        return tuple(base_readonly)

    def save_model(self, request, obj, form, change):
        """
        【全新重构】的保存逻辑，集成了哈希计算和用户级去重。
        """
        # 1. 自动设置上传者 (如果为空)
        if not obj.uploader_id:
            obj.uploader = request.user

        # 2. 检查是否有新文件上传或文件被更改
        uploaded_file = form.cleaned_data.get('file')
        if uploaded_file and 'file' in form.changed_data:
            # a. 计算新文件的哈希值
            file_hash = calculate_file_hash_for_admin(uploaded_file)

            # b. 检查当前用户是否已上传过相同内容的文件 (排除当前对象自身)
            existing_asset = Asset.objects.filter(
                uploader=obj.uploader,
                image_hash=file_hash
            ).exclude(pk=obj.pk).first()

            if existing_asset:
                # c. 如果找到重复项，则不保存，并给出明确的错误提示
                obj.pk = None  # 阻止保存当前对象，防止创建不完整的记录
                existing_asset_url = reverse(
                    'admin:knowledge_project_asset_change',
                    args=[existing_asset.pk]
                )
                messages.set_level(request, messages.ERROR)
                messages.error(
                    request,
                    format_html(
                        '上传失败：您已上传过相同内容的文件。请访问 <a href="{}">这里</a> 查看已存在的资产。',
                        existing_asset_url
                    )
                )
                return  # 中断保存流程

            # d. 如果是新文件，将计算出的哈希值赋给当前对象
            obj.image_hash = file_hash

        # 3. 先执行Django默认的保存流程，这会处理文件系统中的文件写入
        super().save_model(request, obj, form, change)

        # 4. 如果 name 字段为空，则使用文件名自动填充
        # 这个操作必须在 super().save_model 之后，因为那时 obj.file.name 才会有值
        if not obj.name and obj.file:
            obj.name = os.path.basename(obj.file.name)
            obj.save(update_fields=['name'])  # 只更新name字段，避免触发循环保存


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