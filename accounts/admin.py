from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html

from .models import AccessLog, LoginDevice, LoginNotification, Profile, TrustedDevice


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = '鐢ㄦ埛璧勬枡'
    readonly_fields = ('activation_code', 'code_created_at')


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'activation_code', 'code_created_at')
    search_fields = ('user__username',)
    readonly_fields = ('user', 'activation_code', 'code_created_at')


class CustomUserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)


try:
    admin.site.unregister(User)
except NotRegistered:
    pass
admin.site.register(User, CustomUserAdmin)


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
