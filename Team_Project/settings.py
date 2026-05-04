# settings.py

import os
from pathlib import Path
from django.urls import reverse_lazy
from dotenv import load_dotenv


# --- 1. 修正 BASE_DIR 和环境变量加载 ---
# BASE_DIR 应该指向项目的根目录，即 manage.py 所在的目录
# 这将确保所有其他路径（如 static, media）都能正确解析
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载位于项目根目录下的 .env 文件
load_dotenv(os.path.join(BASE_DIR, '.env'))


# --- 2. 核心设置 ---
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-fallback-key-for-dev') # 建议从环境变量加载
DEBUG = os.getenv('DEBUG', 'True').lower() in ['true', '1', 't']
ALLOWED_HOSTS = ["*"] # 在生产环境中应配置为具体的域名

# HTTPS dev 环境下（runserver_plus + 自签证书），Django 4.x CSRF 校验要求 Origin 在白名单
# 从环境变量 CSRF_TRUSTED_ORIGINS 读取，逗号分隔；默认覆盖常见 LAN/localhost HTTPS 地址
# 注意：HTTPS 协议默认端口是 443，非默认端口（如 80/8000）Origin 里必须显式带端口
_csrf_env = os.getenv('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_env.split(',') if o.strip()] or [
    'https://localhost',
    'https://localhost:443',
    'https://127.0.0.1',
    'https://127.0.0.1:443',
    'https://192.168.1.6',
    'https://192.168.1.6:443',
]

# Vite 开发模式开关
# 设置为 True 时，模板会从 Vite 开发服务器 (localhost:5173) 加载资源
# 设置为 False 时，模板会从 static/dist/ 加载构建后的资源
VITE_DEV_MODE = os.getenv('VITE_DEV_MODE', 'False').lower() in ['true', '1', 't']


# --- 3. INSTALLED_APPS (只保留 django-ckeditor-5) ---
INSTALLED_APPS = [
    'knowledge_project.apps.KnowledgeProjectConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_ckeditor_5',  # 只保留这一个
    'captcha',  # django-simple-captcha
]

# django-extensions 提供 runserver_plus（HTTPS dev server），仅在已安装时启用
try:
    import django_extensions  # noqa: F401
    INSTALLED_APPS.append('django_extensions')
except ImportError:
    pass


# --- 4. 中间件和 URL 配置 ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'Team_Project.middleware.IPBanMiddleware',  # IP 封禁中间件（在认证之前拦截）
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'Team_Project.middleware.SessionTimeoutMiddleware',  # 服务端会话超时兜底
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'Team_Project.middleware.ContentSecurityPolicyMiddleware',  # CSP 响应头中间件
    'Team_Project.middleware.VaultLockMiddleware',  # 【新增】保密柜锁定中间件
]
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


# --- 5. 数据库 (只保留一份) ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'knowledge_project',
        'USER': os.getenv('mysql_user'),
        'PASSWORD': os.getenv('mysql_passwd'),
        'HOST': os.getenv('mysql_ip'),
        'PORT': os.getenv('mysql_port'),
        'OPTIONS': {'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"},
        'OPTIONS': {
                    # This line is critical!
                    'charset': 'utf8mb4',
                },
    }
}


# --- 6. 密码验证和国际化 (只保留一份) ---
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


# --- 7. 静态文件和媒体文件 (关键修正) ---
STATIC_URL = 'static/'
# 【修正】STATICFILES_DIRS 应该指向项目根目录下的 'static' 文件夹
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
# 【新增】运行 collectstatic 后，所有静态文件会被收集到这里
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/uploads/'
MEDIA_ROOT = os.path.join(BASE_DIR,'knowledge_project','uploads')


# --- 8. 认证、缓存、邮件 (清理重复项) ---
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

# 密码重置配置 - 设置为12小时过期
PASSWORD_RESET_TIMEOUT = 43200  # 12小时，以秒为单位

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        # 格式: redis://:密码@主机:端口/数据库编号
        # 如果Redis和Django运行在同一台服务器上，主机就是127.0.0.1
        "LOCATION": os.getenv('redis1'),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 100,
                # 空闲连接保活：内核层 TCP keepalive + 应用层每 30s 主动 PING
                "socket_keepalive": True,
                "health_check_interval": 30,
                # 快速失败而不是长时间挂起
                "socket_connect_timeout": 5,
                "socket_timeout": 5,
                # 偶发超时自动重试一次
                "retry_on_timeout": True,
            },
            # 增加一个密码选项，更明确
            "PASSWORD": os.getenv('mysql_passwd'),
            # 任何 cache 异常都不往上抛，返回 None；配合下面的日志开关避免静默丢数据
            "IGNORE_EXCEPTIONS": True,
        }
    }
}
# 被 IGNORE_EXCEPTIONS 吞掉的异常仍写日志，便于排障
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
DJANGO_REDIS_LOGGER = 'django_redis'
# --- 【核心新增配置】会话超时设置 ---

# 1. 设置 Session 的 cookie 有效期为3小时（以秒为单位）
#    3 小时 * 60 分钟/小时 * 60 秒/分钟 = 10800 秒
SESSION_COOKIE_AGE = 10800

# 2. 每次请求都保存并刷新 Session 的有效期，保留“有活动就续期”的滚动过期行为。
#    SessionTimeoutMiddleware 额外维护 last_activity_at，供在线用户统计使用。
SESSION_IDLE_TIMEOUT = int(os.getenv('SESSION_IDLE_TIMEOUT', SESSION_COOKIE_AGE))
SESSION_SAVE_EVERY_REQUEST = True
#mail设定
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# 智能邮件后端 (可选，当需要使用智能邮件发送器时取消注释)
# EMAIL_BACKEND = 'knowledge_project.utils.smart_email_sender.SmartEmailBackend'

# 代理邮件后端 (推荐，自动回退到代理)
# EMAIL_BACKEND = 'knowledge_project.utils.proxy_email_sender.ProxyEmailBackend'

EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# --- 邮件代理配置 ---
# 当直连失败时，自动使用代理重试
SMTP_PROXY_HOST = os.getenv('SMTP_PROXY_HOST')          # 代理服务器地址，如 '127.0.0.1'
SMTP_PROXY_PORT = int(os.getenv('SMTP_PROXY_PORT', '1080'))  # 代理端口，如 1080 (SOCKS5) 或 7890 (HTTP)
SMTP_PROXY_TYPE = os.getenv('SMTP_PROXY_TYPE', 'socks5')    # 代理类型: 'socks5', 'socks4', 或 'http'
SMTP_PROXY_USERNAME = os.getenv('SMTP_PROXY_USERNAME')  # 代理用户名（可选）
SMTP_PROXY_PASSWORD = os.getenv('SMTP_PROXY_PASSWORD')  # 代理密码（可选）
EMAIL_FALLBACK_TO_PROXY = os.getenv('EMAIL_FALLBACK_TO_PROXY', 'True').lower() in ['true', '1', 't']
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '30'))  # 连接超时时间（秒）

# --- Cloudflare Turnstile Configuration ---
CLOUDFLARE_TURNSTILE_SITE_KEY = os.getenv('CLOUDFLARE_TURNSTILE_SITE_KEY')
CLOUDFLARE_TURNSTILE_SECRET_KEY = os.getenv('CLOUDFLARE_TURNSTILE_SECRET_KEY')
# 开发环境可设置 TURNSTILE_ENABLED=false 跳过验证（用于网络无法访问 Cloudflare 的情况）
TURNSTILE_ENABLED = os.getenv('TURNSTILE_ENABLED', 'true').lower() in ['true', '1', 't', 'yes']

# --- django-simple-captcha Configuration ---
CAPTCHA_IMAGE_SIZE = (120, 50)
CAPTCHA_FONT_SIZE = 32
CAPTCHA_LENGTH = 4
CAPTCHA_TIMEOUT = 5  # 验证码有效期（分钟）
CAPTCHA_NOISE_FUNCTIONS = ('captcha.helpers.noise_dots',)
CAPTCHA_CHALLENGE_FUNCT = 'captcha.helpers.random_char_challenge'
# 验证码方案选择: 'turnstile', 'simple_captcha', 'auto' (自动降级)
CAPTCHA_BACKEND = os.getenv('CAPTCHA_BACKEND', 'auto')

# --- 指定使用我们自己下载的、包含高级功能的 JS 文件 ---
CKEDITOR_5_CUSTOM_JS_URL = 'ckeditor5/ckeditor.js'

# --- 上传相关配置 ---
# 【关键】确保这个 URL 指向我们为 CKEditor 5 专门创建的视图
CKEDITOR_5_UPLOAD_URL = reverse_lazy("ckeditor_image_upload_view")
CKEDITOR_5_CSRF_COOKIE_NAME = "csrftoken"

# --- 自定义颜色面板 (保持不变) ---
customColorPalette = [
    {'color': 'hsl(4, 90%, 58%)', 'label': 'Red'}, {'color': 'hsl(340, 82%, 52%)', 'label': 'Pink'},
    {'color': 'hsl(291, 64%, 42%)', 'label': 'Purple'}, {'color': 'hsl(262, 52%, 47%)', 'label': 'Deep Purple'},
    {'color': 'hsl(231, 48%, 48%)', 'label': 'Indigo'}, {'color': 'hsl(207, 90%, 54%)', 'label': 'Blue'},
    {'color': 'hsl(120, 73%, 45%)', 'label': 'Green'}, {'color': 'hsl(50, 95%, 55%)', 'label': 'Yellow'},
    {'color': 'hsl(25, 95%, 53%)', 'label': 'Orange'}, {'color': 'hsl(0, 0%, 20%)', 'label': 'Dark Gray'},
    {'color': 'hsl(0, 0%, 60%)', 'label': 'Light Gray'},
]

# --- 【核心修改】替换现有的 CKEDITOR_5_CONFIGS ---
CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': ['heading', '|', 'bold', 'italic', 'link'],
    },
    'full': {
        'language': 'zh-cn',

        # 【关键】1. 强制加载 SimpleUploadAdapter 插件
        # 这个插件是实现自定义上传的核心
        'extraPlugins': ['SimpleUploadAdapter'],

        # 【关键】2. 为 SimpleUploadAdapter 提供配置
        # 明确告诉编辑器上传时应该将文件 POST 到哪个 URL
        'simpleUpload': {
            'uploadUrl': CKEDITOR_5_UPLOAD_URL,
            # 'withCredentials': True, # 如果遇到跨域cookie问题可以尝试开启
        },

        # 3. 工具栏和原有其他配置保持不变
        'toolbar': [
            'sourceEditing', '|', 'findAndReplace', 'selectAll', '|',
            'heading', '|', 'bold', 'italic', 'underline', 'strikethrough', 'removeFormat', '|',
            'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor', 'highlight', '|',
            'alignment', '|', 'outdent', 'indent', '|',
            'bulletedList', 'numberedList', 'todoList', 'blockQuote', '|',
            # 确保 'imageUpload' 按钮存在
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
