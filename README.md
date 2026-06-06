[![CI](https://img.shields.io/badge/CI-placeholder-lightgrey)](https://example.com)
[![coverage](https://img.shields.io/badge/coverage-placeholder-lightgrey)](https://example.com)
[![license](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![issues](https://img.shields.io/badge/issues-open-lightgrey)](https://github.com/jtmyd-top/Team_Project/issues)

# Team_Project / 团队笔记项目

**创建个人/团队笔记与私信系统。**

This repository contains a full-stack personal/team note-taking application with realtime private messaging and a secure vault feature. The backend is Django (ASGI) and the frontend is a Vue 3 + Vite application.

---

## 目录 / Contents

- 项目概述 / Project Overview
- 主要特性 / Key Features
- 技术栈 / Tech Stack
- 目录结构概览 / Repo Layout
- 快速开始（开发环境） / Quickstart (Development)
- 环境变量 / Environment Variables
- 容器化与部署参考 / Docker & Deployment
- systemd 与 Nginx 生产示例 / systemd & Nginx Production Example
- 运行测试 / Testing
- 安全审计摘要（紧急事项） / Security Audit Summary (Urgent)
- 代码质量与建议 / Code Quality & Suggestions
- 贡献 / Contributing
- 许可 / License
- 常见问题 / FAQ

---

## 项目概述 / Project Overview

中文：
这是一个面向个人和小团队的笔记/知识管理平台，包含笔记（可公开/私密）、私信（支持实时与轮询混合）、保密柜（Vault）与用户管理功能。后端由 Django 提供 API 与 WebSocket（Channels/Daphne），前端为 Vue 3 + Vite + Element Plus。

English:
A note-taking and team-knowledge platform supporting public/private notes, realtime private messaging, and a secure vault. Backend is Django (ASGI) with Channels for websockets; frontend is Vue 3 + Vite + Element Plus.

---

## 主要特性 / Key Features

- 笔记管理：创建、编辑、删除、公开/私密、收藏、标签
- 私信系统：一对一会话、附件、未读计数、实时推送 + 轮询降级
- 保密柜（Vault）：客户端加密/解密、DEK 管理、2FA 保护
- 用户认证：普通登录、邮箱验证码、TOTP/备用码 二次认证方案
- 健康检查：`/healthz`（liveness）与 `/readyz`（readiness）
- 部署友好：静态文件收集、可与 Nginx + CDN 配合

---

## 技术栈 / Tech Stack

- 后端：Python 3.x, Django, Django Channels (ASGI)
- 前端：Vue 3, Vite, Element Plus, Pinia
- 数据库：MySQL / MariaDB（推荐生产使用）
- 缓存与 Channel Layer：Redis
- 构建与运行：Daphne / Nginx / systemd / Docker

---

## 目录结构概览 / Repo Layout

- Team_Project/ — Django 项目配置（settings、middleware、asgi）
- knowledge_project/ — 业务代码（models, views, tests, utils）
- frontend/ — Vue 3 前端应用（Vite）
- DEPLOYMENT.md — 部署与环境变量说明
- PROJECT_AUDIT_REPORT.md — 审计与修复建议（请优先阅读）

---

## 快速开始（开发环境） / Quickstart (Development)

后端（Python / Django）

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\\Scripts\\activate
pip install --upgrade pip
pip install -r requirements.txt
```

复制并编辑环境变量：

```bash
cp .env.example .env
# 编辑 .env，填入 SECRET_KEY、DATABASE_URL、REDIS_URL 等（见 DEPLOYMENT.md）
```

初始化数据库并运行迁移：

```bash
python manage.py migrate
python manage.py createsuperuser  # 可选
python manage.py runserver
```

前端（Node / Vite）

```bash
npm run install:frontend
npm run dev
```

构建前端用于生产：

```bash
npm run build
python manage.py collectstatic --noinput
```

---

## 环境变量 / Environment Variables

请参阅 DEPLOYMENT.md 中的完整清单。关键项示例：

- DJANGO_ENV=production
- SECRET_KEY=your-secret-key
- DEBUG=false
- ALLOWED_HOSTS=example.com,www.example.com
- DATABASE_URL=mysql://user:pass@db-host:3306/dbname
- REDIS_URL=redis://:password@redis-host:6379/1
- CHANNEL_REDIS_URL=redis://:password@redis-host:6379/2

---

## 容器化与部署参考 / Docker & Deployment (example)

见上文 Docker Compose 示例（README_EN 或 README 原始内容中已有基础示例）。下面以更完整的生产级示例补充 systemd 与 Nginx 配置：

### systemd 单机服务示例（daphne）

将以下文件保存为 `/etc/systemd/system/teamproject-web.service`：

```ini
[Unit]
Description=Team_Project Daphne
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/team_project
Environment=DJANGO_ENV=production
EnvironmentFile=/var/www/team_project/.env
ExecStart=/var/www/team_project/.venv/bin/daphne -b 127.0.0.1 -p 8001 Team_Project.asgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable teamproject-web
sudo systemctl start teamproject-web
sudo systemctl status teamproject-web
```

注意：在生产环境中通常会运行多个 Daphne 实例（不同端口或通过 socket），并由 Nginx 进行负载均衡。使用 supervisor 或 systemd template unit `teamproject-web@.service` 可以管理多实例。

### Nginx 配置示例

以下为基本的 Nginx 反向代理配置（放在 `/etc/nginx/sites-available/teamproject` 并启用）：

```nginx
upstream teamproject_backends {
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

server {
    listen 80;
    server_name example.com www.example.com;

    # SSL: 在生产请使用 TLS（证书由 Let's Encrypt 或云提供商管理）

    # 静态与媒体
    location /static/ {
        alias /var/www/team_project/static/;
        expires 30d;
        add_header Cache-Control "public";
    }

    location /media/ {
        alias /var/www/team_project/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # WebSocket / ASGI proxy
    location /ws/ {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_pass http://teamproject_backends;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # 普通 HTTP 代理到 Daphne
    location / {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_pass http://teamproject_backends;
    }

    # 可选：强制 HTTPS 重定向（如果使用 TLS）
}
```

安全与性能注意事项：

- 使用 TLS；设定 HSTS；禁用不安全的 header 转发。
- 使用客户端上传限制与 Nginx 层限制 `client_max_body_size 50M;`。
- 静态和媒体文件使用 CDN 或独立服务器/桶存储（S3）以减轻后端负载。
- WebSocket 长连接需要 Nginx 的 proxy_read_timeout 足够大并允许 `Upgrade`。

---

## 运行测试 / Testing

见上文 Testing 小节（保持一致）。

---

## 安全审计摘要（紧急事项） / Security Audit Summary (Urgent)

请阅读 `PROJECT_AUDIT_REPORT.md`，优先修复报告中指出的高风险问题。仓库中将为高优先级问题创建 Issue 以便跟踪（详见仓库 Issues 列表）。

---

## 代码质量与建议 / Code Quality & Suggestions

见上文（保持一致）。

---

## 贡献 / Contributing

见上文（保持一致）。

---

## 许可 / License

本仓库采用 Apache License 2.0（LICENSE 文件已添加）。

---

## 常见问题 / FAQ (中英)

见上文。
