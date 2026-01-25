# 保密柜智能 UX 流程 - 完整实现指南

## 📋 概述

本文档详细说明了「加入保密柜」时的**两分支智能流程**实现，解决了之前的痛点：
- ❌ **旧问题**：每次操作都弹窗，需要重复验证 2FA
- ✅ **新方案**：检查 DEK 缓存，有就直接加密，没有才验证

---

## 🎯 核心改进

### 问题根源分析

**之前的代码问题**：
```javascript
// ❌ 错误做法
const { dek: dekValue } = useVaultEncryption()  // 创建实例 #1
// ...
const { dek: newDek } = useVaultEncryption()     // 创建实例 #2 （独立）
if (!newDek.value) {
  throw new Error('仍然无法获取加密密钥')  // 新实例中 DEK 为空
}
```

**问题**：每次调用 `useVaultEncryption()` 都创建新的独立实例，DEK 状态不同步

### 解决方案

**✅ 改进方案**：

1. **在组件顶部统一调用 composable**
   ```javascript
   // SecondaryPanel.vue 顶部
   const { dek, isKeyValid, verify2FAAndGetKey } = useVaultEncryption()
   const { encryptContent } = useClientCrypto()
   ```

2. **同时使用 vaultStore 作为备份**
   ```javascript
   // 优先级顺序
   function getAvailableDEK() {
     // 1. 优先从 vaultStore 获取（跨组件同步）
     if (vaultStore.dek && vaultStore.keyExpireTime > Date.now()) {
       return vaultStore.dek
     }
     // 2. 其次从 composable 获取
     if (dek.value && isKeyValid.value) {
       return dek.value
     }
     return null
   }
   ```

3. **同步更新两处 DEK**
   ```javascript
   // useVaultEncryption.js
   async function verify2FAAndGetKey(code, useBackup = false) {
     // ... 验证逻辑
     const expireTime = Date.now() + (data.expire_time * 1000)
     dek.value = data.dek
     keyExpireTime.value = expireTime
     // 【新增】同时更新 vaultStore
     vaultStore.setDEK(data.dek, expireTime)
   }
   ```

---

## 🔀 两分支智能流程

### 流程图

```
用户点击「加入保密柜」
  ↓
[检查] getAvailableDEK()
  ↓
  ├─── 有有效 DEK ───→ 【分支 A: Smart Pass】
  │                 ├─ 直接加密内容
  │                 ├─ 保存密文到后端
  │                 └─ 显示「加入成功」✅
  │
  └─── 没有有效 DEK ──→ 【分支 B: Require Auth】
                     ├─ 撤销 is_secret 标志
                     ├─ 弹出 2FA 验证窗口
                     ├─ 用户输入验证码
                     ├─ 验证成功 → DEK 被更新
                     ├─ 自动继续：重新标记 + 加密
                     └─ 显示「加入成功」✅
```

### 分支 A: Smart Pass（已解锁）

**场景**：用户已验证过 2FA，DEK 缓存仍有效（1800秒内）

**代码流程**：
```javascript
async function executeEncryptAndSave(note) {
  const availableDEK = getAvailableDEK()

  if (availableDEK) {
    // ========== 分支 A: Smart Pass ==========
    console.log('[Vault] Branch A: Smart Pass - Using existing key')
    try {
      await performEncryption(note, availableDEK)
      ElMessage.success('加入保密柜成功！内容已加密')
      await refreshVaultData(note)
    } catch (e) {
      // 错误处理...
    }
  } else {
    // 分支 B...
  }
}
```

**用户体验**：
- ⚡ 无需等待
- 🔇 无弹窗
- ✅ 直接加密

### 分支 B: Require Auth（未解锁）

**场景**：用户没有有效的 DEK（首次使用或已过期）

**代码流程**：

```javascript
else {
  // ========== 分支 B: Require Auth ==========
  console.log('[Vault] Branch B: Require Auth - Need 2FA verification')

  // 1️⃣ 撤销 is_secret，因为加密还未完成
  await revertSecretFlag(note)

  // 2️⃣ 定义待处理的加密操作
  const encryptOperation = async () => {
    // 等待 DEK 被更新（验证成功后）
    const dekForEncryption = await waitForDEK()

    if (!dekForEncryption) {
      throw new Error('未能获取有效的加密密钥')
    }

    // 重新标记为保密笔记
    await toggleSecretAPI(note)

    // 执行加密
    await performEncryption(note, dekForEncryption)
  }

  // 3️⃣ 保存待处理操作
  vaultStore.setPendingOperation(note.id, note.content, encryptOperation)

  // 4️⃣ 弹出验证窗口
  sidebarStore.vaultVerifyDialogVisible = true

  // 5️⃣ 监听验证成功事件
  window.addEventListener('vault-verification-success', async () => {
    // 验证成功 → DEK 已更新 → 自动执行加密操作
    await vaultStore.executePendingOperation()
    ElMessage.success('加入保密柜成功！内容已加密')
  })
}
```

**用户体验**：
- 🔔 弹出 2FA 验证框
- ✍️ 用户输入验证码
- ✅ 验证成功后自动加密（无需再点按钮）

---

## 📁 核心文件改动

### 1. `frontend/src/stores/vault.js`（Pinia Store）

**新增状态**：
```javascript
const dek = ref(null)                    // DEK 缓存
const keyExpireTime = ref(null)          // 过期时间
const vaultInitialized = ref(false)      // 是否已初始化
const pendingOperation = ref(null)       // 待处理操作

// 计算属性
const isUnlocked = computed(() => {
  return dek.value && keyExpireTime.value > Date.now()
})
```

**新增方法**：
```javascript
function setDEK(dekValue, expireTime) {
  dek.value = dekValue
  keyExpireTime.value = expireTime
}

async function checkAndInitVault() {
  // 懒加载初始化保密柜（如果未初始化）
}
```

### 2. `frontend/src/composables/useVaultEncryption.js`

**改进**：
```javascript
import { useVaultStore } from '@/stores/vault'
const vaultStore = useVaultStore()

async function verify2FAAndGetKey(code, useBackup = false) {
  // ... 验证逻辑
  if (data.dek) {
    const expireTime = Date.now() + (data.expire_time * 1000)
    dek.value = data.dek
    keyExpireTime.value = expireTime
    // 【新增】同时更新 vaultStore
    vaultStore.setDEK(data.dek, expireTime)
  }
}
```

### 3. `frontend/src/components/layout/SecondaryPanel.vue`

**顶部导入**（统一实例）：
```javascript
// 在组件顶部，只调用一次
const { dek, isKeyValid, verify2FAAndGetKey } = useVaultEncryption()
const { encryptContent } = useClientCrypto()
```

**新增函数**：
```javascript
// 获取可用的 DEK（双源）
function getAvailableDEK()

// 执行加密并保存（包含两分支逻辑）
async function executeEncryptAndSave(note)

// 加密笔记内容
async function performEncryption(note, dekValue)

// 等待 DEK 更新
async function waitForDEK(timeout = 5000)

// 完整的智能流程
async function handleToggleSecret(note)
```

---

## 🧪 测试场景

### 测试 1: Smart Pass（已验证用户）

**前置条件**：
- 用户已登录
- 已完成 2FA 验证（DEK 在缓存中，未过期）

**操作步骤**：
1. 登录系统
2. 浏览任意笔记列表
3. 右键点击笔记 → 「加入保密柜」

**预期结果**：
- ✅ **无弹窗**出现
- ✅ 笔记立即加入保密柜
- ✅ 控制台显示：`[Vault] Branch A: Smart Pass - Using existing key`
- ✅ 笔记从列表中消失（移入保密柜）

**验证方式**：
```bash
# 检查浏览器开发者工具 - Console
[Vault] Branch A: Smart Pass - Using existing key
[Vault] Content encrypted successfully
```

---

### 测试 2: Require Auth（新用户或已过期）

**前置条件**：
- 新用户刚注册
- 或用户登出再登入（DEK 缓存失效）

**操作步骤**：
1. 登录系统（DEK 缓存为空）
2. 浏览任意笔记列表
3. 右键点击笔记 → 「加入保密柜」

**预期结果**：
- ✅ 弹出 2FA 验证窗口
- ✅ 用户输入验证码
- ✅ 验证成功后 **自动继续** 加密（无需再点按钮）
- ✅ 笔记加入保密柜
- ✅ 控制台显示：
  ```
  [Vault] Branch B: Require Auth - Need 2FA verification
  [Vault] 2FA verified, DEK updated in both composable and store
  [Vault] Content encrypted successfully
  ```

**验证方式**：
```bash
# 控制台查看
[Vault] Branch B: Require Auth - Need 2FA verification
[Vault] 2FA verified, DEK updated in both composable and store
[Vault] Content encrypted successfully
```

---

### 测试 3: DEK 自动恢复

**前置条件**：
- 用户已验证过（DEK 在 Redis）
- 刷新页面

**操作步骤**：
1. 验证 2FA（进入保密柜）
2. 刷新页面 `Ctrl+F5`
3. 打开笔记列表
4. 立即尝试「加入保密柜」

**预期结果**：
- ✅ **无需重新验证** 2FA
- ✅ DEK 自动从 Redis 恢复
- ✅ 笔记直接加密（Smart Pass）
- ✅ 控制台显示：`[Vault] Key recovered from session`

---

## 📊 关键数据流

### DEK 更新流程

```javascript
后端返回 DEK
  ↓
useVaultEncryption() 接收
  ├─ 更新 dek.value
  └─ 更新 keyExpireTime.value
  ↓
同时更新 vaultStore.setDEK()
  ├─ 更新 vaultStore.dek
  └─ 更新 vaultStore.keyExpireTime
  ↓
触发 'vault-verification-success' 事件
  ↓
SecondaryPanel 监听到事件
  ├─ 执行待处理的加密操作
  ├─ 调用 getAvailableDEK()（现在有值）
  └─ 自动加密并保存
```

### DEK 可用性检查

```javascript
getAvailableDEK() {
  // 检查优先级
  if (vaultStore.dek && vaultStore.isUnlocked) {
    return vaultStore.dek  // ✓ 使用 vaultStore
  }

  if (dek.value && isKeyValid.value) {
    return dek.value       // ✓ 使用 composable
  }

  return null              // ✗ 需要验证
}
```

---

## 🔧 调试技巧

### 1. 查看 DEK 状态

```javascript
// 在浏览器 Console 中
console.log('useVaultEncryption dek:', window.__VAULT__.dek)
console.log('vaultStore dek:', window.__VAULT_STORE__.dek)
```

### 2. 监控 pending operation

```javascript
// SecondaryPanel.vue 中的调试
const handleToggleSecret = async (note) => {
  console.log('[DEBUG] Before check:', {
    vaultStoreDEK: vaultStore.dek ? '✓' : '✗',
    composableDEK: dek.value ? '✓' : '✗',
    isKeyValid: isKeyValid.value
  })
  // ...
}
```

### 3. 验证事件触发

```javascript
// 监听所有 vault 相关事件
window.addEventListener('vault-verification-success', (e) => {
  console.log('[DEBUG] vault-verification-success triggered:', e.detail)
})
```

---

## ⚙️ 性能优化

### 1. DEK 缓存时间

```javascript
// 设置在 useVaultEncryption.js 中
// 后端返回 expire_time = 1800（秒）
const expireTime = Date.now() + (data.expire_time * 1000)
```

当前设置为 **1800 秒 = 30 分钟**，可根据需要调整

### 2. waitForDEK() 超时

```javascript
async function waitForDEK(timeout = 5000) {
  // 等待最多 5000ms（5秒）
  // 防止无限期等待
}
```

---

## 🚀 生产部署检查清单

- [x] 前端构建成功 (`npm run build`)
- [x] 后端 API 可用：
  - [x] `/api/vault/status/` - 获取保密柜状态
  - [x] `/api/vault/verify/` - 2FA 验证
  - [x] `/api/vault/key/` - 获取 DEK
  - [x] `/api/notes/{id}/toggle-secret/` - 切换保密状态
  - [x] `/api/notes/{id}/` - 保存加密内容
- [x] vaultStore 已初始化所有用户
- [x] 懒加载初始化已部署 (`checkAndInitVault()`)
- [x] Pinia 配置正确
- [x] 事件监听正常工作

---

## 📝 常见问题

### Q: 为什么有时还是需要验证？
**A**: DEK 有过期时间（1800秒）。如果超过这个时间，需要重新验证一次。

### Q: 验证后仍然加密失败？
**A**: 检查浏览器控制台日志。可能的原因：
1. 笔记内容为空或过大
2. 后端 CSRF token 不匹配
3. 网络连接中断

### Q: 如何手动测试 DEK 恢复？
```bash
# 1. 打开开发者工具 - Application
# 2. 查看 localStorage 中是否有 DEK
# 3. 检查 Redis 中的 vault_session:{user_id}
```

### Q: 可以延长 DEK 缓存时间吗？
**A**: 可以。修改后端 `knowledge_project/views.py` 中的 `vault_verify()` 函数：
```python
# 当前设置
remaining_seconds = 1800  # 30分钟

# 修改为
remaining_seconds = 3600  # 1小时（示例）
```

---

## 🎉 总结

新的智能 UX 流程实现了以下改进：

| 指标 | 旧方案 | 新方案 |
|------|-------|--------|
| **已验证用户** | 每次都弹窗 | ✅ 无弹窗，直接加密 |
| **未验证用户** | 弹窗，需手动重试 | ✅ 自动重试 |
| **代码重用性** | 创建多个 composable 实例 | ✅ 单实例 + vaultStore 同步 |
| **用户体验** | 繁琐 | ✅ 流畅 |
| **DEK 一致性** | 可能不同步 | ✅ 双源同步 |

**状态**：✅ 生产就绪

---

**最后更新**：2026-01-26
**作者**：系统架构
