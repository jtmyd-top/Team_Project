# 智能 UX 流程 - 快速测试指南

## ✅ 立即测试

### 步骤 1: 清除缓存
```bash
按 Ctrl+Shift+Delete
→ 清除所有数据
→ 关闭标签页
```

### 步骤 2: 硬刷新
```bash
按 Ctrl+F5（硬刷新）
或 Ctrl+Shift+R
```

---

## 🧪 测试 A: Smart Pass（无弹窗）

**前置条件**：
- 用户已登录
- 刚完成一次 2FA 验证（比如访问保密柜列表）

**测试步骤**：
1. 打开「全部笔记」列表
2. 在 Console 中看到：`[Vault] Key recovered from session`
3. 右键点击任意笔记 → 「加入保密柜」
4. **观察**：无弹窗，直接成功

**期望 Console 输出**：
```
[Vault] Using DEK from vaultStore
[Vault] Branch A: Smart Pass - Using existing key
[Vault] Content encrypted successfully {plainLength: XXX, encryptedLength: YYY}
```

✅ **成功标志**：笔记立即从列表消失，进入保密柜

---

## 🧪 测试 B: Require Auth（自动重试）

**前置条件**：
- 新打开浏览器标签页
- 或登出再登入
- **DEK 缓存完全清空**

**测试步骤**：
1. 登录系统
2. 打开「全部笔记」列表
3. **不要访问保密柜**（这样 DEK 不会被恢复）
4. 右键点击笔记 → 「加入保密柜」

**期望行为**：
1. 弹出 2FA 验证窗口 ← **关键！无需用户再操作**
2. 用户输入验证码
3. 验证成功后 **自动继续加密** ← **最关键改进**
4. 笔记自动进入保密柜

**期望 Console 输出**：
```
[Vault] Branch B: Require Auth - Need 2FA verification
[Vault] 2FA verified, DEK updated in both composable and store
[Vault] Content encrypted successfully {plainLength: XXX, encryptedLength: YYY}
```

✅ **成功标志**：验证码输入成功后，自动完成加密，无需额外操作

---

## 🧪 测试 C: 移出保密柜

**步骤**：
1. 访问「保密柜」
2. 右键点击保密笔记 → 「移出保密柜」

**期望结果**：
- ✅ 无需验证
- ✅ 笔记立即移出（不加密）
- ✅ 显示「移出保密柜成功」

---

## 🐛 调试命令

### 查看当前 DEK 状态
```javascript
// 在浏览器 Console 中运行
// 1. 查看 vaultStore 中的 DEK
window.__VAULT_STORE__ = undefined  // 先检查 Pinia 实例

// 2. 快速测试 getAvailableDEK()
console.log('[DEBUG] vaultStore.dek:', window.$pinia?.state?.value?.vault?.dek ? '✓ 有值' : '✗ 无值')
```

### 强制清除 DEK
```javascript
// 模拟 DEK 过期
localStorage.removeItem('vault_dek')
sessionStorage.clear()
// 然后刷新页面
```

### 查看事件触发
```javascript
// 监听验证成功事件
window.addEventListener('vault-verification-success', (e) => {
  console.log('[DEBUG] Event received:', e.detail)
})
```

---

## 📊 对比：旧 vs 新

### 旧流程 ❌
```
用户点击「加入保密柜」
  ↓
弹窗 2FA 验证
  ↓
用户输入验证码
  ↓
验证成功，弹窗关闭
  ↓
❌ 用户需要再点一次「加入保密柜」
  ↓
才能开始加密
```

### 新流程 ✅
```
用户点击「加入保密柜」
  ↓
[检查] 有 DEK 缓存吗?
  ├─ YES ──→ 直接加密，完成 ✅ (Smart Pass)
  │
  └─ NO ──→ 弹窗 2FA 验证
           ↓
           用户输入验证码
           ↓
           验证成功 + DEK 更新
           ↓
           ✅ 自动继续加密，完成 (Require Auth)
```

---

## ⚠️ 常见问题排查

### 问题 1：总是弹窗
**症状**：每次都需要 2FA 验证

**原因**：
- [ ] DEK 已过期（超过 1800 秒）
- [ ] 浏览器 localStorage/sessionStorage 被清除
- [ ] Redis session 丢失

**解决**：
```bash
# 检查 Redis 中的 vault_session 是否存在
redis-cli get "vault_session:{user_id}"
# 应该返回有效的 DEK JSON

# 如果不存在，用户需要重新验证一次
```

### 问题 2：验证后仍然加密失败
**错误信息**：`加密失败: 未能获取有效的加密密钥`

**原因**：DEK 更新没有同步到 getAvailableDEK()

**排查步骤**：
```javascript
// 在 console 中查看
// 1. 验证是否收到了验证成功事件
window.addEventListener('vault-verification-success', () => {
  console.log('[DEBUG] Event OK')
})

// 2. 检查 vaultStore 是否被更新
console.log('vaultStore.dek:', window.$pinia?.state?.value?.vault?.dek)

// 3. 检查 useVaultEncryption 中的 dek 是否被更新
// (需要在 SecondaryPanel.vue 中添加调试代码)
```

### 问题 3：页面刷新后需要重新验证
**现象**：刷新后 DEK 丢失

**预期行为**：应该从 Redis 自动恢复

**排查**：
```bash
# 检查后端 /api/vault/key/ 是否返回有效的 DEK
curl -X GET http://localhost:8000/api/vault/key/ \
  -H "Cookie: sessionid=..."

# 应该返回
# {"status": "success", "dek": "...", "expire_time": 1800}
```

---

## 🔍 关键代码位置

| 文件 | 函数 | 作用 |
|------|------|------|
| `SecondaryPanel.vue` | `getAvailableDEK()` | 获取可用的 DEK（双源） |
| `SecondaryPanel.vue` | `executeEncryptAndSave()` | 执行两分支智能逻辑 |
| `SecondaryPanel.vue` | `performEncryption()` | 实际执行加密 |
| `SecondaryPanel.vue` | `waitForDEK()` | 等待 DEK 更新（轮询） |
| `useVaultEncryption.js` | `verify2FAAndGetKey()` | 2FA 验证 + DEK 更新 |
| `vault.js` (Pinia) | `setDEK()` | 保存 DEK 到 store |

---

## 📈 期望的 Console 日志

### Smart Pass 场景
```
[Vault] Using DEK from vaultStore
[Vault] Branch A: Smart Pass - Using existing key
[Vault] Content encrypted successfully {plainLength: 500, encryptedLength: 752}
加入保密柜成功！内容已加密
```

### Require Auth 场景
```
[Vault] Branch B: Require Auth - Need 2FA verification
[Vault] Using DEK from useVaultEncryption
[Vault] 2FA verified, DEK updated in both composable and store
[Vault] Content encrypted successfully {plainLength: 500, encryptedLength: 752}
加入保密柜成功！内容已加密
```

---

## 🎯 验收标准

| 功能 | 测试 | 结果 |
|------|------|------|
| Smart Pass | 验证后立即操作 | ✅ 无弹窗，直接加密 |
| Require Auth | 新会话操作 | ✅ 弹窗 + 自动重试 |
| 自动恢复 | 刷新页面 | ✅ DEK 自动恢复 |
| 时间过期 | 等待 1800秒后 | ✅ 需要重新验证 |
| 错误处理 | 网络故障 | ✅ 正确提示错误 |

---

## 🚀 部署检查清单

运行以下命令确保一切就绪：

```bash
# 1. 检查前端是否重新构建
ls -lh D:\Team\ Project\Team_Project\static\dist\knowledge-list.js
# 应该显示最新的修改时间

# 2. 验证 Python 依赖（如果有更新）
pip list | grep -i crypto

# 3. 检查数据库状态
python manage.py shell -c "
from knowledge_project.models import Profile
print(f'总用户: {Profile.objects.count()}')
print(f'已初始化: {Profile.objects.filter(vault_initialized=True).count()}')
"

# 4. 验证后端 API
curl -X GET http://localhost:8000/api/vault/status/ \
  -H "Cookie: sessionid=..." \
  -H "X-CSRFToken: ..."

# 应该返回
# {"status": "success", "two_fa_enabled": true/false, ...}
```

---

## 💡 优化建议

### 1. 增加 DEK 缓存时间
```python
# knowledge_project/views.py - vault_verify()
remaining_seconds = 1800  # 改为 3600 (1小时)
```

### 2. 添加 loading 提示
```javascript
// executeEncryptAndSave() 中
ElMessage.loading('加密中...')
// 完成后关闭
```

### 3. 支持批量加入保密柜
```javascript
// 未来扩展：选中多个笔记后
// 一次性加密多个
```

---

**最后更新**：2026-01-26
