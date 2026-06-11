# knowledge_project/urls.py
from django.urls import path,re_path
from . import views
from . import folder_views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('healthz', views.healthz, name='healthz'),
    path('readyz', views.readyz, name='readyz'),
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
    path('api/notes/<int:note_id>/comments/', views.note_comments_api, name='note_comments_api'),
    path('api/notes/<int:note_id>/comments/create/', views.note_comment_create_api, name='note_comment_create_api'),
    path('api/notes/<int:note_id>/report/', views.note_report_api, name='note_report_api'),
    path('api/comments/<int:comment_id>/delete/', views.note_comment_delete_api, name='note_comment_delete_api'),
    path('api/comments/<int:comment_id>/report/', views.note_comment_report_api, name='note_comment_report_api'),
    path('api/ubb/resolve-qqmusic/', views.resolve_qqmusic_share_api, name='resolve_qqmusic_share_api'),
    # --- 【新增】CKEditor 5 图片上传的 API 路由 ---
    path('api/upload/ckeditor_image/', views.ckeditor_image_upload_view, name='ckeditor_image_upload_view'),
    # --- 【新增】图片上传的 API 路由 ---
    path('api/upload/image/', views.image_upload_view, name='image_upload_view'),
    re_path(r'^protected_uploads/(?P<file_path>.*)$', views.protected_media_view, name='protected_media_view'),
    path('api/public-notes/', views.public_notes_api, name='public_notes_api'),
    path('api/notes/history/', views.note_history_api, name='note_history_api'),
    path('api/notes/record-history/', views.record_note_history_api, name='record_note_history_api'),
    path('api/home-stats/', views.home_stats_api, name='home_stats_api'),
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
    path('api/notifications/', views.notifications_list_api, name='notifications_list_api'),
    path('api/notifications/unread-count/', views.notifications_unread_count_api, name='notifications_unread_count_api'),
    path('api/notifications/mark-read/', views.notifications_mark_read_api, name='notifications_mark_read_api'),

    # ==================== 主题设置 API ====================
    path('api/theme-settings/', views.theme_settings, name='theme_settings'),

    # ==================== 私信功能 API ====================
    path('messages/', views.messages_view, name='messages'),
    path('uploads/messages/<path:path>', views.blocked_message_attachment_media_api, name='blocked_message_attachment_media_api'),
    re_path(r'^uploads/(?P<file_path>.*)$', views.public_profile_media_view, name='public_profile_media_view'),
    path('api/messages/send/', views.send_message_api, name='send_message_api'),
    path('api/messages/forward/', views.forward_message_api, name='forward_message_api'),
    path('api/messages/attachments/upload/', views.upload_message_attachment_api, name='upload_message_attachment_api'),
    path('api/messages/attachments/<int:attachment_id>/file/', views.message_attachment_file_api, name='message_attachment_file_api'),
    path('api/messages/attachments/<int:attachment_id>/report/', views.report_message_attachment_api, name='report_message_attachment_api'),
    path('api/messages/attachments/<int:attachment_id>/review/', views.review_reported_attachment, name='review_reported_attachment'),
    path('api/messages/get/', views.get_messages_api, name='get_messages_api'),
    path('api/messages/conversations/', views.get_message_conversations_api, name='get_message_conversations_api'),
    path('api/messages/groups/policy/', views.get_group_policy_api, name='get_group_policy_api'),
    path('api/messages/groups/', views.create_message_group_api, name='create_message_group_api'),
    path('api/messages/groups/<int:group_id>/', views.message_group_detail_api, name='message_group_detail_api'),
    path('api/messages/groups/<int:group_id>/members/', views.add_group_members_api, name='add_group_members_api'),
    path('api/messages/groups/<int:group_id>/members/<int:user_id>/', views.remove_group_member_api, name='remove_group_member_api'),
    path('api/messages/groups/<int:group_id>/leave/', views.leave_message_group_api, name='leave_message_group_api'),
    path('api/messages/groups/<int:group_id>/dissolve/', views.dissolve_message_group_api, name='dissolve_message_group_api'),
    path('api/messages/groups/<int:group_id>/settings/<str:action>/', views.toggle_group_setting_api, name='toggle_group_setting_api'),
    path('api/messages/groups/<int:group_id>/messages/', views.get_group_messages_api, name='get_group_messages_api'),
    path('api/messages/groups/<int:group_id>/send/', views.send_group_message_api, name='send_group_message_api'),
    path('api/messages/groups/<int:group_id>/messages/<int:message_id>/edit/', views.edit_group_message_api, name='edit_group_message_api'),
    path('api/messages/groups/<int:group_id>/messages/<int:message_id>/delete/', views.delete_group_message_api, name='delete_group_message_api'),
    path('api/messages/groups/<int:group_id>/messages/<int:message_id>/report/', views.report_group_message_api, name='report_group_message_api'),
    path('api/messages/page-touch/', views.touch_messages_page_api, name='touch_messages_page_api'),
    path('api/messages/preference/', views.get_message_preference_api, name='get_message_preference_api'),
    path('api/messages/preference/update/', views.update_message_preference_api, name='update_message_preference_api'),
    path('api/messages/bulk-delete/', views.bulk_delete_messages_api, name='bulk_delete_messages_api'),
    path('api/messages/<int:message_id>/delete/', views.delete_message_api, name='delete_message_api'),
    path('api/messages/conversation/clear/', views.clear_conversation_api, name='clear_conversation_api'),
    path('api/messages/conversation/mark-read/', views.mark_conversation_read_api, name='mark_conversation_read_api'),
    path('api/messages/conversation/mark-unread/', views.mark_conversation_unread_api, name='mark_conversation_unread_api'),
    path('api/messages/conversation/pin/', views.toggle_pin_api, name='toggle_pin_api'),
    path('api/messages/conversation/mute/', views.toggle_mute_api, name='toggle_mute_api'),
    path('api/messages/conversation/archive/', views.toggle_archive_api, name='toggle_archive_api'),
    path('api/messages/conversation/disappearing/', views.set_disappearing_api, name='set_disappearing_api'),
    path('api/messages/conversation/settings/', views.get_conversation_settings_api, name='get_conversation_settings_api'),
    path('api/messages/search/', views.search_messages_api, name='search_messages_api'),
    path('api/messages/conversation/export/', views.export_conversation_api, name='export_conversation_api'),
    path('api/users/<int:user_id>/profile/', views.get_user_public_profile_api, name='get_user_public_profile_api'),
    path('user/<int:user_id>/', views.user_public_profile_view, name='user_public_profile'),
    path('api/users/search/', views.search_users_api, name='search_users_api'),
    path('api/users/block/', views.block_user_api, name='block_user_api'),
    path('api/users/unblock/', views.unblock_user_api, name='unblock_user_api'),
    path('api/users/blocked/', views.get_blocked_users_api, name='get_blocked_users_api'),
    path('api/users/report/', views.report_user_api, name='report_user_api'),

    # ==================== 举报处置中心（仅超级管理员） ====================
    path('moderation/reports/', views.moderation_view, name='moderation_reports'),
    path('api/moderation/reports/', views.moderation_reports_list_api, name='moderation_reports_list_api'),
    path('api/moderation/reports/<str:rtype>/<int:rid>/', views.moderation_report_detail_api, name='moderation_report_detail_api'),
    path('api/moderation/reports/<str:rtype>/<int:rid>/resolve/', views.moderation_resolve_api, name='moderation_resolve_api'),
    path('api/moderation/templates/', views.moderation_templates_api, name='moderation_templates_api'),
    path('api/moderation/users/<int:user_id>/sanction/', views.moderation_user_sanction_api, name='moderation_user_sanction_api'),
    path('api/moderation/sanctions/<int:sid>/revoke/', views.moderation_revoke_sanction_api, name='moderation_revoke_sanction_api'),
    path('api/moderation/sanctions/<int:sid>/appeal/', views.moderation_sanction_appeal_api, name='moderation_sanction_appeal_api'),
    path('api/moderation/appeals/<int:appeal_id>/resolve/', views.moderation_appeal_resolve_api, name='moderation_appeal_resolve_api'),
    path('api/moderation/attachments/<int:attachment_id>/file/', views.moderation_attachment_file_api, name='moderation_attachment_file_api'),

    # ==================== 未读统计 / 账户可发现性 / 关注 ====================
    path('api/messages/unread-count/', views.get_unread_messages_count_api, name='get_unread_messages_count_api'),
    path('api/users/discoverability/', views.update_discoverability_api, name='update_discoverability_api'),
    path('api/users/follow/', views.follow_user_api, name='follow_user_api'),
    path('api/users/unfollow/', views.unfollow_user_api, name='unfollow_user_api'),
    path('api/users/<int:user_id>/follow-status/', views.follow_status_api, name='follow_status_api'),

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
    path('api/notes/<int:note_id>/copy/', folder_views.copy_note_api, name='copy_note_api'),
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
