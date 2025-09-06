# knowledge_project/admin.py
import hashlib
import os
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html
from django.db import models
# 【修改点】从 models.py 导入更新后的模型，移除了 Project 和 ProjectMembership
from .models import Note, Asset, Profile, Tag
from django_ckeditor_5.widgets import CKEditor5Widget
from django import forms
from django.contrib import messages

# ---------------------------------
#  Inlines (内联模型)
# ---------------------------------

# 辅助函数，保持不变
def calculate_file_hash_for_admin(file):
    hasher = hashlib.sha256()
    for chunk in file.chunks():
        hasher.update(chunk)
    file.seek(0)
    return hasher.hexdigest()

class ProfileInline(admin.StackedInline):
    """在用户页面内联显示Profile信息"""
    model = Profile
    can_delete = False
    verbose_name_plural = '用户资料'
    readonly_fields = ('activation_code', 'code_created_at')

# 【已移除】NoteInline 和 AssetInline，因为它们是用于 ProjectAdmin 的，而 ProjectAdmin 已被删除。

# 【已移除】ProjectMembershipInline，因为它依赖于已删除的 ProjectMembership 模型。

# ---------------------------------
#  ModelAdmins (模型后台管理)
# ---------------------------------

# 【已移除】ProjectAdmin，因为它管理的 Project 模型已被删除。

# 【已移除】ProjectMembershipAdmin，因为它管理的 ProjectMembership 模型已被删除。

class NoteAdminForm(forms.ModelForm):
    content = forms.CharField(
        label="笔记内容",
        widget=CKEditor5Widget(config_name='full'),
        required=False
    )
    class Meta:
        model = Note
        fields = '__all__'

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    form = NoteAdminForm
    # 【修改点】移除了 'project' 字段
    list_display = ('title', 'author', 'is_public', 'display_public_link', 'created_at')
    # 【修改点】移除了 'project' 过滤器
    list_filter = ('is_public', 'author')
    # 【修改点】移除了 'project__title' 搜索字段
    search_fields = ('title', 'author__username', 'content')
    # 【修改点】移除了 'project' 自动完成字段
    autocomplete_fields = ['author']
    readonly_fields = ('public_id',)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        # 【新增】更新时，记录最后修改者
        else:
            obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='公开链接')
    def display_public_link(self, obj):
        if obj.is_public:
            try:
                url = reverse('public_note_view', args=[obj.public_id])
                return format_html('<a href="{}" target="_blank">点击查看</a>', url)
            except Exception:
                return "链接 (URL未配置)"
        return "未公开"

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    # 【修改点】移除了 'project' 字段
    list_display = ('name', 'asset_type', 'uploader', 'uploaded_at')
    # 【修改点】移除了 'project' 过滤器，可以按上传者过滤
    list_filter = ('asset_type', 'uploader')
    # 【修改点】移除了 'project__title' 搜索字段
    search_fields = ('name', 'uploader__username')
    # 【修改点】移除了 'project' 自动完成字段
    autocomplete_fields = ['uploader']
    readonly_fields = ('uploaded_at', 'image_hash')

    def get_fields(self, request, obj=None):
        """【修改点】移除了 'project' 字段"""
        if obj is None:
            # “增加”页面的字段顺序
            return ('uploader', 'file', 'asset_type', 'description')
        else:
            # “修改”页面的字段顺序
            return ('name', 'uploader', 'file', 'asset_type', 'description', 'uploaded_at', 'image_hash')

    def get_readonly_fields(self, request, obj=None):
        base_readonly = list(self.readonly_fields)
        if obj:
            base_readonly.append('name')
        return tuple(base_readonly)

    def save_model(self, request, obj, form, change):
        if not obj.uploader_id:
            obj.uploader = request.user

        uploaded_file = form.cleaned_data.get('file')
        if uploaded_file and 'file' in form.changed_data:
            file_hash = calculate_file_hash_for_admin(uploaded_file)
            existing_asset = Asset.objects.filter(
                uploader=obj.uploader,
                image_hash=file_hash
            ).exclude(pk=obj.pk).first()

            if existing_asset:
                obj.pk = None
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
                return
            obj.image_hash = file_hash

        super().save_model(request, obj, form, change)

        if not obj.name and obj.file:
            obj.name = os.path.basename(obj.file.name)
            obj.save(update_fields=['name'])

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'activation_code', 'code_created_at')
    search_fields = ('user__username',)
    readonly_fields = ('user', 'activation_code', 'code_created_at')

# 【新增】为 Tag 模型注册一个简单的管理界面
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

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