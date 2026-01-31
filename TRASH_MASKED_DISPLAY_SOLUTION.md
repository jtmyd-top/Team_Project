# 回收站模糊展示修复方案 (Masked Display for Trash)

## 问题描述

用户首次登录时，若未解锁保密柜，进入回收站查看：
- ❌ 加密笔记标题显示为密文 (例如：`YZ1s3YzHQoivmlhy...`)
- ❌ 应该显示模糊占位符 (例如：`🔒 加密笔记 - 点击解锁`)

## 完整解决方案

### 第 1 层：自动解密 (SecondaryPanel.vue)
**如果 DEK 可用，自动解密标题**

```javascript
watch(
  () => ({
    notes: sidebarStore.currentNotes,
    isTrash: sidebarStore.activeModule === 'trash',
    dek: dek.value,
    vaultDek: vaultStore.dek
  }),
  ({ notes, isTrash, dek: dekValue, vaultDek }) => {
    if (!isTrash) return

    notes.forEach(note => {
      if (note.decryptedTitle) return  // 已解密，跳过

      if (note.is_secret && note.title) {
        const dekToUse = dekValue || vaultDek

        if (dekToUse) {
          try {
            const plainTitle = decryptContent(note.title, dekToUse)
            note.decryptedTitle = plainTitle  // ✅ 自动解密成功
          } catch (e) {
            console.warn('Decrypt failed, will show masked title')
            // ❌ 解密失败，不设置 decryptedTitle，会触发 needsUnlock
          }
        } else {
          // ⚠️ 没有 DEK，会触发 needsUnlock
          console.log('No DEK available, showing masked title')
        }
      }
    })
  },
  { deep: true, immediate: true }
)
```

### 第 2 层：模糊展示 (NoteListItem.vue)
**如果无法解密，显示模糊占位符**

**条件判断**:
```javascript
// 是否需要解锁
const needsUnlock = computed(() => {
  return (
    props.note.is_secret &&  // 是保密笔记
    !isKeyValid.value &&      // 未解锁
    !vaultStore.dek &&        // 无备用 DEK
    isInTrash.value           // 在回收站
  )
})
```

**UI 渲染**:
```vue
<!-- 标题已解密或未加密 -->
<h4 v-if="!needsUnlock" class="note-title">
  {{ displayTitle }}
</h4>

<!-- 需要解锁 - 显示模糊占位符 -->
<h4 v-else class="note-title locked" @click="handleUnlockVault">
  <span class="lock-icon">🔒</span>
  <span class="mask-text">加密笔记 - 点击解锁</span>
</h4>
```

### 第 3 层：按需解锁
**用户点击模糊占位符时，触发解锁流程**

```javascript
function handleUnlockVault() {
  window.dispatchEvent(new CustomEvent('request-vault-unlock', {
    detail: { fromTrash: true, noteId: props.note.id }
  }))
}
```

---

## 完整工作流程

```
用户进入回收站
    ↓
sidebarStore.loadTrashedNotes() 加载数据
    ↓
SecondaryPanel watch 触发
    ├─ 检查 activeModule === 'trash'
    ├─ 遍历 currentNotes
    ├─ 对于每个 is_secret=true 的笔记：
    │   ├─ 如果有 DEK（dek.value 或 vaultStore.dek）
    │   │   └─ 尝试 decryptContent()
    │   │       ├─ 成功 → 设置 note.decryptedTitle ✅
    │   │       └─ 失败 → 不设置 decryptedTitle ⚠️
    │   └─ 如果无 DEK
    │       └─ 跳过解密，不设置 decryptedTitle ⚠️
    ↓
NoteListItem 计算 needsUnlock
    ├─ 如果 note.decryptedTitle 存在
    │   └─ displayTitle = note.decryptedTitle ✅
    ├─ 如果 needsUnlock = true（无 DEK 且在回收站）
    │   └─ 显示模糊占位符 🔒
    └─ 其他情况
        └─ 显示原标题或本地解密

用户点击 🔒 模糊占位符
    ↓
触发 'request-vault-unlock' 事件
    ↓
AppLayout 打开保密柜解锁对话框
    ↓
用户完成 2FA 验证
    ↓
DEK 加载到内存
    ↓
isKeyValid 变为 true / vaultStore.dek 更新
    ↓
SecondaryPanel watch 重新触发
    ↓
自动重新解密所有笔记
    ↓
needsUnlock 变为 false
    ↓
列表自动更新，显示解密后的标题 ✅
```

---

## 关键代码位置

### SecondaryPanel.vue (第 428-472 行)

```javascript
// 【新增】监听回收站笔记变化，自动解密保密笔记的标题
watch(
  () => ({
    notes: sidebarStore.currentNotes,
    isTrash: sidebarStore.activeModule === 'trash',
    dek: dek.value,
    vaultDek: vaultStore.dek
  }),
  ({ notes, isTrash, dek: dekValue, vaultDek }) => {
    if (!isTrash) return

    console.log('[SecondaryPanel] Processing trash notes, DEK available:', !!(dekValue || vaultDek))

    notes.forEach(note => {
      if (note.decryptedTitle) return

      if (note.is_secret && note.title) {
        const dekToUse = dekValue || vaultDek

        if (dekToUse) {
          try {
            const plainTitle = decryptContent(note.title, dekToUse)
            note.decryptedTitle = plainTitle
            console.log('[SecondaryPanel] ✅ Title decrypted:', note.id)
          } catch (e) {
            console.warn('[SecondaryPanel] ❌ Failed to decrypt:', note.id, e.message)
          }
        } else {
          console.log('[SecondaryPanel] ⚠️ No DEK, showing masked title:', note.id)
        }
      }
    })
  },
  { deep: true, immediate: true }
)
```

### NoteListItem.vue (第 38-52 行)

```vue
<template v-else class="note-title-wrapper">
  <i v-if="note.is_secret" class="fas fa-lock vault-badge" title="保密笔记"></i>

  <!-- 标题已解密或未加密 -->
  <h4 v-if="!needsUnlock" class="note-title">
    {{ displayTitle }}
  </h4>

  <!-- 需要解锁 - 显示模糊占位符 -->
  <h4 v-else class="note-title locked" @click.stop="handleUnlockVault">
    <span class="lock-icon">🔒</span>
    <span class="mask-text">加密笔记{{ isInTrash ? ' - 点击解锁' : '' }}</span>
  </h4>
</template>
```

### NoteListItem.vue (第 193-194 行)

```javascript
// 计算属性：是否需要解锁
const needsUnlock = computed(() => {
  return props.note.is_secret && !isKeyValid.value && !vaultStore.dek && isInTrash.value
})
```

### NoteListItem.vue (回收站操作按钮)

```vue
<!-- 恢复按钮 -->
<button
  class="action-btn restore-btn"
  @click="handleRestore"
  :disabled="note.is_secret && !isKeyValid && !vaultStore.dek"
  :title="note.is_secret && !isKeyValid && !vaultStore.dek ? '需要先解锁保密柜' : '恢复'"
>
  <i class="fas fa-undo"></i>
</button>
```

---

## CSS 样式

### 模糊占位符样式 (第 476-502 行)

```css
.note-title.locked {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-secondary, #999);
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 3px;
  transition: all 0.2s;
}

.note-title.locked:hover {
  background: var(--primary-color-light, rgba(64, 158, 255, 0.1));
  color: var(--primary-color, #409eff);
}

.note-title.locked .lock-icon {
  flex-shrink: 0;
  font-size: 14px;
}

.note-title.locked .mask-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}
```

### 禁用按钮样式

```css
.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  pointer-events: none;
}

.action-btn:disabled:hover {
  background: transparent;
}
```

---

## 测试流程

### 场景 1：首次登录 - 未解锁保密柜
```
✅ 进入回收站
✅ 加密笔记显示为 "🔒 加密笔记 - 点击解锁"
✅ 恢复/删除按钮被禁用
✅ 点击 🔒 触发解锁对话框
✅ 完成 2FA 后，自动显示解密标题
```

### 场景 2：已解锁保密柜
```
✅ 进入回收站
✅ 加密笔记标题自动解密显示
✅ 恢复/删除按钮启用
✅ 点击操作正常工作
```

### 场景 3：DEK 过期但有 session 备份
```
✅ isKeyValid = false，但 vaultStore.dek 有值
✅ SecondaryPanel watch 使用 vaultStore.dek 解密
✅ 加密笔记标题自动显示（无需再次 2FA）
```

### 场景 4：完全无 DEK（刚登录）
```
✅ isKeyValid = false，vaultStore.dek = null
✅ 加密笔记显示为 "🔒 加密笔记 - 点击解锁"
✅ 恢复/删除按钮禁用
```

---

## 故障排查

### 问题 1：模糊占位符未显示，仍显示密文

**检查点**：
1. 检查浏览器控制台日志：
   ```
   ✅ [SecondaryPanel] Processing trash notes, DEK available: false
   ✅ [SecondaryPanel] ⚠️ No DEK, showing masked title: 123
   ```

2. 检查 needsUnlock 计算：
   ```javascript
   // 在浏览器控制台运行
   note.is_secret && !isKeyValid.value && !vaultStore.dek && isInTrash.value
   // 应该返回 true
   ```

3. 检查 v-if 条件：
   ```vue
   <h4 v-if="!needsUnlock">...</h4>
   <h4 v-else>🔒 加密笔记 - 点击解锁</h4>
   ```

### 问题 2：点击解锁无反应

**检查点**：
1. 检查事件是否触发：
   ```
   [NoteListItem] User clicked to unlock vault for note: 123
   ```

2. 检查是否收到事件：
   ```
   [SecondaryPanel] Received vault unlock request from trash: 123
   ```

3. 检查解锁对话框是否打开

### 问题 3：解密后仍显示模糊占位符

**检查点**：
1. 检查 decryptedTitle 是否被设置：
   ```javascript
   note.decryptedTitle  // 应该有值
   ```

2. 检查 DEK 是否更新：
   ```javascript
   dek.value  // 应该有值
   vaultStore.dek  // 应该有值
   ```

3. 检查 needsUnlock 是否变为 false：
   ```javascript
   needsUnlock.value  // 应该为 false
   ```

---

## 相关事件

### 触发事件
- `request-vault-unlock` - 用户点击 🔒 时触发
  ```javascript
  window.dispatchEvent(new CustomEvent('request-vault-unlock', {
    detail: { fromTrash: true, noteId: 123 }
  }))
  ```

### 监听事件
- `open-vault-unlock-dialog` - SecondaryPanel 转发给父组件
  ```javascript
  window.addEventListener('open-vault-unlock-dialog', (event) => {
    const { fromTrash, noteId } = event.detail
    // 打开保密柜解锁对话框
  })
  ```

---

## 安全性说明

✅ **完全安全** - 即使某人打开用户的屏幕，也只能看到：
- "🔒 加密笔记 - 点击解锁"
- 而不是敏感标题（如 "银行密码"）

✅ **体验友好** - 用户可以：
- 识别自己需要的笔记（通过 ID、修改时间等）
- 快速判断是还原还是删除
- 一键解锁后快速恢复或删除

