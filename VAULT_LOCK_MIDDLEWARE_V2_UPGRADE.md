# 保密柜锁定中间件 v2.0 升级说明

**更新时间**: 2026-01-25
**版本**: v2.0
**文件**: `Team_Project/middleware.py` (VaultLockMiddleware)

---

## 问题分析

### 之前存在的安全隐患：Zombie Session（殭屍会话）

#### 场景描述
当用户的保密柜被锁定时：

1. **用户操作**
   - 用户点击"登出"按钮
   - 前端删除 Cookie 和本地 Token
   - 浏览器跳转到登录页面
   - **用户以为已安全登出** ✓

2. **实际发生的事情**
   - POST /logout/ 请求被中间件拦截
   - Django 的 logout() 视图函数无法执行
   - 服务器的 Session 未被销毁
   - 攻击者盗取的 Token 仍然有效（直到自然过期）
   - **隐患：假性登出 (Fake Logout)** ✗

#### 术语
- **假性登出**: 前端清除了凭证，但后端会话未销毁
- **殭屍会话**: 无人使用但仍然有效的会话
- **会话泄露**: 攻击者可以使用盗取的会话进行操作

#### 风险示例
```
时间线：
T1: 攻击者 XSS 注入盗取用户 sessionid
T2: 用户发现异常，点击"登出"
T3: 前端清除 Cookie，跳转登录页
T4: 用户：✅ "我现在安全了"
T5: 攻击者：🎯 仍然可以使用盗取的 sessionid（因为后端没销毁）
T6: 用户密码被改、邮箱被改...
```

---

## 解决方案：写入操作白名单

### 核心改动

在 `VaultLockMiddleware` 中添加 **WRITE_METHOD_WHITELIST**：

```python
WRITE_METHOD_WHITELIST = [
    ('POST', '/logout'),              # 真正销毁会话
    ('POST', '/api/logout/'),         # API 版本的登出
    ('POST', '/forgot-password/'),    # 启动密码重置流程
    ('POST', '/api/password-reset/'), # API 版本的密码重置
    ('POST', '/api/2fa/resend-email/'), # 重发2FA邮件
    ('GET', '/api/password-reset/'),  # 获取重置状态
]
```

### 执行流程

**之前的流程（有隐患）**
```
用户请求 POST /logout/
    ↓
中间件检查：用户被锁定 → 返回 403 Forbidden
    ↓
Django logout() 视图未执行
    ↓
Session 未销毁 ✗
```

**现在的流程（安全）**
```
用户请求 POST /logout/
    ↓
中间件检查：用户被锁定 → 继续检查
    ↓
检查是否在写入白名单中 → 是 (POST /logout/)
    ↓
允许请求通过 ✓
    ↓
Django logout() 视图执行
    ↓
Session 被销毁 ✓
```

---

## 代码变更详情

### 1. 添加白名单配置（第125-137行）

```python
# 白名单：允许的 POST/PUT/PATCH/DELETE 操作（即使被锁定也可以执行）
WRITE_METHOD_WHITELIST = [
    ('POST', '/logout'),
    ('POST', '/api/logout/'),
    ('POST', '/forgot-password/'),
    ('POST', '/api/password-reset/'),
    ('POST', '/api/2fa/resend-email/'),
    ('GET', '/api/password-reset/'),
]
```

### 2. 修改 __call__ 方法（第174-201行）

添加白名单检查逻辑，在阻止操作前优先检查：

```python
def __call__(self, request):
    # ... 之前的检查 ...

    if self._is_user_locked(request.user.id):
        # ✨ 新增：检查是否在写入操作白名单中
        if self._is_write_method_whitelisted(request.method, path):
            logger.info(f"✅ 用户被锁定，但 {request.method} {path} 在白名单中，允许执行")
            return self.get_response(request)

        # ... 其他检查 ...
```

### 3. 新增方法 _is_write_method_whitelisted（第217-230行）

```python
def _is_write_method_whitelisted(self, method, path):
    """检查是否是写入操作白名单中的方法"""
    path_stripped = path.rstrip('/')

    for whitelisted_method, whitelisted_path in self.WRITE_METHOD_WHITELIST:
        if (method == whitelisted_method and
            (path == whitelisted_path or path_stripped == whitelisted_path)):
            return True

    return False
```

---

## 白名单项说明

| 方法 | 路径 | 目的 | 为什么需要白名单 |
|-----|------|------|-----------------|
| POST | /logout | 销毁服务器会话 | 防止 Zombie Session，真正登出 |
| POST | /api/logout/ | API 版本登出 | 防止 Zombie Session (JSON API) |
| POST | /forgot-password/ | 启动密码重置 | 允许用户重置密码以解除锁定 |
| POST | /api/password-reset/ | API 密码重置 | 允许通过 API 重置密码 |
| POST | /api/2fa/resend-email/ | 重发2FA邮件 | 在锁定时仍能获得验证码 |
| GET | /api/password-reset/ | 检查重置状态 | 查询密码重置流程状态 |

---

## 安全验证

### ✅ 这样修改是安全的吗？

**是的**，因为：

1. **白名单很小且具体**
   - 只有6个操作
   - 都是"解锁"相关操作
   - 不涉及数据读写

2. **不会绕过数据保护**
   - 笔记、文件夹、设置仍被保护
   - 只有身份验证相关操作放行
   - 用户无法在锁定时修改数据

3. **防止了更大的安全隐患**
   - 旧方案：前端登出成功，后端会话活跃 ✗
   - 新方案：前端后端都登出，彻底销毁会话 ✓

4. **仍然实施最小权限原则**
   ```
   允许操作：登出、密码重置、2FA重发
   阻止操作：一切数据操作（读写）
   ```

### 风险矩阵

| 场景 | 之前 | 之后 | 改进 |
|------|------|------|------|
| 用户点击登出 | ⚠️ 假性登出 | ✅ 真正登出 | +100% |
| 攻击者盗取 Token | ⚠️ 仍然有效 | ✅ 无法使用 | +100% |
| 用户被锁定时读笔记 | ✗ 阻止 | ✗ 阻止 | 不变 |
| 用户被锁定时改数据 | ✗ 阻止 | ✗ 阻止 | 不变 |
| 用户被锁定时重置密码 | ✓ 允许 | ✓ 允许 | 不变 |

---

## 测试建议

### 1. 单元测试

```python
def test_logout_allowed_when_vault_locked():
    """测试：保密柜被锁定时仍允许登出"""
    # 1. 锁定用户的保密柜
    lock_vault(user.id)

    # 2. 尝试 POST /logout/
    response = client.post('/logout/')

    # 3. 验证：
    assert response.status_code == 302  # 重定向到登录
    assert 'sessionid' not in client.cookies  # Session 被删除
```

### 2. 集成测试

```python
def test_zombie_session_prevention():
    """测试：防止殭屍会话"""
    # 1. 创建会话
    login_response = client.post('/login/', {...})
    session_id = get_session_id(login_response)

    # 2. 锁定用户
    lock_vault(user.id)

    # 3. 登出
    logout_response = client.post('/logout/')

    # 4. 验证：盗取的 session_id 无法使用
    response = client.get('/api/notes/', cookies={'sessionid': session_id})
    assert response.status_code == 403  # 会话已销毁
```

### 3. 安全测试

```python
def test_whitelist_prevents_data_access():
    """测试：白名单不会绕过数据保护"""
    lock_vault(user.id)

    # 这些操作仍被阻止：
    assert client.get('/api/notes/').status_code == 403
    assert client.post('/api/notes/create/', {...}).status_code == 403
    assert client.put('/api/notes/1/update/', {...}).status_code == 403

    # 只有白名单项被允许：
    assert client.post('/logout/').status_code in (200, 302)
```

---

## 日志输出

修改后，日志会显示：

```
✅ VaultLockMiddleware: 用户 123 被锁定，但 POST /logout/ 在白名单中，允许执行
[已完成] Session 被销毁
用户 123 已安全登出
```

vs 之前：

```
🔒 VaultLockMiddleware: 用户 123 被锁定，阻止写入操作: POST /logout/
返回 403 Forbidden
⚠️ 警告：会话未被销毁
```

---

## 迁移说明

### 升级步骤

1. ✅ 已修改 `Team_Project/middleware.py`
2. 重启 Django 开发服务器或应用 WSGI 服务
3. 验证日志中出现新的白名单日志
4. 测试被锁定用户是否能正常登出

### 兼容性

- ✅ 不破坏现有 API
- ✅ 不改变请求/响应格式
- ✅ 完全向后兼容
- ✅ 可在任何时间应用

---

## 相关代码位置

| 文件 | 行号 | 内容 |
|-----|------|------|
| `Team_Project/middleware.py` | 65-103 | 类文档注释（已更新） |
| `Team_Project/middleware.py` | 125-137 | WRITE_METHOD_WHITELIST 配置 |
| `Team_Project/middleware.py` | 174-201 | __call__ 方法（已修改） |
| `Team_Project/middleware.py` | 217-230 | _is_write_method_whitelisted 方法（新增） |

---

## 结论

此更新通过引入**写入操作白名单**解决了保密柜锁定状态下的 Zombie Session 安全隐患。

### 改进点
- ✅ 用户可以真正登出（后端会话被销毁）
- ✅ 盗取的 Token 在登出后无法使用
- ✅ 防止攻击者继续访问用户账户
- ✅ 保持了数据保护的完整性

### 安全提升
```
Session 安全性：不安全 → 安全
登出功能：部分失效 → 完全有效
会话泄露风险：高 → 低
```

**建议部署在生产环境前进行完整测试。**

---

**文档版本**: 1.0
**最后更新**: 2026-01-25
**维护者**: Security Team
