from django.urls import path

from . import views


urlpatterns = [
    path('reports/', views.moderation_view, name='moderation_reports'),
]
