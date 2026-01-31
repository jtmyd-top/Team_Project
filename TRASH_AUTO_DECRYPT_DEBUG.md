# 回收站加密笔记自动解密 - 诊断和修复指南

## 问题描述

用户反馈：
- ❌ 回收站列表中的加密笔记标题未自动解密（显示密文）
- ❌ 工具栏中的解密标题在刷新页面后变成密文
- ❌ 需要用户点击后才会解密

## 根本原因分析

### 场景 1：DEK 可用（用户已解锁或 session 恢复）
```
用户进入回收站
    ↓
useVaultEncryption.onMounted() 触发
    ↓
tryRecoverKeyFromSession() 尝试从 Redis 恢复 DEK
    ↓
恢复成功 → dek.value 有值 → isKeyValid.value = true
    ↓
SecondaryPanel watch 执行
    ├─ 检查 dek.value || vaultStore.dek（都有值）
    ├─ 调用 decryptContent() 解密标题
    ├─ 设置 note.decryptedTitle = plainTitle
    ↓
NoteListItem displayTitle 优先使用 note.decryptedTitle
    ↓
列表显示解密后的标题 ✅
```

### 场景 2：DEK 不可用（首次登录，未解锁或 session 过期）
```
用户进入回收站
    ↓
useVaultEncryption.onMounted() 触发
    ↓
tryRecoverKeyFromSession() 失败
    ↓
dek.value = null, isKeyValid.value = false
    ↓
SecondaryPanel watch 执行
    ├─ 检查 dek.value || vaultStore.dek（都是 null）
    ├─ 无法解密，不设置 note.decryptedTitle
    ↓
NoteListItem needsUnlock 计算
    ├─ needsUnlock = is_secret && !isKeyValid && !vaultDek && isInTrash
    ├─ = true && true && true && true = true
    ↓
NoteListItem 显示占位符 🔒 而不是密文 ✅
```

### 问题的关键

**之前的问题**：当 DEK 变为不可用时（session 过期、刷新页面等），已设置的 `note.decryptedTitle` 不会被清除，导致即使 `isKeyValid.value = false` 也会显示解密的标题。

**修复**：添加 watch 监听 `isKeyValid.value`，当它变为 false 时，清除所有 `decryptedTitle`，强制显示占位符。

---

## 实现的修复

### 修复 1：SecondaryPanel.vue - 强制清除不可用时的解密标题

```javascript
// 【新增】监听当 DEK 变为不可用时，清除所有 decryptedTitle
watch(
  () => isKeyValid.value,
  (valid) => {
    if (!valid && sidebarStore.activeModule === 'trash' && !vaultStore.dek) {
      console.log('[SecondaryPanel] DEK became unavailable, clearing decryptedTitles')
      sidebarStore.currentNotes.forEach(note => {
        if (note.is_secret && note.decryptedTitle) {
          delete note.decryptedTitle
        }
      })
    }
  }
)
```

**效果**：
- 当 `isKeyValid.value` 从 true 变为 false（且无备用 DEK）时
- 立即清除所有加密笔记的 `decryptedTitle`
- 这会触发 NoteListItem 的 `needsUnlock = true`
- 显示 🔒 占位符而不是过期的解密标题

### 修复 2：SecondaryPanel.vue - 详细的日志输出

```javascript
watch(
  () => ({
    notes: sidebarStore.currentNotes,
    isTrash: sidebarStore.activeModule === 'trash',
    dek: dek.value,
    vaultDek: vaultStore.dek
  }),
  ({ notes, isTrash, dek: dekValue, vaultDek }) => {
    if (!isTrash) {
      console.log('[SecondaryPanel] Not in trash, activeModule:', sidebarStore.activeModule)
      return
    }

    console.log('[SecondaryPanel] Processing trash notes, DEK available:', !!(dekValue || vaultDek))

    // 对每个笔记都打印详细日志
    notes.forEach(note => {
      console.log('[SecondaryPanel] Note:', note.id, 'is_secret:', note.is_secret, 'decrypted:', !!note.decryptedTitle)
    })
  },
  { deep: true, immediate: true }
)
```

**效果**：
- 提供详细的控制台日志，便于诊断
- 看到 DEK 是否真的不可用
- 看到每个笔记的解密状态

### 修复 3：NoteListItem.vue - 监听 parent 的 decryptedTitle

```javascript
watch(() => props.note.decryptedTitle, (newDecryptedTitle) => {
  console.log('[NoteListItem] parent decryptedTitle updated:', props.note.id)
  // 计算属性自动重新计算
})
```

**效果**：
- 当 SecondaryPanel 设置或清除 `note.decryptedTitle` 时
- NoteListItem 能及时捕捉到变化
- 触发 `displayTitle` 计算属性重新计算

---

## 完整工作流程（修复后）

### 场景：用户刚登录，进入回收站

```
1. 用户登录
   ↓
2. 进入回收站
   ├─ SecondaryPanel onMounted
   ├─ useVaultEncryption.onMounted
   ├─ tryRecoverKeyFromSession()
   │  ├─ 如果 session 有有效 DEK：
   │  │  ├─ dek.value = restored_dek
   │  │  ├─ isKeyValid.value = true ✅
   │  │  └─ SecondaryPanel watch 解密所有标题
   │  └─ 如果 session 无有效 DEK（首次登录、刚登出）：
   │     ├─ dek.value = null
   │     ├─ isKeyValid.value = false
   │     └─ SecondaryPanel watch 无法解密
   ↓
3. 列表渲染
   ├─ 对于加密笔记：
   │  ├─ 如果 note.decryptedTitle 有值：显示明文 ✅
   │  └─ 如果 note.decryptedTitle 无值：
   │     ├─ needsUnlock = true
   │     └─ 显示 🔒 占位符 ✅
   ↓
4. 用户点击 🔒 占位符（如果需要）
   ├─ handleUnlockVault() 触发
   ├─ 打开 2FA 解锁对话框
   ├─ 用户完成验证
   ├─ DEK 加载到内存
   ├─ isKeyValid.value = true
   ├─ SecondaryPanel watch 重新解密
   ├─ note.decryptedTitle 被设置
   └─ 列表自动更新，显示明文 ✅
```

### 场景：用户刷新页面

```
1. 页面刷新
   ├─ isKeyValid.value 重置为 false（在 onMounted 前）
   ├─ vaultStore.dek 被清除（内存中）
   ↓
2. useVaultEncryption.onMounted
   ├─ tryRecoverKeyFromSession()
   ├─ 如果 Redis session 过期：失败
   ├─ dek.value = null
   ├─ isKeyValid.value = false
   ↓
3. SecondaryPanel watch 执行（isKeyValid 从 ? → false）
   ├─ 检测到 isKeyValid.value = false 且无备用 DEK
   ├─ 清除所有 note.decryptedTitle ✅
   ↓
4. 列表重新渲染
   └─ 显示 🔒 占位符（而不是过期的解密标题） ✅
```

---

## 浏览器控制台验证

### 打开浏览器开发者工具（F12）

#### 步骤 1：进入回收站，观察控制台输出

**预期日志 - DEK 可用的情况**：
```
[Vault] Key recovered from session
[SecondaryPanel] Processing trash notes, DEK available: true
[SecondaryPanel] Note: 123 is_secret: true decrypted: false
[SecondaryPanel] ✅ Title decrypted for trash note: 123 我的银行密码
```

**预期日志 - DEK 不可用的情况**：
```
[SecondaryPanel] Processing trash notes, DEK available: false
[SecondaryPanel] Note: 123 is_secret: true decrypted: false
[SecondaryPanel] ⚠️ No DEK available for trash note: 123 - will show masked title
```

#### 步骤 2：检查 needsUnlock 值

```javascript
// 在控制台运行，查看第一个加密笔记的 needsUnlock 状态
// 打开 Vue DevTools，找到 NoteListItem 组件
// 查看 Computed 中的 needsUnlock 值
// 应该是 true（当 DEK 不可用时）
```

#### 步骤 3：点击 🔒 占位符，观察解锁过程

**完成 2FA 后的日志**：
```
[Vault] 2FA verified, DEK updated
[SecondaryPanel] DEK updated, retrying trash note decryption
[SecondaryPanel] ✅ Title decrypted after unlock: 123 我的银行密码
[NoteListItem] parent decryptedTitle updated: 123
```

---

## 测试清单

### 测试 1：DEK 不可用时显示占位符

- [ ] 打开浏览器的隐私模式（无 session cookies）
- [ ] 访问应用，但不进入保密柜（不完成 2FA）
- [ ] 直接进入回收站
- [ ] **验证**：加密笔记显示为 🔒 占位符，而不是密文
- [ ] **验证**：控制台显示 "No DEK available"

### 测试 2：DEK 可用时自动解密

- [ ] 进入保密柜，完成 2FA 验证
- [ ] 切换到回收站
- [ ] **验证**：加密笔记标题自动显示为明文
- [ ] **验证**：控制台显示 "Title decrypted"

### 测试 3：刷新页面后正确处理

- [ ] 在回收站中，DEK 已加载，标题显示明文
- [ ] 刷新页面（F5）
- [ ] **验证**：加密笔记立即显示 🔒 占位符（不是过期的明文）
- [ ] **验证**：控制台显示 "DEK became unavailable"

### 测试 4：点击占位符解锁

- [ ] DEK 不可用的状态下，点击 🔒 占位符
- [ ] **验证**：打开 2FA 解锁对话框
- [ ] 完成验证
- [ ] **验证**：列表自动更新，显示明文标题

### 测试 5：多个加密笔记

- [ ] 回收站中有多个加密笔记
- [ ] DEK 不可用时
- [ ] **验证**：所有加密笔记都显示 🔒 占位符
- [ ] DEK 可用时
- [ ] **验证**：所有加密笔记都自动解密

---

## 常见问题排查

### Q1：仍然看到密文而不是占位符

**可能原因**：
1. `needsUnlock` 条件有问题
2. 模板中的 v-if 未生效
3. Vue 缓存问题

**诊断**：
```javascript
// 在控制台检查 needsUnlock 值
// 应该输出 true（当 DEK 不可用时）
note.is_secret && !isKeyValid.value && !vaultStore.dek && isInTrash.value

// 检查 displayTitle
displayTitle.value
// 应该是 undefined 或空字符串（如果 needsUnlock = true 时不应该使用 displayTitle）
```

**解决**：
1. 清空浏览器缓存（Ctrl+Shift+Delete）
2. 关闭开发者工具后重新打开（刷新 Vue DevTools）
3. 重启浏览器

### Q2：解锁后标题仍未显示

**可能原因**：
1. DEK 恢复失败
2. decryptContent() 抛出异常
3. note.decryptedTitle 未被正确设置

**诊断**：
```javascript
// 检查 dek.value
dek.value  // 应该有值

// 检查 isKeyValid.value
isKeyValid.value  // 应该是 true

// 检查 note.decryptedTitle
note.decryptedTitle  // 应该有解密的标题值

// 手动尝试解密
const { decryptContent } = useClientCrypto()
const plainTitle = decryptContent(encryptedTitle, dek.value)
console.log('Decrypted:', plainTitle)
```

**解决**：
1. 检查浏览器控制台是否有错误
2. 查看 2FA 验证是否真的成功
3. 尝试重新完成 2FA 验证

### Q3：性能问题（解密很慢）

**可能原因**：
- 回收站中有大量加密笔记
- 多个 watch 同时触发解密

**解决**：
```javascript
// 在 SecondaryPanel watch 中添加节流
let debounceTimer = null
watch(
  // ...
  () => {
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      // 执行解密逻辑
    }, 100)
  }
)
```

---

## 验证成功的标志

✅ **完全成功**：
1. DEK 不可用时，列表显示 🔒 占位符（不是密文）
2. DEK 可用时，列表自动显示解密的标题
3. 刷新页面后，占位符正确显示（不是过期的明文）
4. 点击占位符可以打开解锁对话框
5. 完成 2FA 后，标题自动解密更新
6. 浏览器控制台无错误，日志输出符合预期

---

## 相关代码位置

| 文件 | 行数 | 内容 |
|------|------|------|
| SecondaryPanel.vue | 429-448 | DEK 变化 watch |
| SecondaryPanel.vue | 451-491 | currentNotes 变化 watch |
| SecondaryPanel.vue | 493-510 | isKeyValid 变化 watch（新增） |
| NoteListItem.vue | 193-195 | needsUnlock computed |
| NoteListItem.vue | 38-52 | 标题条件渲染 |
| NoteListItem.vue | 316-321 | parent decryptedTitle watch（新增） |

