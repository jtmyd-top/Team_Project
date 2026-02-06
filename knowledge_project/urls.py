# knowledge_project/urls.py
from django.urls import path,re_path
from . import views
from . import folder_views

urlpatterns = [
    path('', views.home_view, name='home'),
    #path('public-notes/', views.public_notes_list_view, name='public_notes_list'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('knowledge/', views.knowledge_list, name='knowledge_list'),
    # 【任务二】新增：为实时用户名检查提供API端点
    path('check-username/', views.check_username, name='check_username'),
    path('send-email-code/', views.SendEmailCodeView.as_view(), name='send_email_code'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('password-reset/', views.password_reset_api, name='password_reset_api'),
    path('reset-password/<int:user_id>/<str:token>/', views.reset_password_view, name='reset_password'),
    path('api/notes/search/', views.search_notes_api, name='api_search_notes'),
    path('api/notes/<int:note_id>/', views.note_detail_api, name='api_note_detail'),
    path('api/notes/all/', views.get_all_notes_api, name='get_all_notes_api'),
    path('api/notes/create/', views.create_note_api, name='create_note_api'),
    path('api/notes/<int:note_id>/update/', views.update_note_api, name='update_note_api'),
    path('api/notes/<int:note_id>/delete/', views.delete_note_api, name='delete_note_api'),
    path('api/notes/<int:note_id>/toggle-secret/', views.toggle_secret_api, name='toggle_secret_api'),
    path('notes/public/<uuid:public_id>/', views.public_note_view, name='public_note_view'),
    # --- 【新增】CKEditor 5 图片上传的 API 路由 ---
    path('api/upload/ckeditor_image/', views.ckeditor_image_upload_view, name='ckeditor_image_upload_view'),
    # --- 【新增】图片上传的 API 路由 ---
    path('api/upload/image/', views.image_upload_view, name='image_upload_view'),
    re_path(r'^protected_uploads/(?P<file_path>.*)$', views.protected_media_view, name='protected_media_view'),
    path('api/public-notes/', views.public_notes_api, name='public_notes_api'),
    path("settings/", views.settings_view, name="settings"),
    path("upload-avatar/", views.upload_avatar, name="upload_avatar"),
    path("update-profile/", views.update_profile, name="update_profile"),
    path("update-email/", views.update_email, name="update_email"),
    path('check-email/', views.check_email, name='check_email'),
    path('api/toggle-like/', views.toggle_profile_like, name='toggle_profile_like'),
    path('api/toggle-note-like/', views.toggle_note_like, name='toggle_note_like'),

    # ==================== 账户安全相关 API ====================
    path('api/security/send-operation-2fa/', views.send_operation_2fa_code, name='send_operation_2fa_code'),
    path('api/security/change-password/', views.change_password, name='change_password'),
    path('api/security/enable-2fa/', views.enable_2fa, name='enable_2fa'),
    path('api/security/verify-2fa-setup/', views.verify_2fa_setup, name='verify_2fa_setup'),
    path('api/security/disable-2fa/', views.disable_2fa, name='disable_2fa'),
    path('api/security/regenerate-backup-codes/', views.regenerate_backup_codes, name='regenerate_backup_codes'),

    # ==================== 通知偏好设置 API ====================
    path('api/notification-preferences/', views.notification_preferences, name='notification_preferences'),

    # ==================== 主题设置 API ====================
    path('api/theme-settings/', views.theme_settings, name='theme_settings'),

    # ==================== Turnstile API ====================
    path('api/turnstile/config/', views.turnstile_config, name='turnstile_config'),

    # ==================== 图形验证码 API ====================
    path('api/captcha/init/', views.captcha_init, name='captcha_init'),
    path('api/captcha/', views.captcha_generate, name='captcha_generate'),

    # ==================== 登录API ====================
    path('api/login/', views.login_api, name='login_api'),

    # ==================== 2FA登录验证 API ====================
    path('api/2fa/verify/', views.verify_2fa_login, name='verify_2fa_login'),
    path('api/2fa/resend-email/', views.resend_2fa_email, name='resend_2fa_email'),

    # ==================== 文件夹相关 API ====================
    path('api/folders/', folder_views.folder_list_api, name='folder_list_api'),
    path('api/folders/<int:folder_id>/', folder_views.folder_detail_api, name='folder_detail_api'),
    path('api/folders/<int:folder_id>/notes/', folder_views.folder_notes_api, name='folder_notes_api'),
    path('api/folders/<int:folder_id>/breadcrumb/', folder_views.folder_breadcrumb_api, name='folder_breadcrumb_api'),
    path('api/folders/inbox/notes/', folder_views.inbox_notes_api, name='inbox_notes_api'),
    
    # ==================== 笔记管理 API（增强版）====================
    path('api/notes/flat/', folder_views.all_notes_flat_api, name='all_notes_flat_api'),
    path('api/notes/favorited/', folder_views.favorited_notes_api, name='favorited_notes_api'),
    path('api/notes/trashed/', folder_views.trashed_notes_api, name='trashed_notes_api'),
    path('api/notes/<int:note_id>/move/', folder_views.move_note_api, name='move_note_api'),
    path('api/notes/<int:note_id>/favorite/', folder_views.toggle_note_favorite_api, name='toggle_note_favorite_api'),
    path('api/notes/<int:note_id>/trash/', folder_views.trash_note_api, name='trash_note_api'),
    path('api/notes/<int:note_id>/restore/', folder_views.restore_note_api, name='restore_note_api'),
    path('api/notes/<int:note_id>/permanent-delete/', folder_views.permanent_delete_note_api, name='permanent_delete_note_api'),

    # ==================== 回收站（文件夹）API ====================
    path('api/folders/trashed-items/', folder_views.trashed_items_api, name='trashed_items_api'),
    path('api/folders/trashed/<int:folder_id>/contents/', folder_views.trashed_folder_contents_api, name='trashed_folder_contents_api'),
    path('api/folders/<int:folder_id>/restore/', folder_views.restore_folder_api, name='restore_folder_api'),
    path('api/folders/<int:folder_id>/permanent-delete/', folder_views.permanent_delete_folder_api, name='permanent_delete_folder_api'),

    # ==================== 保密柜（Vault）API ====================
    path('api/vault/status/', views.vault_status, name='vault_status'),
    path('api/vault/init/', views.vault_init, name='vault_init'),
    path('api/vault/verify/', views.vault_verify, name='vault_verify'),
    path('api/vault/key/', views.vault_get_key, name='vault_get_key'),
    path('api/vault/export/', views.vault_export, name='vault_export'),
    path('api/vault/lock/', views.vault_lock, name='vault_lock'),
    path('api/vault/lock-status/', views.vault_lock_status, name='vault_lock_status'),
    path('api/vault/send-email-code/', views.vault_send_email_code, name='vault_send_email_code'),
    path('api/vault/notes/', views.vault_notes_list, name='vault_notes_list'),

    # ==================== 战情室 Dashboard ====================
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('api/dashboard/stats/', views.dashboard_stats_api, name='dashboard_stats_api'),
    path('api/ban_ip/', views.ban_ip_api, name='ban_ip_api'),

    #path("logout/", views.logout_view, name="logout"),
]
