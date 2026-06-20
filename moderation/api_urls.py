from django.urls import path

from . import views


urlpatterns = [
    path('reports/', views.moderation_reports_list_api, name='moderation_reports_list_api'),
    path('reports/<str:rtype>/<int:rid>/', views.moderation_report_detail_api, name='moderation_report_detail_api'),
    path('reports/<str:rtype>/<int:rid>/resolve/', views.moderation_resolve_api, name='moderation_resolve_api'),
    path('templates/', views.moderation_templates_api, name='moderation_templates_api'),
    path('users/<int:user_id>/sanction/', views.moderation_user_sanction_api, name='moderation_user_sanction_api'),
    path('sanctions/<int:sid>/revoke/', views.moderation_revoke_sanction_api, name='moderation_revoke_sanction_api'),
    path('sanctions/<int:sid>/appeal/', views.moderation_sanction_appeal_api, name='moderation_sanction_appeal_api'),
    path('appeals/<int:appeal_id>/resolve/', views.moderation_appeal_resolve_api, name='moderation_appeal_resolve_api'),
    path('attachments/<int:attachment_id>/file/', views.moderation_attachment_file_api, name='moderation_attachment_file_api'),
]
