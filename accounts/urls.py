from django.urls import path

from . import auth as auth_views
from . import captcha as captcha_views
from . import follow_views, profile_views


urlpatterns = [
    path('signup/', auth_views.SignUpView.as_view(), name='signup'),
    path('check-username/', auth_views.check_username, name='check_username'),
    path('send-email-code/', auth_views.SendEmailCodeView.as_view(), name='send_email_code'),
    path('login/', auth_views.CustomLoginView.as_view(), name='login'),
    path('forgot-password/', auth_views.forgot_password_view, name='forgot_password'),
    path('password-reset/', auth_views.password_reset_api, name='password_reset_api'),
    path('reset-password/<int:user_id>/<str:token>/', auth_views.reset_password_view, name='reset_password'),
    path('check-email/', auth_views.check_email, name='check_email'),
    path('api/login/', auth_views.login_api, name='login_api'),
    path('api/2fa/verify/', auth_views.verify_2fa_login, name='verify_2fa_login'),
    path('api/2fa/resend-email/', auth_views.resend_2fa_email, name='resend_2fa_email'),
    path('api/security/send-operation-2fa/', auth_views.send_operation_2fa_code, name='send_operation_2fa_code'),
    path('api/security/change-password/', auth_views.change_password, name='change_password'),
    path('api/security/enable-2fa/', auth_views.enable_2fa, name='enable_2fa'),
    path('api/security/verify-2fa-setup/', auth_views.verify_2fa_setup, name='verify_2fa_setup'),
    path('api/security/disable-2fa/', auth_views.disable_2fa, name='disable_2fa'),
    path(
        'api/security/regenerate-backup-codes/',
        auth_views.regenerate_backup_codes,
        name='regenerate_backup_codes',
    ),
    path('api/turnstile/config/', captcha_views.turnstile_config, name='turnstile_config'),
    path('api/captcha/init/', captcha_views.captcha_init, name='captcha_init'),
    path('api/captcha/', captcha_views.captcha_generate, name='captcha_generate'),
    path('settings/', profile_views.settings_view, name='settings'),
    path('upload-avatar/', profile_views.upload_avatar, name='upload_avatar'),
    path('update-profile/', profile_views.update_profile, name='update_profile'),
    path('update-email/', profile_views.update_email, name='update_email'),
    path('api/toggle-like/', profile_views.toggle_profile_like, name='toggle_profile_like'),
    path('api/security/devices/', profile_views.security_devices_api, name='security_devices_api'),
    path(
        'api/security/devices/<int:device_id>/revoke/',
        profile_views.revoke_security_device_api,
        name='revoke_security_device_api',
    ),
    path('api/notification-preferences/', profile_views.notification_preferences, name='notification_preferences'),
    path('api/theme-settings/', profile_views.theme_settings, name='theme_settings'),
    path('user/<int:user_id>/', profile_views.user_public_profile_view, name='user_public_profile'),
    path('api/users/follow/', follow_views.follow_user_api, name='follow_user_api'),
    path('api/users/unfollow/', follow_views.unfollow_user_api, name='unfollow_user_api'),
    path('api/users/<int:user_id>/follow-status/', follow_views.follow_status_api, name='follow_status_api'),
]
