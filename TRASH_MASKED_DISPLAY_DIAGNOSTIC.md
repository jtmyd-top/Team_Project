# 回收站模糊展示 - 诊断检查清单

## 实现完成清单

### ✅ SecondaryPanel.vue 修改
- [x] 添加 DEK 变化监听（第 428-447 行）
- [x] 添加 currentNotes 变化监听（第 449-487 行）
- [x] 两个 watch 都配置了 `immediate: true`
- [x] 添加详细日志输出

### ✅ NoteListItem.vue 修改
- [x] 添加 `isInTrash` computed（第 189 行）
- [x] 添加 `needsUnlock` computed（第 193-194 行）
- [x] 修改模板：条件渲染标题（第 38-52 行）
- [x] 实现模糊占位符 HTML（第 44-50 行）
- [x] 实现 `handleUnlockVault` 方法（第 197-204 行）
- [x] 禁用回收站操作按钮（第 102-113 行）
- [x] 添加 CSS 样式（第 476-502 行、553-558 行）

### ✅ SecondaryPanel.vue 事件处理
- [x] 监听 'request-vault-unlock' 事件（第 340-349 行）
- [x] 触发 'open-vault-unlock-dialog' 事件

---

## 浏览器控制台诊断

### 步骤 1：打开浏览器开发者工具
```
按 F12 或 右键 > 检查元素 > Console 标签页
```

### 步骤 2：首次登录场景

**预期日志输出**：
```
[SecondaryPanel] Processing trash notes, DEK available: false
[SecondaryPanel] ⚠️ No DEK available for trash note: 123 - will show masked title
[SecondaryPanel] ⚠️ No DEK available for trash note: 456 - will show masked title
```

**检查点**：
```javascript
// 在控制台运行，检查 isKeyValid
vue.$refs.noteListItem[0].isKeyValid  // 应该为 false

// 检查 vaultStore.dek
const { useVaultStore } = require('@/stores/vault')
useVaultStore().dek  // 应该为 null

// 检查 needsUnlock 是否为 true
vue.$refs.noteListItem[0].needsUnlock  // 应该为 true
```

### 步骤 3：点击 🔒 模糊占位符

**预期日志**：
```
[NoteListItem] User clicked to unlock vault for note: 123
[SecondaryPanel] Received vault unlock request from trash: 123
[SecondaryPanel] Opening vault unlock dialog from trash...
```

### 步骤 4：完成 2FA 解锁

**预期日志序列**：
```
[Vault] DEK loaded into memory
[Vault] isKeyValid changed: false → true
[SecondaryPanel] DEK updated, retrying trash note decryption
[SecondaryPanel] ✅ Title decrypted after unlock: 123
[SecondaryPanel] ✅ Title decrypted after unlock: 456
```

---

## UI 验证

### 场景 1：刚登录（未解锁）

**预期表现**：
```
回收站列表：
┌─────────────────────────────────┐
│ 🔒 加密笔记 - 点击解锁           │  ← 保密笔记
│ (恢复) (删除) 按钮被禁用          │
├─────────────────────────────────┤
│ 普通笔记 1                       │  ← 普通笔记
│ (恢复) (删除) 按钮启用          │
├─────────────────────────────────┤
│ 🔒 加密笔记 - 点击解锁           │  ← 保密笔记
│ (恢复) (删除) 按钮被禁用          │
└─────────────────────────────────┘
```

**检查点**：
- [ ] 加密笔记显示为 🔒 符号 + 文本
- [ ] 加密笔记不显示密文
- [ ] 恢复/删除按钮已禁用（灰色、不可点击）
- [ ] 普通笔记正常显示
- [ ] 普通笔记的按钮启用

### 场景 2：点击 🔒 后

**预期表现**：
```
用户点击 🔒 加密笔记
    ↓
保密柜解锁对话框打开
    ↓
用户完成 2FA
    ↓
回收站列表自动更新
┌─────────────────────────────────┐
│ 我的银行密码                      │  ← 标题已解密
│ (恢复) (删除) 按钮启用           │
├─────────────────────────────────┤
│ 普通笔记 1                       │
│ (恢复) (删除) 按钮启用          │
├─────────────────────────────────┤
│ 我的第二个加密笔记                │  ← 自动解密
│ (恢复) (删除) 按钮启用           │
└─────────────────────────────────┘
```

**检查点**：
- [ ] 解锁对话框打开
- [ ] 2FA 验证工作
- [ ] 解锁后笔记标题显示明文
- [ ] 按钮恢复启用
- [ ] 所有保密笔记自动解密（无需逐个点击）

---

## JavaScript 控制台调试代码

### 检查 NoteListItem 的计算属性

```javascript
// 获取第一个 NoteListItem 组件
const noteItem = document.querySelector('[class*="note-list-item"]')

// 在 Vue DevTools 中可以直接看到：
// - note: {is_secret, title, decryptedTitle, ...}
// - isKeyValid: boolean
// - needsUnlock: boolean
// - displayTitle: string
```

### 手动测试解密逻辑

```javascript
// 模拟从密文解密
const CryptoJS = require('crypto-js')
const { useClientCrypto } = require('@/composables/useClientCrypto')
const { useVaultStore } = require('@/stores/vault')

const crypto = useClientCrypto()
const store = useVaultStore()

const encryptedTitle = "YZ1s3YzHQoivmlhy..."  // 从回收站笔记获取
const dek = store.dek  // 或 dek.value

if (dek) {
  try {
    const plainTitle = crypto.decryptContent(encryptedTitle, dek)
    console.log('Decrypted:', plainTitle)
  } catch (e) {
    console.error('Decrypt failed:', e)
  }
} else {
  console.log('No DEK available')
}
```

---

## 常见问题和解决方案

### Q1: 模糊占位符没有显示，仍然显示密文

**可能原因**：
1. needsUnlock 计算有问题
2. v-if 条件没有生效
3. 初始化时间问题

**诊断**：
```javascript
// 检查 needsUnlock 值
note.is_secret && !isKeyValid.value && !vaultStore.dek && isInTrash.value
// 应该输出 true

// 检查 displayTitle
displayTitle.value
// 应该是密文
```

**解决**：
1. 清空浏览器缓存
2. 重新刷新页面
3. 检查浏览器控制台是否有错误

### Q2: 点击 🔒 没有反应

**可能原因**：
1. 事件没有注册
2. 点击事件被其他元素拦截
3. handleUnlockVault 方法未被调用

**诊断**：
```javascript
// 检查事件监听器是否注册
window.addEventListener('request-vault-unlock', (e) => {
  console.log('Event received:', e.detail)
})

// 手动触发测试
window.dispatchEvent(new CustomEvent('request-vault-unlock', {
  detail: { fromTrash: true, noteId: 123 }
}))
```

**解决**：
1. 检查 onClick 绑定：`@click.stop="handleUnlockVault"`
2. 确保没有其他 @click 拦截事件
3. 检查 z-index 问题（是否被其他元素遮挡）

### Q3: 解锁后标题仍未显示

**可能原因**：
1. DEK 更新没有触发 watch
2. 解密失败
3. note.decryptedTitle 未被设置

**诊断**：
```javascript
// 监听 DEK 变化
const { dek } = useVaultEncryption()
watch(() => dek.value, (newDek) => {
  console.log('DEK changed:', !!newDek)
})

// 检查 note.decryptedTitle
note.decryptedTitle  // 应该有值
```

**解决**：
1. 尝试手动刷新页面
2. 检查解密函数是否抛出异常
3. 查看 SecondaryPanel 的日志输出

---

## 性能监控

### 监听 watch 执行次数

```javascript
// 在 SecondaryPanel.vue 中添加计数器
let watchCount = 0
watch(
  () => ({ /* ... */ }),
  () => {
    watchCount++
    console.log(`[SecondaryPanel] Watch executed: ${watchCount} times`)
    // ...
  }
)
```

**预期**：
- 进入回收站：1 次（immediate）
- DEK 加载：1 次（watch dek.value）
- currentNotes 变化：可能多次（如果列表更新）

**警告**：
- 如果执行超过 5 次，可能有无限循环
- 检查是否有重复修改 note.decryptedTitle

---

## 最终验证清单

进行完整的端到端测试：

- [ ] 清空浏览器缓存和数据
- [ ] 重新登录（模拟首次登录）
- [ ] 进入回收站
- [ ] 验证加密笔记显示为 🔒 模糊占位符
- [ ] 验证恢复/删除按钮被禁用
- [ ] 点击 🔒，打开解锁对话框
- [ ] 完成 2FA 验证
- [ ] 验证列表自动更新，标题显示为明文
- [ ] 验证恢复/删除按钮恢复启用
- [ ] 尝试恢复一个加密笔记
- [ ] 验证笔记从回收站消失，出现在原位置

所有步骤都通过 ✅ 时，实现完成！

