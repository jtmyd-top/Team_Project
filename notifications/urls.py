from django.urls import path

from . import views


urlpatterns = [
    path('', views.notifications_list_api, name='notifications_list_api'),
    path('unread-count/', views.notifications_unread_count_api, name='notifications_unread_count_api'),
    path('mark-read/', views.notifications_mark_read_api, name='notifications_mark_read_api'),
]
