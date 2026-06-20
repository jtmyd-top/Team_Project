from django.urls import path

from . import views


urlpatterns = [
    path('messages/', views.messages_view, name='messages'),
    path(
        'uploads/messages/<path:path>',
        views.blocked_message_attachment_media_api,
        name='blocked_message_attachment_media_api',
    ),
    path('api/messages/send/', views.send_message_api, name='send_message_api'),
    path('api/messages/forward/', views.forward_message_api, name='forward_message_api'),
    path('api/messages/attachments/upload/', views.upload_message_attachment_api, name='upload_message_attachment_api'),
    path(
        'api/messages/attachments/<int:attachment_id>/file/',
        views.message_attachment_file_api,
        name='message_attachment_file_api',
    ),
    path(
        'api/messages/attachments/<int:attachment_id>/report/',
        views.report_message_attachment_api,
        name='report_message_attachment_api',
    ),
    path(
        'api/messages/attachments/<int:attachment_id>/review/',
        views.review_reported_attachment,
        name='review_reported_attachment',
    ),
    path('api/messages/get/', views.get_messages_api, name='get_messages_api'),
    path('api/messages/conversations/', views.get_message_conversations_api, name='get_message_conversations_api'),
    path('api/messages/page-touch/', views.touch_messages_page_api, name='touch_messages_page_api'),
    path('api/messages/preference/', views.get_message_preference_api, name='get_message_preference_api'),
    path('api/messages/preference/update/', views.update_message_preference_api, name='update_message_preference_api'),
    path('api/messages/bulk-delete/', views.bulk_delete_messages_api, name='bulk_delete_messages_api'),
    path('api/messages/<int:message_id>/delete/', views.delete_message_api, name='delete_message_api'),
    path('api/messages/conversation/clear/', views.clear_conversation_api, name='clear_conversation_api'),
    path(
        'api/messages/conversation/mark-read/',
        views.mark_conversation_read_api,
        name='mark_conversation_read_api',
    ),
    path(
        'api/messages/conversation/mark-unread/',
        views.mark_conversation_unread_api,
        name='mark_conversation_unread_api',
    ),
    path('api/messages/conversation/pin/', views.toggle_pin_api, name='toggle_pin_api'),
    path('api/messages/conversation/mute/', views.toggle_mute_api, name='toggle_mute_api'),
    path('api/messages/conversation/archive/', views.toggle_archive_api, name='toggle_archive_api'),
    path('api/messages/conversation/disappearing/', views.set_disappearing_api, name='set_disappearing_api'),
    path(
        'api/messages/conversation/settings/',
        views.get_conversation_settings_api,
        name='get_conversation_settings_api',
    ),
    path('api/messages/search/', views.search_messages_api, name='search_messages_api'),
    path('api/messages/conversation/export/', views.export_conversation_api, name='export_conversation_api'),
    path('api/messages/unread-count/', views.get_unread_messages_count_api, name='get_unread_messages_count_api'),
    path('api/users/<int:user_id>/profile/', views.get_user_public_profile_api, name='get_user_public_profile_api'),
    path('api/users/search/', views.search_users_api, name='search_users_api'),
    path('api/users/block/', views.block_user_api, name='block_user_api'),
    path('api/users/unblock/', views.unblock_user_api, name='unblock_user_api'),
    path('api/users/blocked/', views.get_blocked_users_api, name='get_blocked_users_api'),
    path('api/users/report/', views.report_user_api, name='report_user_api'),
    path('api/users/discoverability/', views.update_discoverability_api, name='update_discoverability_api'),
]
