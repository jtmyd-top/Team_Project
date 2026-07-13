from django.contrib import admin

from .models import BrowserPushSubscription, UserNotification


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'kind', 'title', 'is_read', 'created_at')
    list_filter = ('kind', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'body')
    readonly_fields = ('created_at',)


@admin.register(BrowserPushSubscription)
class BrowserPushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'endpoint', 'expiration_time', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__username', 'endpoint', 'user_agent')
    readonly_fields = ('created_at', 'updated_at')
