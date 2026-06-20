from django.urls import path

from . import views


urlpatterns = [
    path('api/vault/status/', views.vault_status, name='vault_status'),
    path('api/vault/init/', views.vault_init, name='vault_init'),
    path('api/vault/verify/', views.vault_verify, name='vault_verify'),
    path('api/vault/key/', views.vault_get_key, name='vault_get_key'),
    path('api/vault/export/', views.vault_export, name='vault_export'),
    path('api/vault/lock/', views.vault_lock, name='vault_lock'),
    path('api/vault/lock-status/', views.vault_lock_status, name='vault_lock_status'),
    path('api/vault/send-email-code/', views.vault_send_email_code, name='vault_send_email_code'),
    path('api/vault/notes/', views.vault_notes_list, name='vault_notes_list'),
]
