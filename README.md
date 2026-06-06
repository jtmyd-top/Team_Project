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
- PROJECT_AUDIT_REPORT.md — 自动/人工审计与修复建议（请优先阅读）

---

## 快速开始（开发环境） / Quickstart (Development)

以下步骤假设在 UNIX-like 环境 (Mac/Linux)。Windows 示例另注。

后端（Python / Django）

1. 创建并激活虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\\Scripts\\activate
pip install --upgrade pip
pip install -r requirements.txt
```

2. 复制并编辑环境变量：

```bash
cp .env.example .env
# 编辑 .env，填入 SECRET_KEY、DATABASE_URL、REDIS_URL 等（见 DEPLOYMENT.md）
```

3. 初始化数据库并运行迁移：

```bash
python manage.py migrate
python manage.py createsuperuser  # 可选
python manage.py runserver
```

前端（Node / Vite）

```bash
# 在仓库根目录
npm run install:frontend    # 会进入 frontend/ 并安装依赖
npm run dev                 # 等同于 cd frontend && npm run dev

# 或手动
cd frontend
npm install
npm run dev
```

构建前端用于生产：

```bash
npm run build    # 根目录 script 会把命令代理到 frontend/build
```

静态文件收集（Django）

```bash
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
- DEFAULT_FILE_STORAGE_BACKEND=storages.backends.s3.S3Storage (可选)

注意：不要在仓库中提交包含敏感信息的 .env 文件。

---

## 容器化与部署参考 / Docker & Deployment (example)

下面是一个简单的 docker-compose 示例（仅示例，需按生产安全要求调整）：

```yaml
version: '3.8'
services:
  db:
    image: mysql:8.0
    environment:
      MYSQL_DATABASE: app
      MYSQL_USER: app
      MYSQL_PASSWORD: secret
      MYSQL_ROOT_PASSWORD: rootsecret
    volumes:
      - db_data:/var/lib/mysql

  redis:
    image: redis:7
    command: ["redis-server", "--requirepass", "somepassword"]

  web:
    build: .
    command: daphne -b 0.0.0.0 -p 8000 Team_Project.asgi:application
    volumes:
      - .:/app
    env_file: .env
    depends_on:
      - db
      - redis

  nginx:
    image: nginx:stable
    ports:
      - 80:80
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/nginx.conf:ro
      - static_volume:/app/static
    depends_on:
      - web

volumes:
  db_data:
  static_volume:
```

生产注意事项：使用外部（托管）RDS/云数据库、托管 Redis，设置防火墙/安全组、启用 TLS 并把 SECRET_KEY 与凭据存在安全的密钥管理服务。

---

## 运行测试 / Testing

后端单元/集成测试：

```bash
python manage.py test knowledge_project --settings=Team_Project.settings_test -v 2 --keepdb
```

覆盖率：

```bash
coverage run --source=knowledge_project manage.py test --settings=Team_Project.settings_test
coverage report --fail-under=70
coverage html
```

前端建议使用 Vitest（可选）：

```bash
cd frontend
npm install -D vitest @vue/test-utils
# 添加 test 脚本后运行
npm run test
```

---

## 安全审计摘要（紧急事项） / Security Audit Summary (Urgent)

仓库内的 `PROJECT_AUDIT_REPORT.md` 包含详细审计。关键高优先级问题（请在将服务对外发布前修复）：

1. note 写操作越权：公开笔记可能被任意登录用户修改/删除 → 修复建议：在写操作（PUT/PATCH/DELETE）时强制检查资源作者权限，而不是直接使用仅用于读的权限函数。
2. VaultLockMiddleware 失效：中间件当前逻辑可能永远不会阻止请求 → 修复建议：修正配置字段/判断或移除中间件，改为在敏感接口中显式检查。
3. 关闭 2FA 缺少二次验证：关闭 2FA 时应要求输入 2FA 验证码或备用码。
4. 密码重置未使其他会话失效：重置密码后应清理该用户的其它 session 并发送通知邮件。
5. 注册流程中同步外部头像拉取阻塞：应将外部 HTTP 请求异步化（transaction.on_commit + 后台任务/线程/任务队列）。
6. banner 上传大小上限笔误（1500MB -> 应为 15MB）：修复为合理上限以避免 DoS 上传。

这些项的详细位置与修复建议已写在 `PROJECT_AUDIT_REPORT.md`，请务必优先处理并增加对应的回归测试。

---

## 代码质量与建议 / Code Quality & Suggestions

- 前端：拆分过大的单文件组件（MessagesApp/index.vue 等）、引入 ESLint/Prettier、按需引入 Element Plus 与 ECharts。
- 后端：避免裸 except、拆分超长 views、改进数据库索引（复合索引）、优化并发计数（使用 F() 更新或 Redis）。
- 测试：优先添加 Phase 1 回归测试以覆盖审计中列出的严重问题。

---

## 贡献 / Contributing

欢迎 PR 与 Issue。建议流程：

1. Fork 仓库并新建分支：

```bash
git checkout -b feature/your-feature
```

2. 提交并安装依赖，确保测试通过。
3. 发起 PR，描述变更并关联 issue（若有）。

请为大改动附带测试用例与变更说明。

---

## 许可 / License

当前仓库没有指定 LICENSE 文件。请在决定开源协议后添加 LICENSE（例如 MIT / Apache-2.0 / GPL-3.0）。如需我代为添加常见许可证文本（例如 MIT），我可以在确认后提交。

---

## 常见问题 / FAQ (中英)

Q: 如何把项目运行在生产环境？
A: 参考 DEPLOYMENT.md，建议使用 Nginx 反向代理、多个 Daphne ASGI 实例、共享 Redis、MySQL，静态文件由 Nginx 或 CDN 提供。

Q: 我应先修复哪些安全问题？
A: 见 `PROJECT_AUDIT_REPORT.md` 前几节（紧急安全提醒），尤其要修复笔记越权、Vault 中间件、2FA 与密码重置会话的问题。

---

如需我执行：
- 添加/更新 LICENSE（请指明许可证类型）；
- 在 README 顶部加入徽章（CI、coverage、license、issues）；
- 生成英文独立文件 `README_EN.md`（或保留单文件中中英并列）；
- 增加 Docker Compose 的生产示例（含 systemd/nginx 配置）；
- 根据审计自动创建优先修复的 TODO/Issue 列表并提交到 repo。

告诉我你想先完成哪项，我会继续操作并把变更提交到仓库。