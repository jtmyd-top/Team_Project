# knowledge_project/urls.py
from django.urls import include, path
from . import views

urlpatterns = [
    path('', include('ops.urls')),
    path('', include('message_groups.urls')),
    path('', include('assets.urls')),
    path('', include('messaging.urls')),
    path('', include('notes.urls')),
    #path('public-notes/', views.public_notes_list_view, name='public_notes_list'),
    # 【任务二】新增：为实时用户名检查提供API端点
    # --- 【新增】CKEditor 5 图片上传的 API 路由 ---
    # --- 【新增】图片上传的 API 路由 ---
    path('', include('accounts.urls')),
    path('', include('vault.urls')),

    # ==================== 账户安全相关 API ====================

    # ==================== 通知偏好设置 API ====================
    path('api/notifications/', include('notifications.urls')),

    # ==================== 主题设置 API ====================

    # ==================== 私信功能 API ====================
    # Phase 2: 表情回应
    # Phase 3: 入群审批
    # Phase 3: 群公告管理

    # ==================== 举报处置中心（仅超级管理员） ====================
    path('moderation/', include('moderation.urls')),
    path('api/moderation/', include('moderation.api_urls')),

    # ==================== 未读统计 / 账户可发现性 / 关注 ====================

    # ==================== Turnstile API ====================

    # ==================== 图形验证码 API ====================

    # ==================== 登录API ====================

    # ==================== 2FA登录验证 API ====================

    # ==================== 文件夹相关 API ====================
    
    # ==================== 笔记管理 API（增强版）====================

    # ==================== 回收站（文件夹）API ====================

    # ==================== 保密柜（Vault）API ====================
    # ==================== 战情室 Dashboard ====================
    #path("logout/", views.logout_view, name="logout"),
]
