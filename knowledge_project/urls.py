# knowledge_project/urls.py
from . import views
from django.urls import path
from .views import home, SignUpView
from .views import home, SignUpView, knowledge_list,captcha_image,check_username,CustomLoginView
urlpatterns = [
    path('', home, name='home'),
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
    #path('api/notes/create/', views.note_create_api, name='note_create_api'),
    # path('notes/public/<uuid:public_id>/', views.public_note_view, name='public_note_view'),

]

