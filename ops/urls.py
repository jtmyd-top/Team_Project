from django.urls import path

from . import backup_views, dashboard_views, stats_views


urlpatterns = [
    path('healthz', dashboard_views.healthz, name='healthz'),
    path('readyz', dashboard_views.readyz, name='readyz'),
    path('service-worker.js', dashboard_views.service_worker, name='service_worker'),
    path('api/home-stats/', stats_views.home_stats_api, name='home_stats_api'),
    path('dashboard/', dashboard_views.dashboard_view, name='dashboard'),
    path('api/dashboard/stats/', dashboard_views.dashboard_stats_api, name='dashboard_stats_api'),
    path('api/ops/backups/', backup_views.backup_status_api, name='backup_status_api'),
    path('api/ban_ip/', dashboard_views.ban_ip_api, name='ban_ip_api'),
]
