from django.urls import path

from . import dashboard_views, stats_views


urlpatterns = [
    path('healthz', dashboard_views.healthz, name='healthz'),
    path('readyz', dashboard_views.readyz, name='readyz'),
    path('api/home-stats/', stats_views.home_stats_api, name='home_stats_api'),
    path('dashboard/', dashboard_views.dashboard_view, name='dashboard'),
    path('api/dashboard/stats/', dashboard_views.dashboard_stats_api, name='dashboard_stats_api'),
    path('api/ban_ip/', dashboard_views.ban_ip_api, name='ban_ip_api'),
]
