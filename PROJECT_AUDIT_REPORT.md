# Team_Project 综合审阅报告

> **审阅日期**:2026-05-16
> **审阅范围**:后端 Django 应用、前端 Vue3 应用、安全配置、测试基础设施
> **代码体量**:`models.py` 1445 行 / `views/note.py` 1147 行 / `views/message.py` 2044 行 / 前端 `MessagesApp/index.vue` 4220 行
> **当前分支**:main(最近 5 次提交围绕个人主页、健康检查、合并转发、私信优化)

---

## 目录

1. [紧急安全提醒](#一紧急安全提醒)
2. [严重 bug(必须修复)](#二严重-bug必须修复)
3. [中等问题(建议修复)](#三中等问题建议修复)
4. [前端架构问题](#四前端架构问题)
5. [优化建议](#五优化建议)
6. [自动化测试方案](#六自动化测试方案)
7. [综合评估](#七综合评估)
8. [下一步行动建议](#八下一步行动建议)
9. [附录:文件清单](#附录涉及文件清单)

---

## 一、紧急安全提醒

### 🚨 Redis 密码明文暴露

- `.env` 第 32-33 行(用户已选中)包含:
  ```
  redis=redis://111.119.192.253:6379/1
  redis1=redis://:qaz202019@111.119.192.253:6379/1
  ```
- **已确认**:`.env` 在 `.gitignore` 中,且 `git ls-files` 未追踪,**未泄露至 git 仓库**。
- 但仍需立刻处理:
  1. 密码 `qaz202019` 强度极低,建议立即更换为 ≥ 32 位随机串
  2. Redis 实例 `111.119.192.253:6379` 暴露在公网,**必须**:
     - 配置 `bind` 仅监听内网/127.0.0.1
     - 或在云防火墙加 IP 白名单
     - 启用 Redis 7+ 的 ACL,按用户限权
  3. 已用过的密码假定泄露,无论是否真的入过库

---

## 二、严重 bug(必须修复)

> 以下问题已通过实际读取相关代码片段**逐一验证**,均存在。

### 🔴 #1 `note_detail_api` 写操作越权 ⚠️ **高优先级**

**位置**:
- `knowledge_project/views/note.py:531-535`
- `knowledge_project/models.py:167-170`

**问题**:`note_detail_api` 对 PUT/PATCH/DELETE 三种写方法都只调用了 `note.has_permission(request.user)`,而 `Note.has_permission` 的实现是:

```python
def has_permission(self, user):
    if self.is_public:
        return True       # ← 任何人都可读公开笔记 — 但写也直接放行!
    return self.author == user
```

**实际影响**:**任意登录用户可以修改/删除任何"公开笔记"**(包括他人的)。属于明确的水平越权漏洞,在任何生产环境上线前必须修复。

**修复方向**:
- GET:保持现状(公开笔记任何人可读)
- PUT/PATCH/DELETE:在通过 `has_permission` 后**再判断** `note.author == request.user`,否则 403
- 或:把 `has_permission` 改为接受 `action` 参数,区分读/写

### 🔴 #2 `VaultLockMiddleware` 永远不会拦截

**位置**:`Team_Project/middleware.py:208-284`

**问题**:第 263 行:
```python
if not getattr(profile, 'vault_locked', False):
    return self.get_response(request)
```
- **已验证** `Profile` 模型(`models.py:288`)**没有** `vault_locked` 字段
- `getattr` 默认返回 `False`,导致 `not False == True`,中间件**永远直接 pass**
- 这意味着即使用户在保密柜锁定期间,中间件设计的"未解锁则限制访问其它路径"也完全不生效

**实际影响**:保密柜 30 分钟解锁窗口的整体设计被中间件层架空,只有具体接口里直接调用 `check_vault_access(request)` 的位置才生效。

**修复方向**(取决于业务原意,二选一):
- (A) **移除中间件**:如果实际不需要全站锁(只在敏感接口锁即可)
- (B) **修正判断**:改为
  ```python
  if not profile.two_fa_enabled:
      return self.get_response(request)
  if check_vault_access(request):
      return self.get_response(request)
  ```
  并测试是否会破坏既有登录态体验

### 🔴 #3 `toggle_secret_api` 缺装饰器

**位置**:`knowledge_project/views/note.py:955-998`

**问题**:函数定义没有任何装饰器,而上下文中其它 API(`create_note_api`、`update_note_api`、`delete_note_api`)都有 `@login_required + @require_http_methods(["POST"])`。

**实际影响**(经查证):
- `Note.objects.get(id=note_id, author=user)` 隐式校验了 author,**所以并未导致直接越权**
- 但允许 GET 触发写操作 + 无 CSRF 保护 → CSRF 攻击可能
- 不规范,且与同模块其它 API 风格不一致

**修复方向**:补齐
```python
@login_required
@require_http_methods(["POST"])
@csrf_protect
def toggle_secret_api(request, note_id):
    ...
```

### 🔴 #4 `disable_2fa` 仅需密码即可关闭 2FA

**位置**:`knowledge_project/views/auth/two_factor.py:230-258`

**问题**:用户启用 2FA 后,只需要本人密码就能关闭 2FA。一旦密码泄露,攻击者可直接绕过 2FA。

**实际影响**:削弱 2FA 真实安全价值。**业内通行做法**是关闭 2FA 时也要求 2FA 二次验证。

**修复方向**:在 `profile.two_fa_enabled` 为 True 时,要求请求体里同时提供 `two_fa_code`,并调用 `verify_2fa_for_request(request, two_fa_code, use_backup)` 通过后才允许关闭。

### 🔴 #5 密码重置后未失效其它 session

**位置**:`knowledge_project/views/auth/password_reset.py:197-234`

**问题**:`reset_password_view` 在保存新密码后(line 227-228):
```python
user.set_password(password)
user.save()
```
**没有任何后续动作**:
- 没调用 `update_session_auth_hash` 或者 session flush
- 没用 `Session` 模型清理其它设备的 session
- 没有 email 通知用户密码被重置

**实际影响**:攻击者偷过密码登录后,即使受害者发现并重置了密码,**攻击者已有的 session 仍然有效**,可继续访问数小时(默认 session 时长)。

**修复方向**:
```python
user.set_password(password)
user.save()

# 失效该用户的所有其它 session
from django.contrib.sessions.models import Session
import json
for s in Session.objects.iterator():
    data = s.get_decoded()
    if str(data.get('_auth_user_id', '')) == str(user.id):
        s.delete()

# 发邮件通知(异步)
threading.Thread(
    target=_send_email_async_helper,
    args=('密码已重置', f'您的密码已重置...', [user.email]),
    daemon=True,
).start()
```
(注:`change_password` 在 `auth/password_reset.py:109-111` 已正确处理 `update_session_auth_hash`,但 `reset_password_view` 没复用)

### 🔴 #6 注册流程被外网 HTTP 阻塞

**位置**:`knowledge_project/models.py:907-946`(`create_user_profile` 信号)

**问题**:用户注册时,`post_save User` 信号同步调用 `fetch_avatar(instance)`,内部依次尝试 Libravatar、Gravatar、QQ 邮箱头像三个**外网 HTTP 请求**(`models.py:850-870`)。

**实际影响**:
- 任一外网服务变慢或挂掉 → 注册接口卡死
- 默认 `_http_get` 若没超时控制(需查),可能拖死 worker
- 注册是事务里执行的,长 HTTP 会持有数据库连接

**修复方向**:用 `transaction.on_commit` 延迟到事务后,并用后台线程或 celery:
```python
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile = Profile.objects.create(user=instance)
        # 头像拉取异步化,不阻塞注册
        transaction.on_commit(lambda: threading.Thread(
            target=fetch_avatar, args=(instance,), daemon=True
        ).start())
        # ... 其它初始化
```

### 🔴 #7 banner 上传上限错误

**位置**:`knowledge_project/views/profile.py:88-94`

**问题**:
```python
max_size = 1500 * 1024 * 1024 if is_video else 5 * 1024 * 1024  # = 1.5 GB
max_size_mb = 1500 if is_video else 5
```
**1500 MB ≈ 1.5 GB**,远远超过任何合理 banner 视频上限(常规应为 15-30 MB)。

**实际影响**:
- 单个文件可塞满磁盘
- Nginx/Daphne 上传缓冲也会爆
- 推测原意是 `15 * 1024 * 1024`,被笔误成 `1500 * 1024 * 1024`

**修复方向**:
```python
max_size = 15 * 1024 * 1024 if is_video else 5 * 1024 * 1024
max_size_mb = 15 if is_video else 5
```

---

## 三、中等问题(建议修复)

### 性能 / 并发

| 位置 | 问题 |
|---|---|
| `views/note.py:328-331` | `public_note_view` 浏览量 `views += 1; save()`,并发时丢失计数。改 `Note.objects.filter(pk=...).update(views=F('views')+1)` |
| `views/message.py:723-755` | `_iter_user_sessions` 全表扫描 Session 表,每发条私信调用 1-2 次。**用户量大时会导致 DB 雪崩**,应改为 Redis presence 或 Channels group |
| `views/message.py:1167-1289` | `get_message_conversations_api` 拉取所有相关消息后 Python 端去重,大对话量会爆内存。应改窗口函数 `DISTINCT ON` 或子查询 |
| `models.py:87-100` | `Folder.get_descendants` / `get_notes_count` 递归遍历,深层目录会导致 N+1 |
| `views/note.py:1006`、`views/comment.py:201` | `public_notes_api` / `note_comments_api` 缺分页或缓存,评论数大时一次性拉全表 |

### 数据完整性 / 鲁棒性

| 位置 | 问题 |
|---|---|
| `views/comment.py:127-130` | `_resolve_qqmusic_share_payload` 用 `requests.get(allow_redirects=True)`,白名单只校验首跳。**理论上是 SSRF 风险**,但攻击需在白名单域内有开放重定向 → 实际可利用性低,但应关闭 redirect 或跳转后再校验 |
| `views/profile.py:200-204` | `update_profile` 修改 username **无格式校验**,只判断 `<6` 拒绝;允许特殊字符,与他人重名时抛 `IntegrityError 500` |
| `views/auth/login.py:69-78` `:616-627` | 登录 2FA 邮箱验证码以**明文存入 `request.session['2fa_email_code']`**;应改 cache + hash |

### 代码质量

| 位置 | 问题 |
|---|---|
| `views/note.py:1028,1038,1085`、`auth/login.py:314,373` 等 | 多处**裸 `except:`** 吞掉所有异常(包括 KeyboardInterrupt/SystemExit) |
| `views/note.py:425,485`、`views/profile.py:223` | 生产代码遗留 `print(...)` 调试语句 |
| `views/auth/_shared.py` | `from ._shared import *` 通配导入,污染命名空间 |
| `views/message.py` | 单文件 2044 行,应按 conversation / attachment / report / preference 拆分 |

### 安全控制

| 位置 | 问题 |
|---|---|
| `Team_Project/settings.py` | `CSRF_COOKIE_HTTPONLY` 默认 False(供前端读),但前端通常用 Header,可设 True |
| `Team_Project/middleware.py:75-97`(若有 CSP) | CSP 含 `script-src 'unsafe-inline' 'unsafe-eval'` + 大量第三方域,生产应 nonce 化 |
| `models.py:130-216` `Note` 索引 | 单字段索引(`is_trashed`/`is_favorited`/`is_secret`)冗余,实际查询多与 `author` 联用,应改复合索引 `(author, is_trashed, is_secret)` |

---

## 四、前端架构问题

### 🔴 巨石组件

| 文件 | 行数 | 评估 |
|---|---|---|
| `frontend/src/components/messages/MessagesApp/index.vue` | **4220 行** | 必拆;可读性、热更新性能、可测性都已失控 |
| `frontend/src/entries/public-note-entry.js` | 1284 行 | 在 entry 内塞 `<style>` HTML 字符串,绕开 Vue 抽象 |
| `frontend/src/composables/useKnowledgeList.js` | 945 行 | 应拆为多个职责明确的 composable |
| `frontend/src/composables/useSecondaryPanel.js` | 1318 行 | 同上 |

**MessagesApp 拆分建议**:
```
ConversationsSidebar.vue
ChatHeader.vue
MessageList.vue
Composer.vue
useMessagePolling.js
useMessageSocket.js
```

### 🟡 私信实时机制冗余

`MessagesApp` 同时跑:
- **WebSocket**(含 25s 心跳)
- **45s 轮询** (WS 已连通时本应停)
- **60s 在线上报**

`document.hidden` 只检查上报接口,会话列表轮询页面隐藏时仍在跑 → 移动端电量 + 后端 QPS 浪费。WS 重连指数退避到 15s 上限,**8 次失败后无任何用户提示**。

### 🟡 v-html XSS 风险面较大

以下组件直接 `v-html`,大部分**没走 DOMPurify**(项目已装 dompurify,但仅 `utils/ubb.js` 在用):
- `MessageBubble`
- `ChatSearchDrawer`
- `MessagesApp(全局搜索)`
- `EncryptedNoteContent`
- `public-note-entry.js`(评论/回复直接 `v-html="comment.rendered_content"`)

`MessageBubble.markdownToHtml` 自己用正则识别链接,若后端 `rendered_content` 信任不当或 UBB 渲染被绕过,会留注入面。

### 🟡 工具/请求层重复

| 重复类型 | 重复次数 |
|---|---|
| CSRF Token 获取 | **至少 8 处**(各文件 `document.querySelector` 或 `getCookie`) |
| `formatTime` / `formatDate` | **至少 11 处** |
| 并行的请求封装 | **3 套**(`apiService.js` / `utils/request.js` / `api/note.js`) |

**收敛建议**:抽 `utils/csrf.js`、`utils/datetime.js`、`composables/useFetch.js`,迁移其它调用方,删除冗余两套请求封装。

### 🟡 构建产物偏大

| chunk | 大小 | 原因 |
|---|---|---|
| `chunks/element-plus-3zH3XlIy.js` | **898 KB** | 整包打入,未按需引入 |
| ECharts | 535 KB | 应拆 `echarts/core` + `use()` 按需注册 |
| `messages.js` 入口 | 82 KB | 主要来自 4220 行单组件 |

`chunkSizeWarningLimit: 1000` 提高到 1 MB 是**掩盖问题**,不是解决问题。

### 🟢 依赖管理

- 根 `package.json` 把 `@anthropic-ai/claude-code` 当 `dependencies`,会被部署流程误装 → 应为 devDependency 或移除
- `frontend/package.json` 缺 `eslint` / `prettier` / `vue-tsc`,**无类型/规范护栏**,4000+ 行单文件失控可预见

---

## 五、优化建议

### 后端

1. **`views/message.py` 拆分**:按 conversation / attachment / report / preference / search / export 拆成 6 个文件
2. **重复 `try/except Exception` + `_server_error_response`** 抽装饰器
3. **`decorators.py` 中 vault_* 缓存 key 函数** 6 个高度重复,可参数化
4. **`Note` 索引** 改复合索引 `(author, is_trashed, is_secret)`
5. **`update_profile` username** 修改加正则校验 + 唯一性预检
6. **接口缺 `login_required` 自动检测**:写 management command 遍历 url,统计哪些视图函数缺保护

### 前端

1. **抽公共工具**:csrf / datetime / formatBytes / fetch wrapper
2. **拆分 4 个超大文件**(MessagesApp、public-note-entry、useKnowledgeList、useSecondaryPanel)
3. **WS 已连通时停止轮询**,visibility 变化时统一管理所有定时器
4. **所有 `v-html` 走 DOMPurify**
5. **Element Plus / ECharts 按需引入**
6. **加入 eslint + prettier + vue-tsc**

---

## 六、自动化测试方案

> **现状**:测试基础设施已就绪,但**零测试代码**。可以立即开始落地。

### 现有基础

| 文件 | 状态 |
|---|---|
| `Team_Project/settings_test.py` | ✅ 完整(内存 SQLite + LocMem cache + signed_cookies session + locmem email backend,Turnstile/Channels 已关) |
| `knowledge_project/tests/_helpers.py` | ✅ 已有 `make_user`、`login`、`post_json`、`parse`、`patched_avatar_fetch` |
| `knowledge_project/tests/__init__.py` | ✅ 注释已规划好三大模块 |
| `requirements-dev.txt` | ✅ Playwright 1.55 / Selenium 4.35 / OpenCV / ONNX 都装好了 |

### 测试运行命令

```bash
# 后端单元/集成测试
python manage.py test knowledge_project --settings=Team_Project.settings_test -v 2 --keepdb

# 覆盖率
coverage run --source=knowledge_project manage.py test --settings=Team_Project.settings_test
coverage report --fail-under=70
coverage html  # 生成 htmlcov/ 目录可视化
```

### 推荐测试文件结构

```
knowledge_project/tests/
├─ __init__.py              [已有]
├─ _helpers.py              [已有]
├─ test_auth.py             [新建] 登录/注册/密码/2FA/限流
├─ test_note.py             [新建] 笔记 CRUD + 跨用户权限
├─ test_message.py          [新建] 私信/屏蔽/偏好/对话
├─ test_folder.py           [新建] 文件夹/回收站
├─ test_vault.py            [新建] 保密柜锁/解锁/2FA
├─ test_comment.py          [新建] 评论/回复/删除
├─ test_security.py         [新建] CSRF/login_required 批量检查
└─ test_decorators.py       [新建] 备用码消费/TOTP 重放保护
```

### 优先级测试用例清单

#### Phase 1:覆盖严重 bug 的回归测试(配合修复同步落地)

| 测试用例 | 验证哪个 bug |
|---|---|
| `test_note.py::test_public_note_cannot_be_edited_by_others` | #1 越权 |
| `test_note.py::test_public_note_cannot_be_deleted_by_others` | #1 越权 |
| `test_note.py::test_toggle_secret_requires_login_and_post` | #3 装饰器 |
| `test_vault.py::test_vault_lock_middleware_blocks_when_locked` | #2 中间件 |
| `test_auth.py::test_disable_2fa_requires_2fa_code` | #4 关 2FA |
| `test_auth.py::test_password_reset_invalidates_other_sessions` | #5 session 残留 |
| `test_profile.py::test_banner_upload_rejects_over_15mb` | #7 banner 上限 |

#### Phase 2:核心业务流程覆盖

| 测试文件 | 关键用例 |
|---|---|
| `test_auth.py` | 注册成功 / 重复用户名 / 弱密码 / 登录成功 / 密码错锁定 / 2FA 流程 / 备用码消费 + 重放保护 / 密码重置 token 一次性 / 邮箱修改 op2fa |
| `test_note.py` | CRUD 全流程 / 跨用户访问私有笔记 = 403 / 回收站保密笔记不返回 content / 浏览量并发(模拟) / 公开笔记搜索 |
| `test_message.py` | 发送 / 屏蔽后发送被拒 / 偏好为 following-only 被拒 / 对话列表分组 / 未读数 / 阅后即焚 purge_at 到期不返回 / 附件上传 → 举报 → review |
| `test_folder.py` | 创建/嵌套/移动/还原/永久删除 / 移动到他人文件夹 = 403 |
| `test_vault.py` | vault_init / verify / lock-status / 设备级 3 次失败锁 60s / 账户级 5 次失败锁 24h / 邮箱告警 |
| `test_security.py` | IP 24h 内 10 次失败自动 ban / 接口缺 login_required 批量检测 / CSRF 缺失批量检测 |

#### Phase 3:E2E 测试(Playwright)

```
e2e/
├─ test_login_flow.py        # captcha + 2FA + 备用码
├─ test_note_e2e.py          # 创建 → 公开 → 评论 → 收藏
├─ test_message_e2e.py       # 双开浏览器 WS 实时收信
└─ conftest.py               # 启动 daphne + 浏览器 fixture
```

#### Phase 4:前端单测(可选)

```bash
npm install -D vitest @vue/test-utils @vitest/coverage-v8
```

优先盖:
- `useKnowledgeList.js`(945 行 composable)
- `utils/ubb.js`(UBB 转 HTML 的 DOMPurify 边界)
- 抽出的 `utils/csrf.js` / `utils/datetime.js`

### CI 集成

`.github/workflows/test.yml` 三步矩阵:

```yaml
jobs:
  lint:
    - flake8 knowledge_project Team_Project
    - npm --prefix frontend run lint  # 待 eslint 接入后
  unit-test:
    - python manage.py test --settings=Team_Project.settings_test
    - coverage report --fail-under=70
  e2e:
    - playwright install chromium
    - python manage.py runserver_plus 0.0.0.0:8000 &
    - pytest e2e/
```

### 工作量估计

| 阶段 | 用例数 | 单人工作量 |
|---|---|---|
| Phase 1(回归测试) | 7 个 | 0.5 天 |
| Phase 2(后端 80 用例) | 80 个 | 4-5 天 |
| Phase 3(E2E 4 个流程) | 4 个 | 1.5 天 |
| Phase 4(前端单测) | 20-30 个 | 1-2 天 |
| CI 接入 | - | 0.5 天 |
| **合计** | **110+** | **7-9 天 → 60-70% 覆盖率** |

---

## 七、综合评估

| 维度 | 评级 | 说明 |
|---|---|---|
| 功能完整度 | ⭐⭐⭐⭐⭐ | 远超普通课程项目,接近产品级 |
| 安全控制点设计 | ⭐⭐⭐⭐ | 2FA、Vault、Turnstile、设备/IP/账户三级锁、ECDH 都到位 |
| 安全实现完整性 | ⭐⭐⭐ | 存在多个 critical 实现遗漏(权限、Vault 中间件等) |
| 后端架构 | ⭐⭐⭐⭐ | views 拆分合理,但单文件仍偏大 |
| 前端架构 | ⭐⭐ | 4000+ 行单组件、三套请求层、工具重复 8 次 |
| 测试覆盖 | ⭐ | 脚手架到位,**零测试代码** |
| 文档完整度 | ⭐⭐⭐ | 有 DEPLOYMENT.md,代码内中文注释丰富 |
| **生产就绪度** | ⭐⭐⭐ | **修完 🔴 区 + 加上测试后可上线** |

### 已经做得很好的地方

- ✅ `views/` 已按业务域拆分(auth/captcha/comment/dashboard/message/note/profile/stats/upload/vault/follow)
- ✅ 2FA 实现完整:TOTP + Email + 备用码 + 重放保护(`decorators.py:78-92`)
- ✅ 保密柜 ECDH 握手 + DEK 包装(`utils/vault_crypto.py` + `utils/vault_handshake.py`)
- ✅ 设备/IP/账户三级失败计数 + 自动 ban IP
- ✅ Turnstile + 图形验证码 + PoW 验证码
- ✅ 测试基础设施(`settings_test.py` + `_helpers.py`)已经搭好
- ✅ `.env` 正确 gitignore
- ✅ 健康检查端点 `/healthz` `/readyz`(部署友好)
- ✅ 中文注释覆盖率高,新成员容易上手

### 主要风险点

- ❌ **`note_detail_api` 越权**:能让用户互相破坏内容
- ❌ **`VaultLockMiddleware` 失效**:保密柜锁的核心机制被架空
- ❌ **`disable_2fa` 无 2FA**:削弱整体 2FA 价值
- ❌ **密码重置不失效旧 session**:违反账户安全基线
- ❌ **零测试**:任何后续改动都可能引入回归

---

## 八、下一步行动建议

### 推荐顺序(已与用户确认)

```
Week 1
├─ 修复 🔴 区 7 个严重 bug              ← 当前阶段
└─ 同步写 Phase 1 的 7 个回归测试用例

Week 2
├─ 落地 Phase 2 后端核心测试(80 用例)
└─ 中等问题中的"性能"项(并发计数、N+1)

Week 3
├─ 前端拆分 MessagesApp/index.vue
├─ 抽 utils/csrf.js / datetime.js
└─ Phase 3 E2E 测试

Week 4
├─ CI 接入
├─ 覆盖率提升至 70%
└─ DOMPurify 全面接入 v-html 路径
```

### 不建议做的事

- ❌ 现在再加新业务功能(已经过载)
- ❌ 大改 views 层架构(增量改即可)
- ❌ 引入新 UI 框架/状态管理库
- ❌ 接入新第三方服务

---

## 附录:涉及文件清单

### 后端关键文件

| 文件 | 行数 | 功能 |
|---|---|---|
| `knowledge_project/models.py` | 1445 | 所有数据模型 + 信号 |
| `knowledge_project/views/note.py` | 1147 | 笔记 CRUD + 公开访问 + 评论 |
| `knowledge_project/views/message.py` | 2044 | 私信全部功能 |
| `knowledge_project/views/auth/` | - | 登录/注册/2FA/密码重置子包 |
| `knowledge_project/views/vault.py` | - | 保密柜 |
| `knowledge_project/decorators.py` | 713 | 2FA / 保密柜装饰器 |
| `Team_Project/middleware.py` | 285+ | CSP / IP ban / Vault lock 中间件 |
| `Team_Project/settings.py` | - | 全局配置 |
| `Team_Project/settings_test.py` | 68 | 测试专用配置 ✅ |

### 前端关键文件

| 文件 | 行数 | 功能 |
|---|---|---|
| `frontend/src/components/messages/MessagesApp/index.vue` | **4220** | 私信主组件 |
| `frontend/src/entries/public-note-entry.js` | 1284 | 公开笔记入口 |
| `frontend/src/composables/useKnowledgeList.js` | 945 | 笔记列表 composable |
| `frontend/src/composables/useSecondaryPanel.js` | 1318 | 二级面板 composable |

### 测试基础设施

| 文件 | 状态 |
|---|---|
| `Team_Project/settings_test.py` | ✅ 完整 |
| `knowledge_project/tests/_helpers.py` | ✅ 完整 |
| `knowledge_project/tests/__init__.py` | ✅ 已规划 |
| `requirements-dev.txt` | ✅ 含 Playwright + Selenium |
| **测试代码本身** | ❌ **0 个测试文件** |

---

## 附录:本次审阅未覆盖的内容

为节省审阅时间,以下内容未深入(可后续补充):

- `frontend/src/components/` 下未提及的零散组件
- `knowledge_project/admin.py` 与 `admin_auth.py` 的管理后台
- `knowledge_project/consumers.py` 与 `routing.py` 的 Channels 实现细节
- `staticfiles/` 与 CDN 配置
- 数据库迁移本身的可逆性(0001-0027)
- `DEPLOYMENT.md` 部署文档与生产配置的一致性

---

**审阅人**:Claude(Opus 4.7,1M context)
**审阅工具**:Read / Grep / Glob / Explore Agent
**报告生成时间**:2026-05-16
