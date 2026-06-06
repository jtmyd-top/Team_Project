# Nginx配置优化建议

## 完整的Nginx配置示例

```nginx
# /etc/nginx/sites-available/team.03vps.cn

upstream django_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

# HTTP重定向到HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name team.03vps.cn www.team.03vps.cn;
    
    # 强制HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS主配置
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name team.03vps.cn www.team.03vps.cn;

    # SSL证书配置
    ssl_certificate /path/to/your/fullchain.pem;
    ssl_certificate_key /path/to/your/privkey.pem;
    
    # SSL优化
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # 启用HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # 客户端最大上传大小
    client_max_body_size 100M;
    
    # 日志
    access_log /var/log/nginx/team.03vps.cn.access.log;
    error_log /var/log/nginx/team.03vps.cn.error.log;

    # ==================== 静态文件配置（关键优化）====================
    
    # 静态文件 - 启用Gzip和缓存
    location /static/ {
        alias /path/to/Team_Project/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        
        # Gzip压缩
        gzip on;
        gzip_vary on;
        gzip_min_length 1024;
        gzip_types text/css text/javascript application/javascript application/json image/svg+xml;
        gzip_comp_level 6;
        
        # Brotli压缩（如果已安装nginx-brotli模块）
        # brotli on;
        # brotli_comp_level 6;
        # brotli_types text/css text/javascript application/javascript application/json image/svg+xml;
    }
    
    # 媒体文件
    location /uploads/ {
        alias /path/to/Team_Project/knowledge_project/uploads/;
        expires 30d;
        add_header Cache-Control "public";
    }
    
    # 受保护的上传文件（需要Django处理权限）
    location /protected_uploads/ {
        internal;
        alias /path/to/Team_Project/knowledge_project/uploads/;
    }

    # ==================== Django应用代理 ====================
    
    location / {
        proxy_pass http://django_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 连接优化
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # 缓冲设置
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
    
    # WebSocket支持（如果使用Channels）
    location /ws/ {
        proxy_pass http://django_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket超时
        proxy_read_timeout 86400;
    }
}
```

## 应用配置

```bash
# 1. 创建软链接
sudo ln -s /etc/nginx/sites-available/team.03vps.cn /etc/nginx/sites-enabled/

# 2. 测试配置
sudo nginx -t

# 3. 重启Nginx
sudo systemctl restart nginx
```

## 性能测试

```bash
# 测试Gzip是否生效
curl -H "Accept-Encoding: gzip" -I https://team.03vps.cn/static/dist/element-plus.js

# 应该看到：
# Content-Encoding: gzip
```

## 额外优化建议

### 1. 安装Brotli模块（可选，压缩率更高）
```bash
# Ubuntu/Debian
sudo apt install nginx-module-brotli

# 在nginx.conf顶部添加
load_module modules/ngx_http_brotli_filter_module.so;
load_module modules/ngx_http_brotli_static_module.so;
```

### 2. 启用HTTP/2推送（可选）
```nginx
location / {
    http2_push /static/dist/vue-vendor.js;
    http2_push /static/dist/element-plus.js;
    # ... 其他关键资源
}
```

### 3. 配置缓存代理（可选，适合高流量）
```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=django_cache:10m max_size=1g inactive=60m;

location / {
    proxy_cache django_cache;
    proxy_cache_valid 200 5m;
    proxy_cache_key "$scheme$request_method$host$request_uri";
    add_header X-Cache-Status $upstream_cache_status;
    # ... 其他proxy设置
}
```
