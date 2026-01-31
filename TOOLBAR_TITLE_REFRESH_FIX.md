# 工具栏标题刷新后变密文 - 完整修复

## 问题症状

用户刷新页面后，工具栏（预览区）中的加密笔记标题从**明文变成密文**：

```
刷新前：我的银行密码 ✅ (明文显示)
  ↓
按 F5 刷新页面
  ↓
刷新后：jfsasl6YpVoL+AGk9... ❌ (密文显示)
  ↓
需要再点击笔记才能重新解密
```

---

## 根本原因分析

### 问题 1：`handleNoteSelect` 中的解密逻辑过于简陋

**文件**：`KnowledgeList.vue` 第 372-375 行

```javascript
// 【修复前】有问题的代码
if (currentNoteData.value.is_secret && isKeyValid.value) {
  await decryptNoteTitle()
} else {
  decryptedTitle.value = ''  // ❌ 这里会清除已有的解密标题！
}
```

**问题**：
- 当用户刷新页面时，`isKeyValid.value` 暂时为 false
- 代码进入 else 分支
- 执行 `decryptedTitle.value = ''` 清除解密标题
- 即使 DEK 后来恢复成功，也不会重新解密

### 问题 2：`decryptNoteTitle` 没有检查备用 DEK

**文件**：`KnowledgeList.vue` 第 315 行

```javascript
// 【修复前】只检查 dek.value
if (!isKeyValid.value || !dek.value) {
  console.warn('[Vault] Cannot decrypt title: no valid DEK')
  decryptedTitle.value = ''
  return
}
```

**问题**：
- 当 `isKeyValid.value = false` 时，直接返回
- 没有尝试使用 `vaultStore.dek` 作为备用
- 刷新页面时 session 可能还在，但 `isKeyValid.value` 被重置

### 问题 3：watch 监听逻辑有缺陷

**文件**：`KnowledgeList.vue` 第 894-902 行

```javascript
// 【修复前】缺陷
watch(() => isKeyValid.value, async (valid) => {
  if (valid && ...) {
    await decryptNoteTitle()  // ✅ 这个没问题
  } else if (!valid && currentNoteData.value.is_secret) {
    decryptedTitle.value = ''  // ❌ 这里会清除，不会检查 vaultStore.dek
  }
})
```

**问题**：
- 没有监听 `dek.value` 的变化
- 只能在 `isKeyValid.value` 改变时才触发，但 `dek.value` 可能独立变化
- 没有处理 `vaultStore.dek` 的备用情况

---

## 完整修复

### 修复 1：改进 `handleNoteSelect` 的解密逻辑

**文件**：`KnowledgeList.vue` 第 364-385 行

```javascript
// 如果是加密笔记，尝试解密标题（同时检查 isKeyValid 和 vaultStore.dek）
if (currentNoteData.value.is_secret) {
  if (isKeyValid.value || vaultStore.dek) {
    // 有 DEK 时解密
    await decryptNoteTitle()
  } else {
    // 没有 DEK 时不清除已有的解密标题（可能是刷新过程中）
    console.log('[KnowledgeList] No DEK available for secret note:', currentNoteData.value.id)
  }
} else {
  // 非加密笔记，清除解密标题
  decryptedTitle.value = ''
}
```

**改进点**：
- ✅ 同时检查 `isKeyValid.value` 和 `vaultStore.dek`
- ✅ 不清除已有的解密标题（避免刷新时闪烁）
- ✅ 添加调试日志

### 修复 2：增强 `decryptNoteTitle` 的 DEK 检查

**文件**：`KnowledgeList.vue` 第 300-340 行

```javascript
async function decryptNoteTitle() {
  // ... 前面的检查 ...

  // 【修复】尝试同时检查 dek.value 和 vaultStore.dek
  const dekToUse = dek.value || vaultStore.dek

  if (!dekToUse) {
    console.warn('[Vault] Cannot decrypt title: no valid DEK', {
      hasKeyValid: isKeyValid.value,
      hasDek: !!dek.value,
      hasVaultDek: !!vaultStore.dek
    })
    decryptedTitle.value = ''
    return
  }

  try {
    // 【修复】使用 dekToUse 而不是 dek.value
    const plainTitle = decryptContent(currentNoteData.value.title, dekToUse)
    decryptedTitle.value = plainTitle
    console.log('[Vault] Title decrypted successfully in KnowledgeList:', currentNoteData.value.id)
  } catch (e) {
    console.warn('[Vault] Failed to decrypt title:', e.message)
    decryptedTitle.value = ''
  }
}
```

**改进点**：
- ✅ 尝试 `dek.value || vaultStore.dek` 双重 DEK 源
- ✅ 详细的诊断日志，显示 DEK 的来源
- ✅ 增强的错误处理

### 修复 3：完整的 watch 监听策略

**文件**：`KnowledgeList.vue` 第 894-925 行

```javascript
// 【改进】监听 isKeyValid 变化
watch(() => isKeyValid.value, async (valid) => {
  if (valid && currentNoteData.value.is_secret && currentNoteData.value.title && !decryptedTitle.value) {
    console.log('[Vault] isKeyValid became true, retrying title decryption')
    await decryptNoteTitle()
  } else if (!valid && currentNoteData.value.is_secret && vaultStore.dek) {
    // 【修复】只有当 vaultStore.dek 也不可用时，才清除解密的标题
    console.log('[Vault] isKeyValid became false, but vaultStore.dek available, retrying')
    await decryptNoteTitle()
  } else if (!valid && currentNoteData.value.is_secret && !vaultStore.dek) {
    // DEK 完全不可用
    console.log('[Vault] DEK completely unavailable, clearing decrypted title')
    decryptedTitle.value = ''
  }
})

// 【新增】监听 dek.value 变化：当 session 恢复或 2FA 成功时重新解密
watch(() => dek.value, async (newDek) => {
  if (newDek && currentNoteData.value.is_secret && currentNoteData.value.title && !decryptedTitle.value) {
    console.log('[Vault] DEK recovered/updated, retrying title decryption')
    await decryptNoteTitle()
  } else if (!newDek && currentNoteData.value.is_secret && !vaultStore.dek) {
    console.log('[Vault] DEK lost and vaultStore.dek unavailable')
    decryptedTitle.value = ''
  }
})
```

**改进点**：
- ✅ 改进 `isKeyValid` watch：不再无条件清除，检查备用 DEK
- ✅ **新增** `dek.value` watch：捕捉 session 恢复或 2FA 成功的时刻
- ✅ 双层防御：DEK 的任何变化都能触发重新解密

---

## 修复流程示意

### 场景：用户在回收站预览加密笔记，然后刷新页面

```
【初始状态】
用户已在保密柜中完成 2FA
  ├─ dek.value = "base64_key"
  ├─ isKeyValid.value = true
  ├─ vaultStore.dek = "base64_key"

【切换到回收站，选择加密笔记 ID=75】
handleNoteSelect(75)
  ├─ fetchNoteDetail(75) 获取笔记数据
  ├─ currentNoteData.is_secret = true
  ├─ currentNoteData.title = "jfsasl6Y..." (加密)
  ├─ 检查：isKeyValid.value = true OR vaultStore.dek 有值？ → YES ✅
  ├─ 调用 decryptNoteTitle()
  ├─ dekToUse = dek.value (有值)
  ├─ plainTitle = decryptContent(...) = "我的银行密码"
  ├─ decryptedTitle.value = "我的银行密码"
  ↓
【工具栏显示】
displayTitle = decryptedTitle.value = "我的银行密码" ✅

【用户按 F5 刷新页面】
页面卸载
  ├─ 内存中的 dek.value 被重置（为 null）
  ├─ isKeyValid.value 被重置（为 false）
  ├─ vaultStore.dek 仍保留（内存中存储）

【useVaultEncryption.onMounted() 触发】
tryRecoverKeyFromSession()
  ├─ 调用 /api/vault/key/ 获取 DEK
  ├─ 从 Redis session 恢复 DEK
  ├─ dek.value = "base64_key" (恢复成功)
  ├─ 触发 watch(() => dek.value)
  ├─ 检查：currentNoteData.is_secret = true？ → YES
  ├─ 调用 decryptNoteTitle()
  ├─ dekToUse = dek.value (已恢复) OR vaultStore.dek
  ├─ plainTitle = decryptContent(...) = "我的银行密码"
  ├─ decryptedTitle.value = "我的银行密码"
  ↓
【工具栏显示】
displayTitle = decryptedTitle.value = "我的银行密码" ✅ (不是密文！)
```

### 场景：DEK 无法恢复（session 过期）

```
【用户刷新页面，DEK 恢复失败】
useVaultEncryption.onMounted()
  ├─ tryRecoverKeyFromSession()
  ├─ /api/vault/key/ 返回 404
  ├─ dek.value = null
  ├─ isKeyValid.value = false
  ├─ vaultStore.dek 也被清除（session 过期）
  ├─ 触发 watch(() => dek.value) 和 watch(() => isKeyValid.value)
  ├─ 两个 watch 都检查到 no DEK available
  ├─ decryptedTitle.value = ''
  ↓
【工具栏显示】
displayTitle 优先使用 decryptedTitle.value
  └─ decryptedTitle.value = '' (空)
  └─ 回退到 currentNoteData.value.title (密文)
  ↓
【应该显示占位符或提示】
但由于回收站中的 secret note 会被 NoteShadowViewer 拦截
  └─ displayContent = '<div class="vault-trash-notice">🔒 内容已锁定</div>'
```

---

## 完整工作流验证

### 🧪 测试 1：带 DEK 选择加密笔记

**前置条件**：用户已在保密柜完成 2FA

```
操作：进入回收站 → 点击加密笔记
预期日志：
  [Vault] Title decrypted successfully in KnowledgeList: 75
工具栏显示：明文标题 ✅
```

### 🧪 测试 2：无 DEK 选择加密笔记

**前置条件**：用户刚登录，未进入保密柜

```
操作：进入回收站 → 点击加密笔记
预期日志：
  [KnowledgeList] No DEK available for secret note: 75
  [Vault] Cannot decrypt title: no valid DEK
工具栏显示：密文（被 NoteShadowViewer 拦截为 🔒 内容已锁定）
```

### 🧪 测试 3：刷新页面（DEK 恢复成功）

**前置条件**：已选择加密笔记，工具栏显示明文

```
操作：F5 刷新页面
预期日志序列：
  1. [Vault] Key recovered from session
  2. watch(() => dek.value) 触发
  3. [Vault] DEK recovered/updated, retrying title decryption
  4. [Vault] Title decrypted successfully in KnowledgeList: 75
工具栏显示：明文标题（不是密文！）✅
```

### 🧪 测试 4：刷新页面（DEK 恢复失败）

**前置条件**：已选择加密笔记，session 已过期

```
操作：F5 刷新页面（假设 session 过期）
预期日志序列：
  1. Session recovery failed
  2. watch(() => dek.value) 触发（null）
  3. [Vault] DEK lost and vaultStore.dek unavailable
  4. watch(() => isKeyValid.value) 触发（false）
  5. [Vault] DEK completely unavailable
工具栏显示：🔒 内容已锁定（由 NoteShadowViewer 显示）✅
```

### 🧪 测试 5：刷新后再次解锁

**前置条件**：刷新后 DEK 不可用

```
操作：点击 🔒 占位符 → 完成 2FA
预期日志序列：
  1. [Vault] 2FA verified, DEK updated
  2. watch(() => dek.value) 触发
  3. [Vault] DEK recovered/updated, retrying title decryption
  4. [Vault] Title decrypted successfully in KnowledgeList: 75
工具栏显示：明文标题 ✅
```

---

## 修改统计

| 文件 | 修改内容 | 行数 | 目的 |
|------|--------|------|------|
| `KnowledgeList.vue` | 改进 `handleNoteSelect` 解密逻辑 | 364-385 | 避免刷新时清除解密标题 |
| `KnowledgeList.vue` | 增强 `decryptNoteTitle` DEK 检查 | 300-340 | 双重 DEK 源，备用方案 |
| `KnowledgeList.vue` | 改进 `watch isKeyValid` | 894-911 | 不无条件清除，检查备用 DEK |
| `KnowledgeList.vue` | **新增** `watch dek.value` | 913-925 | 捕捉 DEK 恢复/更新时刻 |

---

## Browser Console 输出示例

### 场景 1：DEK 恢复成功

```
[Vault] Key recovered from session
[Vault] DEK recovered/updated, retrying title decryption
[Vault] Title decrypted successfully in KnowledgeList: 75
```

### 场景 2：DEK 恢复失败

```
[Vault] DEK lost and vaultStore.dek unavailable
[Vault] DEK completely unavailable, clearing decrypted title
[Vault] Cannot decrypt title: no valid DEK {
  hasKeyValid: false,
  hasDek: false,
  hasVaultDek: false
}
```

### 场景 3：isKeyValid 从 true → false

```
[Vault] isKeyValid became false, but vaultStore.dek available, retrying
[Vault] Title decrypted successfully in KnowledgeList: 75
```

---

## Build 状态

✅ **成功编译**：
```
npm run build
✓ built in 4.95s
```

---

## 总结

修复解决了三个关键问题：

1. ✅ **`handleNoteSelect` 的过度清除** - 现在只有当完全没有 DEK 时才清除
2. ✅ **备用 DEK 源支持** - `decryptNoteTitle` 现在检查 `dek.value || vaultStore.dek`
3. ✅ **完整的 watch 监听** - 同时监听 `isKeyValid` 和 `dek.value`，捕捉任何变化

**结果**：用户刷新页面后，工具栏标题保持解密状态（如果 DEK 可恢复）✅

