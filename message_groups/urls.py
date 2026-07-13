from django.urls import path

from . import views


urlpatterns = [
    path('api/messages/groups/policy/', views.get_group_policy_api, name='get_group_policy_api'),
    path('api/messages/groups/', views.create_message_group_api, name='create_message_group_api'),
    path('api/messages/groups/<int:group_id>/', views.message_group_detail_api, name='message_group_detail_api'),
    path('api/messages/groups/<int:group_id>/profile/', views.update_group_profile_api, name='update_group_profile_api'),
    path(
        'api/messages/groups/<int:group_id>/transfer-ownership/',
        views.transfer_group_ownership_api,
        name='transfer_group_ownership_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/check-transfer-eligibility/<int:user_id>/',
        views.check_transfer_eligibility_api,
        name='check_transfer_eligibility_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/messages/<int:message_id>/reaction/',
        views.toggle_message_reaction_api,
        name='toggle_message_reaction_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/join-request/',
        views.request_join_group_api,
        name='request_join_group_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/join-requests/',
        views.group_join_requests_api,
        name='group_join_requests_api',
    ),
    path(
        'api/messages/groups/join-requests/pending/',
        views.all_pending_join_requests_api,
        name='all_pending_join_requests_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/join-requests/<int:request_id>/review/',
        views.review_join_request_api,
        name='review_join_request_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/announcement/',
        views.update_group_announcement_api,
        name='update_group_announcement_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/announcement/reads/',
        views.group_announcement_reads_api,
        name='group_announcement_reads_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/announcement/<int:announcement_id>/',
        views.group_announcement_detail_api,
        name='group_announcement_detail_api',
    ),
    path('api/messages/groups/<int:group_id>/mute-mode/', views.set_group_mute_mode_api, name='set_group_mute_mode_api'),
    path('api/messages/groups/<int:group_id>/bans/', views.group_bans_api, name='group_bans_api'),
    path(
        'api/messages/groups/<int:group_id>/bans/<int:ban_id>/revoke/',
        views.revoke_group_ban_api,
        name='revoke_group_ban_api',
    ),
    path('api/messages/groups/<int:group_id>/audit-logs/', views.group_audit_logs_api, name='group_audit_logs_api'),
    path('api/messages/groups/<int:group_id>/shared/', views.group_shared_items_api, name='group_shared_items_api'),
    path('api/messages/groups/<int:group_id>/members/', views.add_group_members_api, name='add_group_members_api'),
    path(
        'api/messages/groups/<int:group_id>/members/<int:user_id>/',
        views.remove_group_member_api,
        name='remove_group_member_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/members/<int:user_id>/role/',
        views.set_group_member_role_api,
        name='set_group_member_role_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/members/<int:user_id>/mute/',
        views.mute_group_member_api,
        name='mute_group_member_api',
    ),
    path('api/messages/groups/<int:group_id>/invites/', views.group_invite_links_api, name='group_invite_links_api'),
    path(
        'api/messages/groups/<int:group_id>/invites/<int:invite_id>/revoke/',
        views.revoke_group_invite_link_api,
        name='revoke_group_invite_link_api',
    ),
    path(
        'api/messages/groups/invites/<str:token>/preview/',
        views.preview_group_invite_api,
        name='preview_group_invite_api',
    ),
    path(
        'api/messages/groups/invites/<str:token>/join/',
        views.join_group_by_invite_api,
        name='join_group_by_invite_api',
    ),
    path('api/messages/groups/<int:group_id>/leave/', views.leave_message_group_api, name='leave_message_group_api'),
    path('api/messages/groups/<int:group_id>/dissolve/', views.dissolve_message_group_api, name='dissolve_message_group_api'),
    path(
        'api/messages/groups/<int:group_id>/settings/<str:action>/',
        views.toggle_group_setting_api,
        name='toggle_group_setting_api',
    ),
    path('api/messages/groups/<int:group_id>/messages/', views.get_group_messages_api, name='get_group_messages_api'),
    path('api/messages/groups/<int:group_id>/send/', views.send_group_message_api, name='send_group_message_api'),
    path(
        'api/messages/groups/<int:group_id>/notes/share/',
        views.share_note_to_group_api,
        name='share_note_to_group_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/note-shares/<int:share_id>/',
        views.get_group_note_share_api,
        name='get_group_note_share_api',
    ),
    path(
        'messages/groups/<int:group_id>/note-shares/<int:share_id>/view/',
        views.group_note_share_view,
        name='group_note_share_view',
    ),
    path(
        'api/messages/groups/<int:group_id>/messages/<int:message_id>/pin/',
        views.pin_group_message_api,
        name='pin_group_message_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/messages/<int:message_id>/edit/',
        views.edit_group_message_api,
        name='edit_group_message_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/messages/<int:message_id>/delete/',
        views.delete_group_message_api,
        name='delete_group_message_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/messages/<int:message_id>/report/',
        views.report_group_message_api,
        name='report_group_message_api',
    ),
    path('api/messages/groups/<int:group_id>/polls/', views.group_polls_api, name='group_polls_api'),
    path(
        'api/messages/groups/<int:group_id>/polls/<int:poll_id>/vote/',
        views.vote_group_poll_api,
        name='vote_group_poll_api',
    ),
    path(
        'api/messages/groups/<int:group_id>/polls/<int:poll_id>/close/',
        views.close_group_poll_api,
        name='close_group_poll_api',
    ),
    path('api/messages/groups/<int:group_id>/tasks/', views.group_tasks_api, name='group_tasks_api'),
    path(
        'api/messages/groups/<int:group_id>/tasks/<int:task_id>/complete/',
        views.complete_group_task_api,
        name='complete_group_task_api',
    ),
]
