from django.urls import path, re_path

from . import views


urlpatterns = [
    path('api/upload/ckeditor_image/', views.ckeditor_image_upload_view, name='ckeditor_image_upload_view'),
    path('api/upload/image/', views.image_upload_view, name='image_upload_view'),
    re_path(r'^protected_uploads/(?P<file_path>.*)$', views.protected_media_view, name='protected_media_view'),
    re_path(r'^uploads/(?P<file_path>.*)$', views.public_profile_media_view, name='public_profile_media_view'),
]
