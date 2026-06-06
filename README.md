# Team_Project

创建个人/团队笔记项目。

> 说明：仓库包含后端（Django）与前端（Vue 3 + Vite）两部分。根目录的 package.json 为前端代理脚本，实际前端代码位于 `frontend/` 目录。

## 主要特性

- 笔记（Note）创建、编辑、公开/私密控制
- 私信（Message）系统（含实时与轮询机制）
- 保密柜（Vault）与 2FA 支持
- 用户注册、头像抓取与个人资料管理
- 健康检查端点 `/healthz` 与 `/readyz`

## 技术栈

- 后端：Python, Django, Channels (ASGI)
- 前端：Vue 3, Vite, Element Plus
- 数据库：MySQL (部署建议)
- 缓存/消息：Redis

## 快速开始（开发环境）

先安装后端依赖：

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 可选：开发依赖
pip install -r requirements-dev.txt
```

准备环境变量（示例）：

- 请参考 `DEPLOYMENT.md` 中推荐的环境变量清单（如 SECRET_KEY、DATABASE_URL、REDIS_URL 等）。

运行后端（开发模式）：

```bash
# 在仓库根目录
python manage.py migrate
python manage.py runserver
```

前端开发：

```bash
# 在根目录可直接代理前端脚本
npm run install:frontend
npm run dev
# 或进入 frontend/ 目录直接运行
cd frontend
npm install
npm run dev
```

构建前端产物：

```bash
npm run build        # 根目录会调用 frontend 内的 build 脚本
# 或者直接在 frontend/ 下运行： npm run build
```

## 运行测试

后端单元/集成测试（示例）：

```bash
python manage.py test knowledge_project --settings=Team_Project.settings_test -v 2 --keepdb
```

覆盖率示例：

```bash
coverage run --source=knowledge_project manage.py test --settings=Team_Project.settings_test
coverage report --fail-under=70
coverage html
```

前端单测（可选）：

```bash
# 在 frontend/ 中
npm install -D vitest @vue/test-utils @vitest/coverage-v8
# 配置后运行
npm run test
```

## 部署要点

推荐拓扑：

`Nginx / Cloud Load Balancer -> 多个 ASGI 实例 -> MySQL + Redis`

- 使用 `python manage.py collectstatic` 将静态文件收集到 `STATIC_ROOT`，由 Nginx 或 CDN 对外提供静态资源
- 媒体文件建议使用对象存储（例如 S3），避免节点本地磁盘作为长期存储
- 会话、限流、Channel layer 等需要使用共享后端（Redis）
- 部署前运行 `python manage.py check --deploy` 并确认 `/readyz` 返回 200

更详细的部署配置与环境变量请参见仓库中的 DEPLOYMENT.md。

## 已知重要安全问题（请优先查看并修复）

本仓库包含一份详细的审计报告：`PROJECT_AUDIT_REPORT.md`，其中列出了若干高优先级问题。特别提醒：

- note 写权限越权（公开笔记当前可能允许任意登录用户修改/删除）
- VaultLockMiddleware 逻辑失效（保密柜中间件未按预期工作）
- 关闭 2FA 时缺少二次验证
- 密码重置后未失效其他会话

请在将项目推向生产前务必阅读并修复 `PROJECT_AUDIT_REPORT.md` 中的“紧急安全提醒”部分。

## 代码风格与质量建议

- 前端建议引入 ESLint / Prettier / vue-tsc 并拆分过大的组件（例如 MessagesApp/index.vue）
- 后端建议拆分过长的 view 文件、添加更多单元测试并修复审计中提到的裸 except、并发问题与索引优化

## 贡献

欢迎提交 issue 或 PR。建议流程：

1. Fork 仓库并新建分支：git checkout -b feature/xxx
2. 提交代码并保证已通过相应的测试
3. 发起 Pull Request，描述变更与关联 issue（如有）

## 联系与许可

项目所有者: jtmyd-top

仓库描述: 创建个人/团队笔记项目

（本仓库未主动包含开源许可证文件。如需对外开源或商业使用，请添加 LICENSE 文件并在 PR 中说明。）

---

如需我把 README 调整为英文版本或加入徽章、示例截图与常见问题（FAQ），我可以继续补充。