# 会话记录 —— 私信安全硬化 + 关注/邮件/未读角标

**日期**：2026-04-19
**分支**：main
**计划文件**：`C:\Users\xingrunxie\.claude\plans\fizzy-chasing-tome.md`

---

## 1. 用户需求（原文精简）

### 1.1 核心底线：禁止模糊搜索下拉列表
> 不要做"输入 a 就展示所有带 a 的用户名"——典型 **用户枚举漏洞**。
> 正确做法：用户必须输入完全正确的用户名/UUID/邮箱，点击搜索后才展示唯一匹配卡片。

### 1.2 主要入口：基于上下文的自然触发
> 公开笔记 / 评论区 / 贡献者列表 里点击头像 → 用户卡片 → 发私信按钮。

### 1.3 隐私开关
> 在个人资料设置页增加开关：**"允许通过用户名搜索到我"**。
> 关闭后哪怕输入 100% 正确的用户名，后端也返回"查无此人"。

### 1.4 风控限流
> 限制每天主动向 N 个陌生人发起新对话（比如 5 个），超限触发 Turnstile。

### 1.5 附加需求
1. 公开笔记界面新增 **关注/订阅** 功能
2. 用户收到私信可通过 **邮箱接收**（可选项，设置页开启）
3. 登录后未读私信需要在 `#userDropdown` 里私信菜单项旁提示，**角标样式跟右上角角标一致**

---

## 2. 决策问答结果

| 决策点 | 用户选择 |
|---|---|
| 搜索匹配字段 | username / email / search_code 三路 iexact |
| `discoverable_by_username` 默认 | **False**（最严格） |
| 每日新对话限额 | 5 个，超限触发 Turnstile |
| 邮件通知频率 | 聚合，15 分钟最多一封 |

---

## 3. 探索分析成果

### 3.1 关键现状
- `knowledge_project/views/message.py:836 search_users_api` 当前使用 `username__icontains`，需重写。
- `frontend/src/components/messages/NewMessageDialog/index.vue:18` 是 `@input` 实时搜索。
- `knowledge_project/models.py` **没有** Follow/Subscribe 模型。
- `MessagePreference.notify_new_message` 字段存在但**未实际发邮件**。
- `knowledge_project/utils/smart_email_sender.py:17 SmartEmailSender` 可复用。
- `knowledge_project/utils/turnstile.py:119 verify_turnstile_token` 可复用。
- `knowledge_project/templates/base.html:86-111` 用户下拉 `#userDropdown` 的私信菜单无角标。
- Frontend settings 已有 `SettingsPrivacy` 组件 + `useSettingsPrivacy.js`，需扩展。
- `PublicNoteView/index.vue:56-77` 作者信息区是关注按钮的落点。
- 统一 Badge 样式参考：`ConversationItem/index.vue:235 .unread-badge`。

### 3.2 已读取的文件
- `knowledge_project/views/message.py` (完整 863 行)
- `knowledge_project/models.py` (完整 1215 行)
- `knowledge_project/urls.py` (完整)
- `knowledge_project/templates/base.html` (完整)
- `knowledge_project/utils/turnstile.py` (完整 181 行)
- `knowledge_project/views/__init__.py`
- `frontend/src/components/messages/NewMessageDialog/index.vue`
- `frontend/src/components/messages/MessagesApp/index.vue`
- `frontend/src/components/common/UserCardModal/index.vue`
- `frontend/src/components/knowledge/PublicNoteView/index.vue`
- `frontend/src/components/settings/SettingsApp/index.vue`
- `frontend/src/components/settings/SettingsPrivacy/index.vue`
- `frontend/src/composables/useSettingsPrivacy.js`

---

## 4. 已落地的改动（本会话）

### 4.1 `knowledge_project/models.py`
1. **Profile 类** 新增三个字段（紧跟通知偏好块）：
   ```python
   discoverable_by_username = BooleanField(default=False, ...)
   discoverable_by_email    = BooleanField(default=False, ...)
   search_code              = CharField(max_length=12, unique=True, null=True, blank=True, db_index=True)
   ```

2. **MessagePreference 类** 新增：
   ```python
   last_email_notified_at = DateTimeField(null=True, blank=True, ...)
   ```

3. **新增 `UserFollow` 模型**：
   - `follower` / `following` 双 ForeignKey
   - `unique_together = ('follower','following')`
   - 两个索引

4. **新增 `NewConversationQuotaLog` 模型**：
   - `user` / `peer` / `created_at` / `turnstile_passed`
   - 索引 `(user, -created_at)`

5. **`create_user_profile` signal** 扩展：为新用户自动生成 8 位 `search_code`（字母数字大写，冲突重试 5 次）。

### 4.2 迁移
尚未执行 `python manage.py makemigrations` — 下次会话恢复后第一步就是执行并应用迁移。

---

## 5. 已写入但未实施的剩余任务

### 5.1 后端
- [ ] 改写 `search_users_api`（`message.py:835-856`）为 iexact 三路精准搜索
- [ ] `send_message_api` 增加新对话限流 + Turnstile 校验
- [ ] `send_message_api` 末尾调用 `_maybe_send_new_message_email`（15 分钟聚合）
- [ ] 新增 `get_unread_messages_count_api`
- [ ] 新建 `knowledge_project/views/follow.py`（follow / unfollow / follow-status）
- [ ] 新建 `update_discoverability_api`（或在 profile.py 扩展）
- [ ] `urls.py` 注册五个新端点
- [ ] `views/__init__.py` 加 `from .follow import *`

### 5.2 前端
- [ ] `NewMessageDialog/index.vue` 重写：按钮触发精准搜索 + 空结果中性文案 + Turnstile 兜底
- [ ] `MessagesApp/index.vue:sendMessage` 捕获 `need_turnstile: true` 走 Turnstile
- [ ] `SettingsPrivacy/index.vue` + `useSettingsPrivacy.js` 增加可发现性分区与 search_code 复制
- [ ] `PublicNoteView/index.vue` + `usePublicNoteView.js` 加关注按钮
- [ ] `UserCardModal/index.vue` 加关注按钮
- [ ] `base.html` 私信菜单项增加 `<span id="navUnreadBadge">` + DOM ready 后 30 s 轮询 `/api/messages/unread-count/`
- [ ] CSS 样式 `.nav-unread-badge`（放 `static/css/modern-base.css` 或新建）

### 5.3 构建
- [ ] `npm run build` 重新生成 `static/dist/`

---

## 6. 任务清单状态

| # | 状态 | 任务 |
|---|---|---|
| 2 | in_progress | 模型与迁移 |
| 6 | pending | 搜索/限流/邮件/未读 API |
| 7 | pending | 关注 API + 可发现性端点 |
| 8 | pending | NewMessageDialog 精准搜索 |
| 3 | pending | SettingsPrivacy 扩展 |
| 4 | pending | PublicNoteView / UserCardModal 关注按钮 |
| 5 | pending | base.html 未读角标 |
| 1 | pending | npm run build |

---

## 7. 恢复下一步

1. 先在 Django 项目根目录运行：
   ```
   python manage.py makemigrations knowledge_project
   python manage.py migrate
   ```
2. 若 migration 命名不是 `0019_...`，按实际文件名记录即可，不影响功能。
3. 检查现有用户的 `Profile.search_code` 是否为空（migration 不会回填老用户）—— 可写一次性 data migration 或 Django shell 脚本：
   ```python
   from knowledge_project.models import Profile
   import secrets, string
   abc = string.ascii_uppercase + string.digits
   for p in Profile.objects.filter(search_code__isnull=True):
       while True:
           code = ''.join(secrets.choice(abc) for _ in range(8))
           if not Profile.objects.filter(search_code=code).exists():
               p.search_code = code; p.save(update_fields=['search_code']); break
   ```
4. 继续 **5. 已写入但未实施的剩余任务** 按顺序推进。

---

## 8. 关键复用清单

| 需求 | 复用资产 | 位置 |
|---|---|---|
| Turnstile 校验 | `verify_turnstile_token` | `knowledge_project/utils/turnstile.py:119` |
| 发邮件 | `SmartEmailSender` | `knowledge_project/utils/smart_email_sender.py:17` |
| 头像 URL 工具 | `_get_avatar_url` | `knowledge_project/views/message.py:27` |
| CSRF token | `document.querySelector('[name=csrfmiddlewaretoken]').value` | 现有模式 |
| Badge 样式 | `.tab-badge` / `.unread-badge` | `MessagesApp/index.vue:1112`、`ConversationItem/index.vue:235` |
