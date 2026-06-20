# Django App 拆分计划

目标：保持一个 Django project、一个部署入口、一个 Nginx/Gunicorn/Daphne 配置，只按业务域逐步拆成多个 Django app。

## 当前阶段：软拆分

已经先把 Django admin 首页按功能域分组。第一批硬拆已从 `UserNotification` 开始：模型归属迁到 `notifications` app，但继续使用原表 `knowledge_project_usernotification`，避免移动或删除现有数据。

分组方向：

- `accounts`：用户资料、登录设备、信任设备、登录提醒
- `knowledge`：笔记、标签、资源文件
- `messaging`：私信、群聊、群公告、会话设置、群邀请
- `moderation`：举报、处罚、申诉、审核模板
- `notifications`：站内通知、后续邮件队列
- `ops`：后台操作日志、访问安全日志、健康检查

## 下一阶段：代码拆分

优先移动低风险代码，不移动历史模型：

1. 把 `knowledge_project/views/message/` 扩展为 `messaging` 域服务层，保留旧 import shim。
2. 把笔记、文件夹、上传相关视图整理到 `knowledge` 域目录。
3. 把审核 API 和工具函数整理到 `moderation` 域目录。
4. 新增功能的新模型优先放入新 app，旧模型按 `UserNotification` 这种方式逐个迁移。

## 暂缓事项

不要一次性把旧模型类搬到新 app。直接移动模型会改变 `app_label`，容易影响：

- 历史迁移
- Django ContentType
- admin 权限
- 外键引用
- 测试和旧导入路径

如果以后确实要硬迁移旧模型，需要为每个模型单独制定 `db_table`、ContentType/permission 数据迁移和回滚方案。
