"""测试专用 settings：不连真实 MySQL / Redis / SMTP / Turnstile。

跑测试用：
    set DJANGO_SETTINGS_MODULE=Team_Project.settings_test
    python manage.py test knowledge_project
或：
    python manage.py test --settings=Team_Project.settings_test knowledge_project
"""
import os

# 在加载 settings 之前关掉 turnstile —— turnstile.py 在 import 时读取这个环境变量映射出的设置
os.environ.setdefault('TURNSTILE_ENABLED', 'false')
os.environ.setdefault('SESSION_ENGINE', 'django.contrib.sessions.backends.signed_cookies')
# CLOUDFLARE_TURNSTILE_* 必须有值，否则 TurnstileValidator() 会 ImproperlyConfigured
os.environ.setdefault('CLOUDFLARE_TURNSTILE_SITE_KEY', 'test-site-key')
os.environ.setdefault('CLOUDFLARE_TURNSTILE_SECRET_KEY', 'test-secret-key')
os.environ.setdefault('REALTIME_MESSAGES_ENABLED', 'false')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-tests-only')
os.environ.setdefault('DEBUG', 'true')

from .settings import *  # noqa: E402, F401, F403

# ---- 数据库：内存 SQLite ----
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# ---- 缓存：本地内存 ----
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'tests',
    }
}

# ---- Session：用 signed_cookies，避免依赖 cache backend 或 db session 表 ----
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# ---- 邮件：捕获到 outbox，不真实发送 ----
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
DEFAULT_FROM_EMAIL = 'test@example.com'

# ---- 关掉 channels / 实时推送 ----
REALTIME_MESSAGES_ENABLED = False

# ---- 安全相关：关闭测试中无意义的 SSL 强制 ----
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# ---- 关闭密码强度校验，减少夹杂错误 ----
AUTH_PASSWORD_VALIDATORS = []

# ---- 避免测试时跑后台线程发邮件 / 拉头像 ----
TURNSTILE_ENABLED = False

# ---- 关闭 IP-ban / Vault 等中间件中需要的真实 cache 时的 IGNORE_EXCEPTIONS ----
# LocMemCache 已经够用了，无需调整

# ---- MEDIA：写到 tmp，避免污染真实 uploads ----
import tempfile
MEDIA_ROOT = tempfile.mkdtemp(prefix='kp-test-media-')

# 测试时 STATICFILES_DIRS 中的 static 目录可能不存在，照常保留即可（Django 会容忍）
