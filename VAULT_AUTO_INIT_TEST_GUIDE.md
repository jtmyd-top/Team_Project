# 保密柜自动初始化 - 快速测试指南

## ✅ 已执行的操作

- ✅ 修改了 `models.py` 的 `create_user_profile()` signal
- ✅ 创建了 `init_vault_for_users.py` 管理命令
- ✅ 为所有 22 个现有用户初始化了保密柜
- ✅ Django 系统检查通过（无错误）

---

## 🧪 快速测试

### 测试 1: 查看已初始化用户

```bash
cd "D:\Team Project\Team_Project"
python manage.py shell
```

```python
from knowledge_project.models import Profile

# 检查初始化数量
initialized = Profile.objects.filter(vault_initialized=True).count()
not_initialized = Profile.objects.filter(vault_initialized=False).count()

print(f"已初始化: {initialized}")
print(f"未初始化: {not_initialized}")

# 应该看到：
# 已初始化: 22
# 未初始化: 0
```

### 测试 2: 在浏览器中验证

1. **清除缓存并硬刷新**
   ```
   Ctrl+Shift+Delete → 清除所有
   Ctrl+F5 → 硬刷新
   ```

2. **登录任何已有用户**
   - 例如：username = `test01`

3. **尝试使用保密柜**
   - 点击任意笔记
   - 右键 → 「加入保密柜」
   - ✅ 应该立即加密，无「保险柜未初始化」错误

4. **观察 Console**
   ```
   [Vault] Toggle secret: {...}
   [Vault] Branch A: Smart Pass (如果已验证)
   或
   [Vault] Branch B: Require Auth (如果需要 2FA)
   ```

### 测试 3: 注册新用户

1. **注册新用户**
   - 访问 `/signup/`
   - 填写信息并完成注册

2. **验证自动初始化**
   ```bash
   python manage.py shell
   >>> from knowledge_project.models import User, Profile
   >>> user = User.objects.get(username='newuser')
   >>> user.profile.vault_initialized
   # 应该返回 True
   ```

3. **立即使用保密柜**
   - ✅ 无需手动初始化
   - ✅ 直接可以加入保密柜

---

## 📊 预期结果

### 数据库状态
```
Profile 表:
- vault_initialized: 所有用户都应该是 TRUE
- encrypted_vault_key: 所有用户都应该有值
- vault_key_iv: 所有用户都应该有值
```

### 用户体验
```
【旧】"保险柜未初始化" ❌
【新】直接加密，无报错 ✅
```

### Console 日志
```
[Vault] Content encrypted when adding to vault {plainLength: ..., encryptedLength: ...}
```

---

## ❌ 如果出现问题

### 问题 1: 仍然看到"保险柜未初始化"

**原因**：浏览器缓存或旧数据库状态

**解决**：
```bash
# 重新初始化该用户（如果需要）
python manage.py init_vault_for_users --user-id=<用户ID>

# 浏览器清除缓存
Ctrl+Shift+Delete → 清除所有 → 硬刷新 Ctrl+F5
```

### 问题 2: Signal 初始化失败

**症状**：新用户注册后仍未初始化

**解决**：
```bash
# 检查日志
tail -f /path/to/django.log | grep "Vault"

# 手动初始化
python manage.py init_vault_for_users --user-id=<新用户ID>
```

### 问题 3: 数据库 vault_initialized 字段不存在

**症状**：`OperationalError: no such column: ...vault_initialized`

**解决**：
```bash
# 运行迁移
python manage.py migrate
```

---

## 📈 监控指标

检查系统健康状态：

```bash
python manage.py shell
```

```python
from knowledge_project.models import Profile, User

# 总用户数
total_users = User.objects.filter(is_active=True).count()

# 已初始化 vault 的用户
initialized = Profile.objects.filter(vault_initialized=True).count()

# 初始化率
rate = (initialized / total_users * 100) if total_users > 0 else 0

print(f"总用户: {total_users}")
print(f"已初始化: {initialized}")
print(f"初始化率: {rate:.1f}%")

# 最近创建的 10 个用户的 vault 状态
for user in User.objects.filter(is_active=True).order_by('-date_joined')[:10]:
    status = "✓" if user.profile.vault_initialized else "✗"
    print(f"{status} {user.username}: vault_initialized={user.profile.vault_initialized}")
```

---

## 🎯 验证清单

- [ ] 所有 22 个现有用户的 `vault_initialized = True`
- [ ] 浏览器清除缓存后可以正常使用保密柜
- [ ] 登录不同用户，都能一键加入保密柜
- [ ] 新注册用户自动初始化 vault
- [ ] Console 显示正确的加密日志
- [ ] 没有看到"保险柜未初始化"错误

---

## ✨ 完成标志

当以下条件都满足时，可以认为实现完成：

✅ 数据库中所有用户的 `vault_initialized = True`
✅ 浏览器测试中无"保险柜未初始化"错误
✅ 新用户注册后自动初始化
✅ 加入保密柜时自动加密成功

---

**当前状态**：所有代码改动已完成，22 个用户已初始化，可以开始测试 ✅
