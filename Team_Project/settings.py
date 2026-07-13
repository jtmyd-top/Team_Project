# settings.py

import importlib.util
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, '.env'))


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {'true', '1', 't', 'yes', 'on'}


def env_list(name, default=''):
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(',') if item.strip()]


DJANGO_ENV = os.getenv('DJANGO_ENV', 'development').strip().lower()
IS_PRODUCTION = DJANGO_ENV in {'prod', 'production'}

SECRET_KEY = os.getenv('SECRET_KEY', '')
if not SECRET_KEY:
    raise ImproperlyConfigured(
        'SECRET_KEY must be set in .env or environment variables. '
        'Generate one with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
    )
DEBUG = env_bool('DEBUG', not IS_PRODUCTION)

_allowed_hosts = env_list('ALLOWED_HOSTS')
if _allowed_hosts:
    ALLOWED_HOSTS = _allowed_hosts
    if DEBUG and 'testserver' not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append('testserver')
elif DEBUG:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
else:
    raise ImproperlyConfigured('ALLOWED_HOSTS must be set in production.')

CSRF_TRUSTED_ORIGINS = env_list(
    'CSRF_TRUSTED_ORIGINS',
    'https://localhost,https://localhost:443,https://127.0.0.1,https://127.0.0.1:443,https://192.168.1.6,https://192.168.1.6:443'
)

TRUSTED_PROXY_CIDRS = env_list('TRUSTED_PROXY_CIDRS', '127.0.0.1/32,::1/128')
USE_X_FORWARDED_HOST = env_bool('USE_X_FORWARDED_HOST', IS_PRODUCTION)
USE_X_FORWARDED_PORT = env_bool('USE_X_FORWARDED_PORT', IS_PRODUCTION)
if env_bool('TRUST_X_FORWARDED_PROTO', IS_PRODUCTION):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

VITE_DEV_MODE = env_bool('VITE_DEV_MODE', False)
CHANNELS_AVAILABLE = importlib.util.find_spec('channels') is not None
CHANNELS_REDIS_AVAILABLE = importlib.util.find_spec('channels_redis') is not None
DAPHNE_AVAILABLE = importlib.util.find_spec('daphne') is not None

INSTALLED_APPS = []
if DAPHNE_AVAILABLE and CHANNELS_AVAILABLE:
    INSTALLED_APPS.append('daphne')

# 注意：Django 内置 apps 通常应该在自定义 apps 之前
# 但由于某些自定义 apps 可能依赖特定的加载顺序，这里保持原顺序
INSTALLED_APPS += [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
    'accounts.apps.AccountsConfig',
    'notifications.apps.NotificationsConfig',
    'notes.apps.NotesConfig',
    'assets.apps.AssetsConfig',
    'vault.apps.VaultConfig',
    'ops.apps.OpsConfig',
    'moderation.apps.ModerationConfig',
    'messaging.apps.MessagingConfig',
    'message_groups.apps.MessageGroupsConfig',
    'knowledge_project.apps.KnowledgeProjectConfig',
    'django_ckeditor_5',
    'captcha',
]

if CHANNELS_AVAILABLE:
    INSTALLED_APPS.append('channels')

if DEBUG and importlib.util.find_spec('debug_toolbar') is not None:
    INSTALLED_APPS.append('debug_toolbar')

try:
    import django_extensions  # noqa: F401
    INSTALLED_APPS.append('django_extensions')
except ImportError:
    pass

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'Team_Project.middleware.IPBanMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'Team_Project.middleware.SessionTimeoutMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'Team_Project.middleware.ContentSecurityPolicyMiddleware',
    'Team_Project.middleware.VaultLockMiddleware',
]

if DEBUG and importlib.util.find_spec('debug_toolbar') is not None:
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

INTERNAL_IPS = env_list('INTERNAL_IPS', '127.0.0.1,::1')

ROOT_URLCONF = 'Team_Project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'Team_Project.wsgi.application'
ASGI_APPLICATION = 'Team_Project.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('mysql_name', 'knowledge_project'),
        'USER': os.getenv('mysql_user'),
        'PASSWORD': os.getenv('mysql_passwd'),
        'HOST': os.getenv('mysql_ip'),
        'PORT': os.getenv('mysql_port'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 9}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

DEFAULT_FILE_STORAGE_BACKEND = os.getenv('DEFAULT_FILE_STORAGE_BACKEND', '').strip()
MEDIA_URL = os.getenv('MEDIA_URL', '/uploads/')
MEDIA_ROOT = os.getenv('MEDIA_ROOT', os.path.join(BASE_DIR, 'knowledge_project', 'uploads'))
BACKUP_DIR = os.getenv('BACKUP_DIR', os.path.join(BASE_DIR, 'backups'))
IMAGE_UPLOAD_MAX_SIZE = int(os.getenv('IMAGE_UPLOAD_MAX_SIZE', str(10 * 1024 * 1024)))
IMAGE_UPLOAD_ALLOWED_EXTENSIONS = env_list('IMAGE_UPLOAD_ALLOWED_EXTENSIONS', '.jpg,.jpeg,.png,.gif,.webp')
IMAGE_UPLOAD_ALLOWED_MIME_TYPES = env_list(
    'IMAGE_UPLOAD_ALLOWED_MIME_TYPES',
    'image/jpeg,image/png,image/gif,image/webp'
)

# WhiteNoise 配置 - 用于在 ASGI/Daphne 下提供静态文件
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

if DEFAULT_FILE_STORAGE_BACKEND:
    STORAGES['default']['BACKEND'] = DEFAULT_FILE_STORAGE_BACKEND

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'
PASSWORD_RESET_TIMEOUT = 43200
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REDIS_URL = os.getenv('REDIS_URL') or os.getenv('redis1')
if not REDIS_URL:
    REDIS_URL = 'redis://127.0.0.1:6379/1' if DEBUG else ''

if not REDIS_URL and IS_PRODUCTION:
    raise ImproperlyConfigured('REDIS_URL or redis1 must be set in production.')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 100,
                'socket_keepalive': True,
                'health_check_interval': 30,
                'socket_connect_timeout': 5,
                'socket_timeout': 5,
                'retry_on_timeout': True,
            },
            'IGNORE_EXCEPTIONS': env_bool('CACHE_IGNORE_EXCEPTIONS', not IS_PRODUCTION),
        },
    }
}
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
DJANGO_REDIS_LOGGER = 'django_redis'

# Keep an authoritative session record in MySQL. Redis remains the fast path,
# but a cache flush must not log every user out.
SESSION_ENGINE = os.getenv('SESSION_ENGINE', 'django.contrib.sessions.backends.cached_db')
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 10800
SESSION_IDLE_TIMEOUT = int(os.getenv('SESSION_IDLE_TIMEOUT', SESSION_COOKIE_AGE))
SESSION_ABSOLUTE_TIMEOUT = int(os.getenv('SESSION_ABSOLUTE_TIMEOUT', SESSION_COOKIE_AGE))
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_TOUCH_INTERVAL_SECONDS = int(os.getenv('SESSION_TOUCH_INTERVAL_SECONDS', '300'))
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', IS_PRODUCTION)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', IS_PRODUCTION)
CSRF_COOKIE_HTTPONLY = env_bool('CSRF_COOKIE_HTTPONLY', False)
CSRF_COOKIE_SAMESITE = os.getenv('CSRF_COOKIE_SAMESITE', 'Lax')

SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', IS_PRODUCTION)
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000' if IS_PRODUCTION else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', IS_PRODUCTION)
SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', False)
SECURE_REFERRER_POLICY = os.getenv('SECURE_REFERRER_POLICY', 'same-origin')
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

SMTP_PROXY_HOST = os.getenv('SMTP_PROXY_HOST')
SMTP_PROXY_PORT = int(os.getenv('SMTP_PROXY_PORT', '1080'))
SMTP_PROXY_TYPE = os.getenv('SMTP_PROXY_TYPE', 'socks5')
SMTP_PROXY_USERNAME = os.getenv('SMTP_PROXY_USERNAME')
SMTP_PROXY_PASSWORD = os.getenv('SMTP_PROXY_PASSWORD')
EMAIL_FALLBACK_TO_PROXY = env_bool('EMAIL_FALLBACK_TO_PROXY', True)
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '30'))

REALTIME_MESSAGES_ENABLED = CHANNELS_AVAILABLE and env_bool('REALTIME_MESSAGES_ENABLED', True)
REALTIME_MESSAGES_PATH = os.getenv('REALTIME_MESSAGES_PATH', '/ws/messages/')
WS_CLIENT_INACTIVITY_TIMEOUT = int(os.getenv('WS_CLIENT_INACTIVITY_TIMEOUT', '300'))
REQUIRE_SHARED_CHANNEL_LAYER = env_bool('REQUIRE_SHARED_CHANNEL_LAYER', IS_PRODUCTION)

# Web Push remains disabled until a VAPID key pair and contact subject are configured.
WEB_PUSH_ENABLED = env_bool('WEB_PUSH_ENABLED', False)
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '').strip()
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', '').strip()
VAPID_SUBJECT = os.getenv('VAPID_SUBJECT', '').strip()
WEB_PUSH_TTL_SECONDS = int(os.getenv('WEB_PUSH_TTL_SECONDS', '300'))
WEB_PUSH_CONFIGURED = bool(
    WEB_PUSH_ENABLED
    and VAPID_PUBLIC_KEY
    and VAPID_PRIVATE_KEY
    and VAPID_SUBJECT
)

if REALTIME_MESSAGES_ENABLED:
    channel_redis_url = os.getenv('CHANNEL_REDIS_URL') or REDIS_URL or 'redis://127.0.0.1:6379/2'
    if CHANNELS_REDIS_AVAILABLE:
        CHANNEL_LAYERS = {
            'default': {
                'BACKEND': 'channels_redis.core.RedisChannelLayer',
                'CONFIG': {
                    'hosts': [channel_redis_url],
                    'expiry': 60,
                    'group_expiry': 86400,
                },
            },
        }
    elif REQUIRE_SHARED_CHANNEL_LAYER:
        raise ImproperlyConfigured(
            'channels_redis is required when REALTIME_MESSAGES_ENABLED is true in production.'
        )
    else:
        CHANNEL_LAYERS = {
            'default': {
                'BACKEND': 'channels.layers.InMemoryChannelLayer',
            },
        }

CLOUDFLARE_TURNSTILE_SITE_KEY = os.getenv('CLOUDFLARE_TURNSTILE_SITE_KEY')
CLOUDFLARE_TURNSTILE_SECRET_KEY = os.getenv('CLOUDFLARE_TURNSTILE_SECRET_KEY')
TURNSTILE_ENABLED = env_bool('TURNSTILE_ENABLED', True)

CAPTCHA_IMAGE_SIZE = (120, 50)
CAPTCHA_FONT_SIZE = 32
CAPTCHA_LENGTH = 4
CAPTCHA_TIMEOUT = 5
CAPTCHA_NOISE_FUNCTIONS = ('captcha.helpers.noise_dots',)
CAPTCHA_CHALLENGE_FUNCT = 'captcha.helpers.random_char_challenge'
CAPTCHA_BACKEND = os.getenv('CAPTCHA_BACKEND', 'auto')

CKEDITOR_5_CUSTOM_JS_URL = 'ckeditor5/ckeditor.js'
CKEDITOR_5_UPLOAD_URL = reverse_lazy('ckeditor_image_upload_view')
CKEDITOR_5_CSRF_COOKIE_NAME = 'csrftoken'

customColorPalette = [
    {'color': 'hsl(4, 90%, 58%)', 'label': 'Red'},
    {'color': 'hsl(340, 82%, 52%)', 'label': 'Pink'},
    {'color': 'hsl(291, 64%, 42%)', 'label': 'Purple'},
    {'color': 'hsl(262, 52%, 47%)', 'label': 'Deep Purple'},
    {'color': 'hsl(231, 48%, 48%)', 'label': 'Indigo'},
    {'color': 'hsl(207, 90%, 54%)', 'label': 'Blue'},
    {'color': 'hsl(120, 73%, 45%)', 'label': 'Green'},
    {'color': 'hsl(50, 95%, 55%)', 'label': 'Yellow'},
    {'color': 'hsl(25, 95%, 53%)', 'label': 'Orange'},
    {'color': 'hsl(0, 0%, 20%)', 'label': 'Dark Gray'},
    {'color': 'hsl(0, 0%, 60%)', 'label': 'Light Gray'},
]

CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': ['heading', '|', 'bold', 'italic', 'link'],
    },
    'full': {
        'language': 'zh-cn',
        'extraPlugins': ['SimpleUploadAdapter'],
        'simpleUpload': {
            'uploadUrl': CKEDITOR_5_UPLOAD_URL,
        },
        'toolbar': [
            'sourceEditing', '|', 'findAndReplace', 'selectAll', '|',
            'heading', '|', 'bold', 'italic', 'underline', 'strikethrough', 'removeFormat', '|',
            'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor', 'highlight', '|',
            'alignment', '|', 'outdent', 'indent', '|',
            'bulletedList', 'numberedList', 'todoList', 'blockQuote', '|',
            'link', 'imageUpload', 'insertTable', 'mediaEmbed', 'horizontalLine', 'specialCharacters', 'pageBreak',
        ],
        'image': {
            'toolbar': [
                'imageTextAlternative', '|', 'imageStyle:alignLeft', 'imageStyle:alignRight',
                'imageStyle:alignCenter', 'imageStyle:side', '|', 'linkImage'
            ]
        },
        'table': {
            'contentToolbar': [
                'tableColumn', 'tableRow', 'mergeTableCells', 'tableProperties', 'tableCellProperties'
            ],
            'tableProperties': {'borderColors': customColorPalette, 'backgroundColors': customColorPalette},
            'tableCellProperties': {'borderColors': customColorPalette, 'backgroundColors': customColorPalette}
        },
        'heading': {
            'options': [
                {'model': 'paragraph', 'title': 'Paragraph', 'class': 'ck-heading_paragraph'},
                {'model': 'heading1', 'view': 'h1', 'title': 'Heading 1', 'class': 'ck-heading_heading1'},
                {'model': 'heading2', 'view': 'h2', 'title': 'Heading 2', 'class': 'ck-heading_heading2'}
            ]
        },
        'fontColor': {'colors': customColorPalette},
        'fontBackgroundColor': {'colors': customColorPalette},
        'alignment': {'options': ['left', 'right', 'center', 'justify']},
    }
}
