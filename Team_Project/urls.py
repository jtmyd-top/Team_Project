"""
URL configuration for Team_Project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from ops.admin_auth import secure_admin_site

# 将默认 admin 的已注册模型复制到安全 admin
for model, model_admin in admin.site._registry.items():
    if model not in secure_admin_site._registry:
        secure_admin_site._registry[model] = model_admin

urlpatterns = [
    path('admin/', secure_admin_site.urls),  # 使用安全增强的 Admin
    # 核心修复：确保包含了Django内置的认证URL
    # 这会自动为我们添加 /accounts/login/, /accounts/logout/ 等所有必需的URL
    path('accounts/', include('django.contrib.auth.urls')),
    # 将我们自己app的URL包含进来
    # Domain app URL entrypoints live here; knowledge_project.urls is kept only as a compatibility shell.
    path('', include('ops.urls')),
    path('', include('message_groups.urls')),
    path('', include('assets.urls')),
    path('', include('messaging.urls')),
    path('', include('notes.urls')),
    path('', include('accounts.urls')),
    path('', include('vault.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('moderation/', include('moderation.urls')),
    path('api/moderation/', include('moderation.api_urls')),
    path('', include('knowledge_project.urls')),
    path("ckeditor5/", include('django_ckeditor_5.urls'), name="ck_editor_5_upload_file"),
    path('captcha/', include('captcha.urls')),  # django-simple-captcha
]
# --- 【核心新增代码】---
# 只有在 DEBUG 模式下，才让 Django 开发服务器来处理媒体文件
if settings.DEBUG:
    try:
        import debug_toolbar
    except ImportError:
        debug_toolbar = None
    if debug_toolbar is not None:
        urlpatterns.insert(0, path('__debug__/', include(debug_toolbar.urls)))

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # 这行代码会添加一个新的 URL 模式。
    # 它会拦截以 settings.MEDIA_URL (即 '/uploads/') 开头的请求，
    # 然后去 settings.MEDIA_ROOT (即 'D:\...\uploads') 文件夹下查找并返回对应的文件。
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
