# 🔒 生产环境安全配置检查清单

## ⚠️ 部署前必须完成

在将应用部署到生产环境之前，请确保完成以下配置：

### 1. 环境变量配置

复制 `.env.example` 为 `.env` 并修改以下关键配置：

```bash
# 必须修改的配置
DJANGO_ENV=production
DEBUG=False
SECRET_KEY=<生成新的密钥>
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
```

生成新的 SECRET_KEY：
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 2. HTTPS 和 Cookie 安全

```bash
# 启用 HTTPS（需要配置 SSL 证书）
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True

# 启用 HSTS（HTTP 严格传输安全）
SECURE_HSTS_SECONDS=31536000  # 1年
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=False  # 谨慎启用，一旦启用很难撤销
```

### 3. 数据库和 Redis

```bash
# 使用强密码
mysql_passwd=<强密码>
REDIS_URL=redis://:password@host:6379/1

# 生产环境禁用缓存异常忽略
CACHE_IGNORE_EXCEPTIONS=False
```

### 4. CSRF 可信源

```bash
# 必须包含所有允许的域名（包括协议）
CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

### 5. 反向代理配置（如使用 Nginx）

```bash
TRUST_X_FORWARDED_PROTO=True
USE_X_FORWARDED_HOST=True
USE_X_FORWARDED_PORT=True
TRUSTED_PROXY_CIDRS=10.0.0.0/8  # 根据实际代理IP配置
```

### 6. WebSocket / Channels

```bash
# 生产环境必须使用 Redis Channel Layer
REALTIME_MESSAGES_ENABLED=True
REQUIRE_SHARED_CHANNEL_LAYER=True
CHANNEL_REDIS_URL=redis://:password@host:6379/2
```

## 📋 部署检查

运行 Django 安全检查：
```bash
python manage.py check --deploy
```

应该看到所有检查通过（或只有合理的警告）。

## 🔐 安全最佳实践

1. **永远不要提交 .env 文件到 Git**
   - 已在 `.gitignore` 中配置
   - 定期检查 `git status` 确保未追踪

2. **定期轮换密钥**
   - SECRET_KEY 每季度更换
   - 数据库密码定期更新
   - API 密钥定期刷新

3. **监控和日志**
   - 启用应用性能监控（APM）
   - 配置日志聚合系统
   - 设置异常告警

4. **备份策略**
   - 数据库每日自动备份
   - 媒体文件定期备份
   - 测试备份恢复流程

## 🚀 快速部署指南

### 方法 1：使用 Docker（推荐）

```dockerfile
# 创建 Dockerfile（待添加）
# docker-compose.yml（待添加）
```

### 方法 2：传统部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 收集静态文件
python manage.py collectstatic --noinput

# 3. 运行数据库迁移
python manage.py migrate

# 4. 创建超级用户
python manage.py createsuperuser

# 5. 启动应用（使用 Gunicorn + Daphne）
# WSGI (HTTP)
gunicorn Team_Project.wsgi:application --bind 0.0.0.0:8000 --workers 4

# ASGI (WebSocket)
daphne -b 0.0.0.0 -p 8001 Team_Project.asgi:application
```

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /path/to/staticfiles/;
    }

    location /uploads/ {
        alias /path/to/uploads/;
    }
}
```

## ⚡ 性能优化

1. **启用 HTTP/2**
2. **配置 Gzip 压缩**
3. **启用浏览器缓存**
4. **使用 CDN 分发静态资源**
5. **数据库连接池优化**
6. **Redis 持久化配置**

## 📞 故障排查

### 常见问题

1. **500 错误**
   - 检查 `DEBUG=False` 时是否配置了 `ALLOWED_HOSTS`
   - 查看日志文件排查具体错误

2. **静态文件 404**
   - 确保运行了 `collectstatic`
   - 检查 Nginx 静态文件路径配置

3. **WebSocket 连接失败**
   - 确认 Daphne 正在运行
   - 检查 Nginx WebSocket 代理配置

4. **Session 丢失**
   - 确认 Redis 正常运行
   - 检查 `SESSION_COOKIE_SECURE` 配置

## 📚 相关文档

- [Django 部署检查清单](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [Django 安全配置](https://docs.djangoproject.com/en/4.2/topics/security/)
- [Channels 部署指南](https://channels.readthedocs.io/en/stable/deploying.html)
