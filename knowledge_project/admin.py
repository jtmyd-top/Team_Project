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
from .models import Note, Asset, Profile, Tag, LoginDevice, LoginNotification, AccessLog, TrustedDevice, MessageAttachment
from django_ckeditor_5.widgets import CKEditor5Widget
from django import forms
from django.contrib import messages
from django.contrib.admin.models import LogEntry

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
    list_display = ('title', 'author', 'is_public', 'is_secret', 'display_public_link', 'created_at')
    list_filter = ('is_public', 'is_secret', 'author')
    search_fields = ('title', 'author__username', 'content')
    autocomplete_fields = ['author']
    readonly_fields = ('public_id',)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.is_secret:
            readonly.extend(['title', 'content', 'is_secret'])
        return readonly

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
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


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        'original_name',
        'attachment_status',
        'attachment_type',
        'uploader',
        'message',
        'size',
        'created_at',
    )
    list_filter = ('attachment_type', 'created_at')
    search_fields = ('original_name', 'uploader__username', 'message__content')
    readonly_fields = ('attachment_status', 'created_at')

    @admin.display(description='附件状态')
    def attachment_status(self, obj):
        if not obj.file:
            return format_html('<span style="color: #6b7280; font-weight: 500;">无附件文件</span>')

        if obj.reports.filter(status='pending').exists():
            review_url = reverse('review_reported_attachment', args=[obj.id])
            return format_html(
                '<a href="{}" target="_blank" style="color: #ef4444; font-weight: bold;">收到举报 (点击审查)</a>',
                review_url
            )

        return format_html(
            '<span style="color: #10b981; font-weight: 500;">🔒 隐私保护 (已锁定)</span>'
        )


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

# ---------------------------------
#  安全日志管理
# ---------------------------------

@admin.register(LoginDevice)
class LoginDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_info', 'ip_address', 'ip_location', 'login_count', 'last_login_at', 'is_trusted', 'vault_fail_count_display')
    list_filter = ('is_trusted', 'last_login_at')
    search_fields = ('user__username', 'ip_address', 'ip_location', 'device_info')
    readonly_fields = ('user', 'device_fingerprint', 'ip_address', 'ip_location', 'user_agent', 'device_info', 'first_login_at', 'last_login_at', 'login_count', 'trusted_at')
    ordering = ('-last_login_at',)
    actions = ['ban_ip_action']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def vault_fail_count_display(self, obj):
        from django.core.cache import cache
        import time

        # 直接读取缓存
        fail_key = f'vault_fail:{obj.user.id}'
        lock_key = f'vault_lock:{obj.user.id}'

        fail_count = cache.get(fail_key, 0)
        lock_expire_time = cache.get(lock_key)

        is_locked = False
        if lock_expire_time:
            remaining = lock_expire_time - int(time.time())
            is_locked = remaining > 0

        if is_locked:
            return format_html('<span style="color: red; font-weight: bold;">🔒 已锁定 ({}次)</span>', fail_count)
        elif fail_count > 0:
            return format_html('<span style="color: orange; font-weight: bold;">⚠️ {}次失败</span>', fail_count)
        return format_html('<span style="color: green;">✓ 正常</span>')
    vault_fail_count_display.short_description = '保密柜状态'

    @admin.action(description='封禁选中设备的IP地址')
    def ban_ip_action(self, request, queryset):
        from django.core.cache import cache
        from django.utils import timezone

        banned_count = 0
        for device in queryset:
            cache_key = f'banned_ip:{device.ip_address}'
            cache.set(cache_key, {
                'banned_by': request.user.username,
                'banned_at': timezone.now().isoformat(),
                'reason': f'Admin封禁 - 设备: {device.device_info}',
            }, timeout=None)
            banned_count += 1

        self.message_user(request, f'成功封禁 {banned_count} 个IP地址', messages.SUCCESS)

@admin.register(LoginNotification)
class LoginNotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'reason', 'ip_address', 'sent_at', 'email_sent')
    list_filter = ('reason', 'email_sent', 'sent_at')
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('user', 'device', 'ip_address', 'reason', 'sent_at', 'email_sent')
    ordering = ('-sent_at',)

    def has_add_permission(self, request):
        return False

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

@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    """安全访问日志管理 - 所有字段只读"""
    list_display = ('user_identifier', 'ip_address', 'action', 'count', 'created_at', 'updated_at', 'user_status_display')
    list_filter = ('action', 'created_at')
    search_fields = ('user_identifier', 'ip_address', 'details')
    readonly_fields = ('user_identifier', 'ip_address', 'action', 'count', 'details', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    actions = ['ban_user_action', 'unban_user_action', 'ban_ip_action']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def user_status_display(self, obj):
        """显示用户封禁状态"""
        from django.core.cache import cache
        from django.contrib.auth.models import User as AuthUser
        import time

        # 检查用户级锁定
        try:
            user = AuthUser.objects.filter(username=obj.user_identifier).first()
            if user:
                user_lock_key = f'vault_user_lock:{user.id}'
                lock_expire = cache.get(user_lock_key)
                if lock_expire and lock_expire > int(time.time()):
                    remaining = (lock_expire - int(time.time())) // 60
                    return format_html('<span style="color: red;">🔒 已冻结 ({}分钟)</span>', remaining)
        except:
            pass

        # 检查 IP 封禁
        ban_key = f'banned_ip:{obj.ip_address}'
        if cache.get(ban_key):
            return format_html('<span style="color: orange;">🚫 IP已封禁</span>')

        return format_html('<span style="color: green;">✓ 正常</span>')
    user_status_display.short_description = '状态'

    @admin.action(description='🔒 冻结选中用户的账户 (24小时)')
    def ban_user_action(self, request, queryset):
        """冻结用户账户24小时"""
        from django.core.cache import cache
        from django.contrib.auth.models import User as AuthUser
        import time

        banned_count = 0
        for log in queryset:
            try:
                user = AuthUser.objects.filter(username=log.user_identifier).first()
                if user:
                    user_lock_key = f'vault_user_lock:{user.id}'
                    lock_expire_time = int(time.time()) + 86400  # 24小时
                    cache.set(user_lock_key, lock_expire_time, timeout=86400)
                    banned_count += 1

                    # 记录操作日志
                    AccessLog.objects.create(
                        user_identifier=log.user_identifier,
                        ip_address=log.ip_address,
                        action='device_revoked',
                        details=f'管理员 {request.user.username} 手动冻结账户 24小时'
                    )
            except Exception as e:
                self.message_user(request, f'冻结用户 {log.user_identifier} 失败: {e}', messages.ERROR)

        if banned_count > 0:
            self.message_user(request, f'成功冻结 {banned_count} 个用户账户 (24小时)', messages.SUCCESS)

    @admin.action(description='🔓 解除选中用户的账户冻结')
    def unban_user_action(self, request, queryset):
        """解除用户账户冻结"""
        from django.core.cache import cache
        from django.contrib.auth.models import User as AuthUser

        unbanned_count = 0
        for log in queryset:
            try:
                user = AuthUser.objects.filter(username=log.user_identifier).first()
                if user:
                    # 清除用户级锁定
                    cache.delete(f'vault_user_lock:{user.id}')
                    cache.delete(f'vault_user_fail:{user.id}')
                    unbanned_count += 1
            except Exception as e:
                self.message_user(request, f'解除用户 {log.user_identifier} 冻结失败: {e}', messages.ERROR)

        if unbanned_count > 0:
            self.message_user(request, f'成功解除 {unbanned_count} 个用户的账户冻结', messages.SUCCESS)

    @admin.action(description='🚫 封禁选中记录的 IP 地址')
    def ban_ip_action(self, request, queryset):
        """封禁 IP 地址"""
        from django.core.cache import cache
        from django.utils import timezone

        banned_count = 0
        banned_ips = set()
        for log in queryset:
            ip = log.ip_address
            if ip not in banned_ips:
                cache_key = f'banned_ip:{ip}'
                cache.set(cache_key, {
                    'banned_by': request.user.username,
                    'banned_at': timezone.now().isoformat(),
                    'reason': f'Admin封禁 - 来源用户: {log.user_identifier}',
                }, timeout=None)  # 永久封禁
                banned_ips.add(ip)
                banned_count += 1

                # 记录操作日志
                AccessLog.objects.create(
                    user_identifier=log.user_identifier,
                    ip_address=ip,
                    action='ip_banned',
                    details=f'管理员 {request.user.username} 手动封禁 IP'
                )

        self.message_user(request, f'成功封禁 {banned_count} 个 IP 地址', messages.SUCCESS)


@admin.register(TrustedDevice)
class TrustedDeviceAdmin(admin.ModelAdmin):
    """信任设备管理"""
    list_display = ('user', 'device_info_display', 'ip_address', 'fail_count_display', 'status_display', 'expires_at', 'last_used_at')
    list_filter = ('is_revoked', 'expires_at', 'created_at')
    search_fields = ('user__username', 'user_agent', 'ip_address', 'device_token')
    readonly_fields = ('user', 'device_token', 'user_agent', 'ip_address', 'last_login_ip', 'created_at', 'last_used_at', 'expires_at', 'fail_count', 'is_revoked', 'revoked_reason')
    ordering = ('-last_used_at',)
    actions = ['revoke_devices']

    def has_add_permission(self, request):
        return False

    def device_info_display(self, obj):
        """截取UA显示前50字符"""
        ua = obj.user_agent or ''
        if len(ua) > 50:
            return ua[:50] + '...'
        return ua
    device_info_display.short_description = '设备信息'

    def fail_count_display(self, obj):
        """失败计数显示，带颜色警告"""
        if obj.fail_count >= 3:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ {}次 (已撤销)</span>', obj.fail_count)
        elif obj.fail_count > 0:
            return format_html('<span style="color: orange;">{}次</span>', obj.fail_count)
        return format_html('<span style="color: green;">0次</span>')
    fail_count_display.short_description = '失败次数'

    def status_display(self, obj):
        """设备状态显示"""
        if obj.is_revoked:
            return format_html('<span style="color: red;">❌ 已撤销</span>')
        elif not obj.is_valid():
            return format_html('<span style="color: gray;">⏰ 已过期</span>')
        return format_html('<span style="color: green;">✓ 有效</span>')
    status_display.short_description = '状态'

    @admin.action(description='撤销选中设备的信任')
    def revoke_devices(self, request, queryset):
        """批量撤销信任设备"""
        revoked_count = 0
        for device in queryset.filter(is_revoked=False):
            device.is_revoked = True
            device.revoked_reason = f'管理员手动撤销 by {request.user.username}'
            device.save(update_fields=['is_revoked', 'revoked_reason'])
            revoked_count += 1
        self.message_user(request, f'成功撤销 {revoked_count} 个设备的信任', messages.SUCCESS)


# ---------------------------------
#  私信 / 会话设置 / 举报
# ---------------------------------
from .models import (
    Message, MessagePreference, UserBlocklist,
    ConversationSettings, MessageReport, AttachmentReport,
    NoteReport, CommentReport, MessageGroupPolicy, MessageGroup, MessageGroupMember,
    MessageGroupInviteLink, MessageGroupInviteUse, MessageGroupAnnouncementHistory,
    MessageGroupBan, MessageGroupAuditLog, GroupMessage,
)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'recipient', 'short_content', 'is_read',
                    'is_recalled', 'deleted_for_sender', 'deleted_for_recipient', 'created_at')
    list_filter = ('is_read', 'is_recalled', 'created_at')
    search_fields = ('sender__username', 'recipient__username', 'content', 'searchable_text')
    readonly_fields = ('created_at', 'read_at', 'recalled_at')

    def short_content(self, obj):
        return (obj.content or '')[:40]
    short_content.short_description = '内容'


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
    list_display = ('id', 'name', 'owner', 'mute_mode', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'mute_mode', 'created_at')
    search_fields = ('name', 'description', 'announcement', 'owner__username')
    autocomplete_fields = ['owner', 'created_by']
    inlines = [MessageGroupMemberInline]


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
    autocomplete_fields = ['group', 'editor']
    readonly_fields = ('created_at',)


@admin.register(GroupMessage)
class GroupMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'sender', 'short_content', 'is_recalled', 'was_reported', 'created_at')
    list_filter = ('is_recalled', 'was_reported', 'created_at')
    search_fields = ('group__name', 'sender__username', 'content', 'searchable_text')
    readonly_fields = ('created_at', 'recalled_at')

    def short_content(self, obj):
        return (obj.content or '')[:40]
    short_content.short_description = '内容'


@admin.register(ConversationSettings)
class ConversationSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'peer', 'is_pinned', 'is_muted', 'is_archived',
                    'disappearing_enabled', 'force_unread', 'updated_at')
    list_filter = ('is_pinned', 'is_muted', 'is_archived', 'disappearing_enabled')
    search_fields = ('user__username', 'peer__username')


@admin.register(MessageReport)
class MessageReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'reporter', 'reported_user', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('reporter__username', 'reported_user__username', 'detail')
    readonly_fields = ('reporter', 'reported_user', 'message', 'reason', 'detail', 'created_at')
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
            return format_html('<span style="color: #10b981; font-weight: 500;">🔒 工单已结案</span>')

        review_url = reverse('review_reported_attachment', args=[obj.attachment_id])
        return format_html(
            '<a href="{}" target="_blank" style="color: #ef4444; font-weight: bold;">点击审查附件</a>',
            review_url
        )

    @admin.action(description='标记为已违规删除')
    def mark_removed(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status='pending').update(
            status='removed',
            pending_dedup_key=None,
            handled_at=timezone.now(),
            handled_by=request.user,
        )

    @admin.action(description='标记为已驳回误报')
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


@admin.register(CommentReport)
class CommentReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'comment', 'note', 'reporter', 'reported_user', 'reason', 'status', 'created_at', 'handled_at', 'handled_by')
    list_filter = ('status', 'created_at', 'handled_at')
    search_fields = ('comment__content', 'note__title', 'reporter__username', 'reported_user__username', 'reason', 'detail')
    readonly_fields = ('comment', 'note', 'reporter', 'reported_user', 'reason', 'detail', 'created_at', 'handled_at', 'handled_by')


@admin.register(MessagePreference)
class MessagePreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'allow_messages', 'message_mode',
                    'show_read_status', 'auto_reply_enabled', 'updated_at')
    list_filter = ('allow_messages', 'message_mode')
    search_fields = ('user__username',)


@admin.register(UserBlocklist)
class UserBlocklistAdmin(admin.ModelAdmin):
    list_display = ('user', 'blocked_user', 'reason', 'created_at')
    search_fields = ('user__username', 'blocked_user__username')


# ---------------------------------
#  举报处置（制裁 / 处置日志）
# ---------------------------------
from .models import ModerationAppeal, ModerationLog, ModerationTemplate, UserNotification, UserSanction


@admin.register(UserSanction)
class UserSanctionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'sanction_type', 'expires_at', 'is_active',
                    'created_by', 'created_at')
    list_filter = ('sanction_type', 'is_active', 'created_at')
    search_fields = ('user__username', 'reason')
    readonly_fields = ('created_at', 'revoked_at')


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'report_type', 'report_id', 'action', 'moderator',
                    'target_user', 'created_at')
    list_filter = ('report_type', 'action', 'created_at')
    search_fields = ('moderator__username', 'target_user__username', 'note')
    readonly_fields = ('created_at',)


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'kind', 'title', 'is_read', 'created_at')
    list_filter = ('kind', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'body')
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
