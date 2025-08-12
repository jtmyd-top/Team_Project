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
]


# --- 4. 中间件和 URL 配置 ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'Team_Project.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')], # 建议添加一个项目级的模板目录
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
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# --- 7. 静态文件和媒体文件 (关键修正) ---
STATIC_URL = 'static/'
# 【修正】STATICFILES_DIRS 应该指向项目根目录下的 'static' 文件夹
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
# 【新增】运行 collectstatic 后，所有静态文件会被收集到这里
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/uploads/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'uploads')


# --- 8. 认证、缓存、邮件 (清理重复项) ---
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        # 格式: redis://:密码@主机:端口/数据库编号
        # 如果Redis和Django运行在同一台服务器上，主机就是127.0.0.1
        "LOCATION": os.getenv('redis1'),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
            # 增加一个密码选项，更明确
            "PASSWORD": os.getenv('mysql_passwd'),
        }
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


# ==============================================================================
# 9. CKEditor 5 增强版完整配置 (现在是唯一的编辑器配置)
# ==============================================================================

# --- 指定使用我们自己下载的、包含高级功能的 JS 文件 ---
CKEDITOR_5_CUSTOM_JS_URL = 'ckeditor5/ckeditor.js'

# --- 上传相关配置 ---
CKEDITOR_5_UPLOAD_URL = reverse_lazy("ckeditor_5_upload_file") # Django-ckeditor-5 自带上传处理
CKEDITOR_5_CSRF_COOKIE_NAME = "csrftoken"

# --- 自定义颜色面板 ---
customColorPalette = [
    {'color': 'hsl(4, 90%, 58%)', 'label': 'Red'}, {'color': 'hsl(340, 82%, 52%)', 'label': 'Pink'},
    {'color': 'hsl(291, 64%, 42%)', 'label': 'Purple'}, {'color': 'hsl(262, 52%, 47%)', 'label': 'Deep Purple'},
    {'color': 'hsl(231, 48%, 48%)', 'label': 'Indigo'}, {'color': 'hsl(207, 90%, 54%)', 'label': 'Blue'},
    {'color': 'hsl(120, 73%, 45%)', 'label': 'Green'}, {'color': 'hsl(50, 95%, 55%)', 'label': 'Yellow'},
    {'color': 'hsl(25, 95%, 53%)', 'label': 'Orange'}, {'color': 'hsl(0, 0%, 20%)', 'label': 'Dark Gray'},
    {'color': 'hsl(0, 0%, 60%)', 'label': 'Light Gray'},
]

CKEDITOR_5_CONFIGS = {
    'default': { # 保留一个简单的默认配置
        'toolbar': ['heading', '|', 'bold', 'italic', 'link'],
    },
    'full': {
        'language': 'zh-cn',
        # 【重要】这里的工具栏按钮必须与你下载的自定义 ckeditor.js 文件包含的插件完全对应
        'toolbar': [
            'sourceEditing', '|', 'findAndReplace', 'selectAll', '|',
            'heading', '|', 'bold', 'italic', 'underline', 'strikethrough', 'removeFormat', '|',
            'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor', 'highlight', '|',
            'alignment', '|', 'outdent', 'indent', '|',
            'bulletedList', 'numberedList', 'todoList', 'blockQuote', '|',
            'link', 'imageUpload', 'insertTable', 'mediaEmbed', 'horizontalLine', 'specialCharacters', 'pageBreak',
        ],
        'image': {'toolbar': ['imageTextAlternative', '|', 'imageStyle:alignLeft', 'imageStyle:alignRight', 'imageStyle:alignCenter', 'imageStyle:side', '|', 'linkImage']},
        'table': {'contentToolbar': ['tableColumn', 'tableRow', 'mergeTableCells', 'tableProperties', 'tableCellProperties'], 'tableProperties': {'borderColors': customColorPalette, 'backgroundColors': customColorPalette}, 'tableCellProperties': {'borderColors': customColorPalette, 'backgroundColors': customColorPalette}},
        'heading': {'options': [{'model': 'paragraph', 'title': 'Paragraph', 'class': 'ck-heading_paragraph'}, {'model': 'heading1', 'view': 'h1', 'title': 'Heading 1', 'class': 'ck-heading_heading1'}, {'model': 'heading2', 'view': 'h2', 'title': 'Heading 2', 'class': 'ck-heading_heading2'}]},
        'fontColor': {'colors': customColorPalette},
        'fontBackgroundColor': {'colors': customColorPalette},
        'alignment': {'options': ['left', 'right', 'center', 'justify']},
    }
}