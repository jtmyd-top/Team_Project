# 工具栏标题刷新后变密文 - 最终修复

## 问题确认

之前的修复有缺陷，关键在于：
- 当 `handleNoteSelect` 执行时，`decryptedTitle.value` 不应该保持旧值
- 而应该**总是清除旧值**（重置状态），然后根据现在的 DEK 状态来决定是否解密

---

## 根本原因

**时序问题**（刷新页面）：

```
【T0】 页面刷新，URL 参数中有 noteId=75
       ├─ KnowledgeList 重新挂载
       └─ onMounted 触发

【T1】 useVaultEncryption.onMounted 异步开始恢复 DEK
       └─ tryRecoverKeyFromSession() 发起网络请求（异步）

【T2】 页面初始化逻辑尝试加载笔记（假设 activeNoteId 有值）
       ├─ handleNoteSelect(75) 执行
       ├─ fetchNoteDetail(75) 加载笔记（标题是加密的）
       ├─ currentNoteData.title = "jfsasl6Y..." (密文)
       ├─ 检查是否解密：
       │  ├─ isKeyValid.value = false (还没恢复)
       │  ├─ dek.value = null (还没恢复)
       │  └─ 决定：不解密
       ├─ 保持 decryptedTitle.value = '' （之前是什么就保留？❌ 错！）
       └─ 【错误】如果 decryptedTitle.value 之前有值，会导致显示旧值

【T3】 DEK 恢复完成（异步网络请求返回）
       ├─ dek.value = "base64_key"
       ├─ isKeyValid.value = true
       ├─ watch 触发，重新解密
       └─ decryptedTitle.value = "我的银行密码"

【最终】
       工具栏显示明文 ✅
```

但问题是 T2 时如果之前有缓存的 decryptedTitle，就会显示错误的值。

---

## 完整修复

### 修复 1：`handleNoteSelect` 总是清除旧的解密标题

**文件**：`KnowledgeList.vue` 第 378-392 行

```javascript
// 如果是加密笔记，尝试解密标题
if (currentNoteData.value.is_secret) {
  // 【关键修复】先清除旧的解密标题，重置状态
  decryptedTitle.value = ''

  // 如果有 DEK，立即尝试解密
  if (isKeyValid.value || vaultStore.dek) {
    // 有 DEK 时解密
    await decryptNoteTitle()
    console.log('[KnowledgeList] Secret note loaded with DEK available')
  } else {
    // 没有 DEK 时，保持 decryptedTitle = ''
    // watch(() => dek.value) 会在 DEK 恢复后自动重新解密
    console.log('[KnowledgeList] Secret note loaded, no DEK yet, waiting for recovery')
  }
} else {
  // 非加密笔记，清除解密标题
  decryptedTitle.value = ''
}
```

**关键变化**：
- ✅ 第一步就清除 `decryptedTitle.value = ''`（重置状态）
- ✅ 然后根据是否有 DEK 来决定是否立即解密
- ✅ 如果没有 DEK，保持空值，等待 watch 恢复

### 修复 2：删除 watch 中的 `!decryptedTitle.value` 条件

**文件**：`KnowledgeList.vue` 第 899-914 行

```javascript
// 监听保险柜解锁状态：当 DEK 变为 true 时，立即重新解密
watch(() => isKeyValid.value, async (valid) => {
  // 【关键修复】删除了 !decryptedTitle.value 的条件
  if (valid && currentNoteData.value.is_secret && currentNoteData.value.title) {
    // 只要 DEK 变为有效，就立即重新解密
    console.log('[Vault] isKeyValid became true, retrying title decryption for note:', currentNoteData.value.id)
    await decryptNoteTitle()
  } else if (!valid && currentNoteData.value.is_secret && vaultStore.dek) {
    // 有备用 DEK 时，用备用解密
    await decryptNoteTitle()
  } else if (!valid && currentNoteData.value.is_secret && !vaultStore.dek) {
    // 完全无 DEK
    decryptedTitle.value = ''
  }
})
```

**关键变化**：
- ✅ 原条件：`if (valid && ... && !decryptedTitle.value)` - 只有当 decryptedTitle 为空时才解密
- ✅ 新条件：`if (valid && ... && currentNoteData.value.title)` - 只要有 DEK，就解密（无论之前状态）

### 修复 3：同样修改 watch dek.value

**文件**：`KnowledgeList.vue` 第 916-926 行

```javascript
watch(() => dek.value, async (newDek) => {
  // 【关键修复】删除 !decryptedTitle.value 的条件
  if (newDek && currentNoteData.value.is_secret && currentNoteData.value.title) {
    // 只要 dek.value 有值，就立即解密
    console.log('[Vault] DEK recovered/updated, retrying title decryption for note:', currentNoteData.value.id)
    await decryptNoteTitle()
  } else if (!newDek && currentNoteData.value.is_secret && !vaultStore.dek) {
    decryptedTitle.value = ''
  }
})
```

**关键变化**：
- ✅ 删除了 `!decryptedTitle.value` 的条件
- ✅ 现在只要 `dek.value` 有值，就立即解密

---

## 修复后的流程

### 刷新页面时（DEK 可恢复）

```
【T0】页面刷新，笔记 ID=75 在 URL 或已选中
      ├─ useVaultEncryption.onMounted() 开始恢复 DEK（异步）
      └─ handleNoteSelect 加载笔记

【T1】loadNoteSelect 执行
      ├─ fetchNoteDetail(75) → title="jfsasl6Y..." (密文)
      ├─ decryptedTitle.value = '' ✅ 【新】清除旧值
      ├─ 检查：isKeyValid.value = false && dek.value = null
      ├─ 条件不满足，不解密
      ├─ displayTitle computed:
      │  ├─ decryptedTitle.value = '' (空)
      │  └─ 回退到 currentNoteData.value.title = "jfsasl6Y..." (密文)
      ├─ 工具栏暂时显示密文 ⏳
      └─ 返回等待 DEK 恢复

【T2】DEK 恢复完成（异步网络请求完成）
      ├─ dek.value = "base64_..." ✅ 更新
      ├─ isKeyValid.value = true ✅ 更新
      ├─ watch(() => dek.value) 触发 ✅
      ├─ 条件：dek.value && is_secret && title
      ├─ 满足！调用 decryptNoteTitle()
      ├─ dekToUse = dek.value
      ├─ plainTitle = decryptContent("jfsasl6Y...", dekToUse)
      ├─ decryptedTitle.value = "我的银行密码" ✅
      ├─ displayTitle computed:
      │  ├─ decryptedTitle.value = "我的银行密码"
      │  └─ 使用解密的标题
      ├─ 工具栏立即显示明文 ✅ 【成功！】
      └─ 可视化反馈：工具栏标题从密文变为明文
```

### 未解锁状态（DEK 不可恢复）

```
【T0】用户刚登录，进入回收站，选择加密笔记
      ├─ useVaultEncryption.onMounted() 尝试恢复 DEK
      └─ handleNoteSelect 加载笔记

【T1】handleNoteSelect 执行
      ├─ fetchNoteDetail → title="jfsasl6Y..." (密文)
      ├─ decryptedTitle.value = ''
      ├─ 检查：isKeyValid.value = false && dek.value = null && vaultStore.dek = null
      ├─ 条件不满足，不解密
      ├─ displayTitle = "" 或 currentNoteData.title (密文)
      └─ 工具栏显示密文 ⚠️

【用户点击 🔒 占位符，完成 2FA】
      ├─ dek.value = "base64_..." ✅
      ├─ isKeyValid.value = true ✅
      ├─ watch 触发
      ├─ decryptNoteTitle() 执行
      ├─ decryptedTitle.value = "我的银行密码" ✅
      └─ 工具栏更新为明文 ✅
```

---

## 改进前后对比

### 改进前（问题）

```javascript
if (currentNoteData.value.is_secret && isKeyValid.value) {
  await decryptNoteTitle()
} else {
  // ❌ 错：保留旧的 decryptedTitle，可能显示错误的值
  // decryptedTitle.value = '' 不执行
}
```

**问题**：保留了旧值，可能导致显示错的笔记标题

### 改进后（正确）

```javascript
if (currentNoteData.value.is_secret) {
  // ✅ 先清除旧值，重置状态
  decryptedTitle.value = ''

  if (isKeyValid.value || vaultStore.dek) {
    // 有 DEK 就解密
    await decryptNoteTitle()
  }
  // 没有 DEK 就等待 watch 恢复
}
```

**优势**：
- ✅ 总是清除旧值，不会有遗留数据
- ✅ 无 DEK 时等待 watch，自动恢复后解密
- ✅ 确保一致性

---

## Watch 条件变化

### isKeyValid watch

**改进前**：
```javascript
if (valid && currentNoteData.value.is_secret && !decryptedTitle.value)
```
只有当 decryptedTitle 为空时才解密

**改进后**：
```javascript
if (valid && currentNoteData.value.is_secret && currentNoteData.value.title)
```
只要有有效 DEK，就解密（无条件）

### dek.value watch

**改进前**：
```javascript
if (newDek && currentNoteData.value.is_secret && !decryptedTitle.value)
```

**改进后**：
```javascript
if (newDek && currentNoteData.value.is_secret && currentNoteData.value.title)
```

---

## 完整的时序图

```
【没有 DEK】          【DEK 恢复中】        【DEK 恢复成功】
   T0                  T1                    T2

decryptedTitle:      decryptedTitle:       decryptedTitle:
  ""                   ""                  "我的银行密码"

dek.value:           dek.value:            dek.value:
  null                 null                "base64_..."

工具栏显示:           工具栏显示:            工具栏显示:
"jfsasl6Y..." (密文) → "jfsasl6Y..." → "我的银行密码" (明文)
                       (暂时密文)        ✅ watch 触发，立即更新
```

---

## Browser Console 预期输出

### 刷新页面（DEK 恢复成功）

```
[KnowledgeList] Secret note loaded, no DEK yet, waiting for recovery
[Vault] Key recovered from session
[Vault] isKeyValid became true, retrying title decryption for note: 75
[Vault] Title decrypted successfully in KnowledgeList: 75
```

或

```
[Vault] DEK recovered/updated, retrying title decryption for note: 75
[Vault] Title decrypted successfully in KnowledgeList: 75
```

### 未解锁状态

```
[KnowledgeList] Secret note loaded, no DEK yet, waiting for recovery
```

然后用户点击 🔒 完成 2FA：

```
[Vault] 2FA verified, DEK updated
[Vault] isKeyValid became true, retrying title decryption for note: 75
[Vault] Title decrypted successfully in KnowledgeList: 75
```

---

## Build 状态

✅ **成功**：
```
npm run build
✓ built in 4.26s
```

---

## 关键改动总结

| 位置 | 改动 | 效果 |
|------|------|------|
| handleNoteSelect | 先清除 decryptedTitle | 重置状态，无旧值遗留 |
| handleNoteSelect | 有 DEK 就解密 | 同步解密（如果可用） |
| watch isKeyValid | 删除 !decryptedTitle.value | 任何 DEK 变化都重新解密 |
| watch dek.value | 删除 !decryptedTitle.value | 任何 DEK 变化都重新解密 |

---

## 验证方法

1. **清空缓存**：`Ctrl + Shift + Delete`
2. **刷新页面**：`F5`
3. **检查**：
   - ⏳ 初始可能显示密文（0-1秒）
   - ✅ 然后自动变为明文
   - 📊 Console 应显示解密日志

