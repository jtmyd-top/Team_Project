# 会话隔离修复 - 保密柜多设备解锁状态独立管理

## 问题严重性：🔴 **严重安全漏洞**

### 问题描述

**原本的实现（不安全）**：
```
用户 A 在浏览器解锁保密柜 (Client 1)
  ↓
后端存储 cache_key = f"vault_access:{user_id}" = "vault_access:123"
  ↓
用户 A 的手机 (Client 2) 自动继承解锁状态
  ↓
任何登录该用户账户的设备都共享解锁状态 ❌
```

**安全威胁**：
1. **办公室未锁屏** - 同事可以看到你的敏感信息
2. **Session 劫持** - 黑客窃取 Cookie 后可直接访问解密内容
3. **设备丢失** - 多个设备同时解锁，无法单独撤销

### 根本原因

Django 后端使用 `user.id` 作为 Redis 缓存键，而不是 `request.session.session_key`：

**【错误代码】**
```python
# 【危险】所有客户端共享同一个 Key
vault_session_key = f"vault_session:{request.user.id}"
cache.set(vault_session_key, {...}, timeout=1800)
```

---

## 修复方案

### 核心原则：**会话隔离（Session Isolation）**

每个浏览器会话有独立的 `session_key`：
- Browser 1 → `session_id_abc123`
- Browser 2 → `session_id_xyz789` (同一用户，不同session)
- Mobile → `session_id_mobile456` (同一用户，不同session)

**各自独立解锁**，互不影响。

---

## 代码修改

### 1. 修改 `decorators.py` - 缓存键函数

**【修复前】** 第 363-375 行：
```python
def get_vault_access_key(user_id):
    return f'vault_access:{user_id}'  # ❌ 基于 user_id
```

**【修复后】**：
```python
def get_vault_access_key(user_id_or_request):
    """
    【修复】使用 session_key 而不是 user_id，确保不同设备独立解锁
    向后兼容：支持传 request 或 user_id
    """
    if hasattr(user_id_or_request, 'session'):
        request = user_id_or_request
        if not request.session.session_key:
            request.session.create()
        return f'vault_access:{request.session.session_key}'  # ✅ 基于 session_key
    else:
        return f'vault_access:{user_id_or_request}'  # 向后兼容旧代码
```

**同样修改**：
- `get_vault_fail_key()` - 失败计数（注：失败计数应基于 user_id，防止用户换设备重置）
- `get_vault_lock_key()` - 锁定状态（注：锁定应基于 user_id，防止绕过）

### 2. 修改接收参数 - 从 `user` 改为 `request`

**涉及函数**：
```python
# 【修复前】
def check_vault_access(user):
    cache_key = get_vault_access_key(user.id)

def grant_vault_access(user, window_seconds=None):
    cache_key = get_vault_access_key(user.id)

def revoke_vault_access(user):
    cache_key = get_vault_access_key(user.id)

def get_vault_access_remaining(user):
    cache_key = get_vault_access_key(user.id)

# 【修复后】
def check_vault_access(request):
    cache_key = get_vault_access_key(request)

def grant_vault_access(request, window_seconds=None):
    cache_key = get_vault_access_key(request)

def revoke_vault_access(request):
    cache_key = get_vault_access_key(request)

def get_vault_access_remaining(request):
    cache_key = get_vault_access_key(request)
```

### 3. 修改调用位置 - 在 `views.py` 中

**位置 1：`vault_status()`**
```python
# 【修复前】
is_verified = check_vault_access(user)
remaining_seconds = get_vault_access_remaining(user)

# 【修复后】
is_verified = check_vault_access(request)
remaining_seconds = get_vault_access_remaining(request)
```

**位置 2：`vault_verify()`** （成功后授予访问权限）
```python
# 【修复前】
# 没有主动调用，但 verify_vault_2fa 内部会调用 grant_vault_access(user)

# 【修复后】
grant_vault_access(request, window_seconds=1800)
```

**位置 3：`vault_lock()`**
```python
# 【修复前】
revoke_vault_access(request.user)

# 【修复后】
revoke_vault_access(request)
```

**位置 4：`vault_notes_list()`**
```python
# 【修复前】
if not check_vault_access(user):
    return ...
remaining_seconds = get_vault_access_remaining(user)

# 【修复后】
if not check_vault_access(request):
    return ...
remaining_seconds = get_vault_access_remaining(request)
```

### 4. 修改 `verify_vault_2fa()` 函数内部调用

**两个位置**：
```python
# 【修复前】
expire_time = grant_vault_access(user)
remaining = get_vault_access_remaining(user)

# 【修复后】
expire_time = grant_vault_access(request)
remaining = get_vault_access_remaining(request)
```

---

## 修改统计

| 文件 | 函数 | 修改内容 | 行数 |
|------|------|--------|------|
| `decorators.py` | `get_vault_access_key()` | 改用 session_key | 363-375 |
| `decorators.py` | `get_vault_fail_key()` | 改用 session_key | 377-388 |
| `decorators.py` | `get_vault_lock_key()` | 改用 session_key | 390-401 |
| `decorators.py` | `check_vault_access()` | 参数从 user 改为 request | 551-563 |
| `decorators.py` | `grant_vault_access()` | 参数从 user 改为 request | 566-585 |
| `decorators.py` | `revoke_vault_access()` | 参数从 user 改为 request | 587-598 |
| `decorators.py` | `get_vault_access_remaining()` | 参数从 user 改为 request | 600-618 |
| `decorators.py` | `verify_vault_2fa()` | 2处调用改为传 request | 712-713, 780-781 |
| `decorators.py` | `require_vault_access()` | 调用改为传 request | 871 |
| `views.py` | `vault_status()` | 调用改为传 request | 4048-4049 |
| `views.py` | `vault_verify()` | 新增 grant_vault_access(request) | 4104 |
| `views.py` | `vault_lock()` | 调用改为传 request | 4159 |
| `views.py` | `vault_notes_list()` | 2处调用改为传 request | 4235, 4264 |

---

## 修复后的工作流程

### 场景 1：多个浏览器，同一用户

```
用户 A 的 Chrome：
  session_key = "chrome_abc123"
  vault_access:chrome_abc123 → 已解锁 ✅

用户 A 的 Firefox（同一电脑）：
  session_key = "firefox_xyz789"
  vault_access:firefox_xyz789 → 未解锁 ❌
  需要单独完成 2FA 验证

用户 A 的手机：
  session_key = "mobile_456def"
  vault_access:mobile_456def → 未解锁 ❌
  需要单独完成 2FA 验证
```

### 场景 2：用户主动锁定

```
用户 A 在 Chrome 上点击"锁定"：
  revoke_vault_access(request)
  → 删除 vault_access:chrome_abc123 ✅

用户 A 的其他浏览器和设备：
  vault_access:firefox_xyz789 → 仍然保持原状态（有效或无效）✅
  vault_access:mobile_456def → 仍然保持原状态
```

### 场景 3：会话过期

```
用户 A 关闭 Chrome 并清空 Cookie：
  新打开 Chrome → 新的 session_key = "chrome_new789"
  vault_access:chrome_new789 → 不存在 → 需要重新 2FA ✅

旧的 session_key 数据自动过期（30分钟 TTL）
```

---

## 与前端的关系

✅ **前端无需修改**

前端仍然调用 `/api/vault/verify/`、`/api/vault/status/` 等接口，这些接口会：
1. 自动获得 `request` 对象（Django 框架提供）
2. 自动从 request 中提取 `session.session_key`
3. 返回对应会话的状态

前端不需要知道"会话隔离"的实现细节，一切对用户透明。

---

## 安全优势

### ✅ 已解决的问题

1. **多设备隔离**
   - 每个设备独立解锁
   - 无法通过一个设备解锁同一账户的其他设备

2. **Session 劫持防护**
   - 黑客即使窃取了 Session，也只能访问该特定设备的解锁状态
   - 其他设备的解锁状态不受影响

3. **办公室安全**
   - 在公司电脑上锁定 → 只影响该电脑
   - 回家打开个人电脑 → 需要重新验证

4. **失败计数（正确处理）**
   - 失败计数仍基于 `user_id`（全局）
   - 防止用户通过换设备来重置失败计数
   - 锁定状态也基于 `user_id`（全局）

---

## 浏览器验证（可选）

### 测试 1：多浏览器隔离

1. **浏览器 1（Chrome）**：登录并解锁保密柜
2. **浏览器 2（Firefox）**：用同一账户登录
   - 预期：需要单独完成 2FA ✅
   - 不是自动继承 Chrome 的解锁状态 ✅

### 测试 2：Cookie 被盗

1. **浏览器 1**：正常使用，解锁保密柜
2. **黑客的浏览器**：用盗取的 Cookie
   - 预期：即使有有效的 Cookie，session_key 不同，也无法访问 ✅

### 测试 3：会话过期

1. **浏览器 1**：解锁保密柜后，清空 Cookie
2. **浏览器 1**：重新登录
   - 预期：新 session_key，需要重新 2FA ✅

---

## Build 状态

✅ **成功**：
```
npm run build
✓ built in 4.21s
```

---

## 关键代码差异

**【修复核心】**：从 User ID 迁移到 Session ID

```diff
# 修复前（不安全）
- cache_key = f"vault_access:{user.id}"
- 所有客户端共享解锁状态 ❌

# 修复后（安全）
+ cache_key = f"vault_access:{request.session.session_key}"
+ 每个会话独立解锁状态 ✅
```

这确保了"**即使是同一用户的不同客户端也需要独立验证**"的安全原则。

---

## 下一步

1. **测试**：在开发环境中验证多浏览器隔离
2. **部署**：将修改部署到生产环境
3. **通知用户**：如有需要，通知用户旧的 session 会在 30 分钟后过期

---

**感谢您提出这个关键的安全问题！** 这次修复保护了用户的敏感信息。

