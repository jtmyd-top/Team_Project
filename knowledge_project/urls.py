# knowledge_project/urls.py
from . import views
from django.urls import path,re_path
from .views import  SignUpView
from .views import SignUpView, knowledge_list,captcha_image,check_username,CustomLoginView
urlpatterns = [
    path('', views.public_notes_list_view, name='home'),
    path('signup/', SignUpView.as_view(), name='signup'),
    path('knowledge/', knowledge_list, name='knowledge_list'),
    path('captcha/', captcha_image, name='captcha_image'),
    # 【任务二】新增：为实时用户名检查提供API端点
    path('check-username/', check_username, name='check_username'),
    path('send-email-code/', views.SendEmailCodeView.as_view(), name='send_email_code'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('api/notes/search/', views.search_notes_api, name='api_search_notes'),
    path('api/notes/<int:note_id>/', views.note_detail_api, name='api_note_detail'),
    path('api/notes/all/', views.get_all_notes_api, name='get_all_notes_api'),
    path('api/notes/create/', views.create_note_api, name='create_note_api'),
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

    # ==================== 账户安全相关 API ====================
    path('api/security/send-operation-2fa/', views.send_operation_2fa_code, name='send_operation_2fa_code'),
    path('api/security/change-password/', views.change_password, name='change_password'),
    path('api/security/enable-2fa/', views.enable_2fa, name='enable_2fa'),
    path('api/security/verify-2fa-setup/', views.verify_2fa_setup, name='verify_2fa_setup'),
    path('api/security/disable-2fa/', views.disable_2fa, name='disable_2fa'),
    path('api/security/regenerate-backup-codes/', views.regenerate_backup_codes, name='regenerate_backup_codes'),

    # ==================== 通知偏好设置 API ====================
    path('api/notification-preferences/', views.notification_preferences, name='notification_preferences'),

    # ==================== 2FA登录验证 API ====================
    path('api/2fa/verify/', views.verify_2fa_login, name='verify_2fa_login'),
    path('api/2fa/resend-email/', views.resend_2fa_email, name='resend_2fa_email'),

    # ==================== 测试页面 ====================
    path('test/video-audio/', views.test_video_audio, name='test_video_audio'),

    #path("logout/", views.logout_view, name="logout"),
]

