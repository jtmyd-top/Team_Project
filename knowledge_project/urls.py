# knowledge_project/urls.py
from . import views
from django.urls import path,re_path
from .views import  SignUpView
from .views import SignUpView, knowledge_list,captcha_image,check_username,CustomLoginView
urlpatterns = [
    path('', views.public_notes_list_view, name='home'),
    path('signup/', SignUpView.as_view(), name='signup'),
    path('knowledge/', knowledge_list, name='knowledge_list'),
    path('captcha/', captcha_image, name='captcha_image'),
    # 【任务二】新增：为实时用户名检查提供API端点
    path('check-username/', check_username, name='check_username'),
    path('signup/', SignUpView.as_view(), name='signup'),
    path('send-email-code/', views.SendEmailCodeView.as_view(), name='send_email_code'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('api/notes/search/', views.search_notes_api, name='api_search_notes'),
    path('api/notes/<int:note_id>/', views.note_detail_api, name='api_note_detail'),
    path('api/notes/all/', views.get_all_notes_api, name='get_all_notes_api'),
    path('api/notes/create/', views.create_note_api, name='create_note_api'),
    path('notes/public/<uuid:public_id>/', views.public_note_view, name='public_note_view'),
    # --- 【新增】CKEditor 5 图片上传的 API 路由 ---
    path('api/upload/ckeditor_image/', views.ckeditor_image_upload_view, name='ckeditor_image_upload_view'),
    re_path(r'^protected_uploads/(?P<file_path>.*)$', views.protected_media_view, name='protected_media_view'),
# --- 【新增】图片上传的 API 路由 ---
    path('api/upload/image/', views.image_upload_view, name='image_upload_view'),
    re_path(r'^protected_uploads/(?P<file_path>.*)$', views.protected_media_view, name='protected_media_view'),

]

