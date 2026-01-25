
# 前端 UX 优化方案：智能加密流程

## 架构设计

### 1. Store 管理 (vault.js)
- 保存 DEK 缓存状态
- 管理待处理操作队列
- 处理 2FA 验证对话框的显示/隐藏

### 2. 核心业务流程

```
用户点击「加入保密柜」
    ↓
检查 DEK 是否有效
    ├─ 有效 (Smart Pass)
    │  └─ 直接加密 → 保存 → 成功提示
    │
    └─ 无效 (Require Auth)
       ├─ 保存待处理操作
       ├─ 弹出 2FA 对话框
       └─ 用户验证成功
          └─ 自动执行加密 → 保存 → 成功提示
```

### 3. 关键优化点

**优点 1: 无缝体验**
- 已验证过的用户：一次点击完成
- 未验证的用户：验证后自动完成，无需再点一次

**优点 2: 状态管理清晰**
- 使用 Pinia Store 统一管理
- 避免重复验证

**优点 3: 错误恢复**
- 验证失败时保留待处理操作
- 用户可以重试

## 实现步骤

### Step 1: 创建 Vault Store (已完成)
文件: `frontend/src/stores/vault.js`

主要导出:
- `setDEK(dek, expireTime)` - 保存 DEK
- `setPendingOperation(noteId, content, callback)` - 保存待处理操作
- `executePendingOperation()` - 执行待处理操作
- `isUnlocked` (computed) - 是否已解锁

### Step 2: 修改 SecondaryPanel.vue

添加导入:
```javascript
import { useVaultStore } from '@/stores/vault'
const vaultStore = useVaultStore()
const { dek: currentDek, isKeyValid } = useVaultEncryption()
```

关键函数:
- `handleToggleSecret(note)` - 主流程控制
- `executeEncryptAndSave()` - 执行加密
- `executeToggleSecretAPI()` - 执行切换

### Step 3: 修改 KnowledgeList.vue 或 VaultVerifyDialog.vue

监听验证成功事件:
```javascript
// 当用户在 VaultVerifyDialog 中验证成功时触发
window.dispatchEvent(new CustomEvent('vault-verification-success', {
  detail: { dek: dekValue }
}))
```

### Step 4: 集成现有的 VaultVerifyDialog

确保在验证成功时：
1. 调用 `useVaultEncryption().verify2FAAndGetKey()`
2. 触发 `vault-verification-success` 事件
3. 关闭对话框

## 使用场景示例

### 场景 1: 用户已验证（Smart Pass）

```
用户点击「加入保密柜」
  ↓ (vaultStore.isUnlocked = true)
直接加密内容 (< 1秒)
  ↓
保存到后端
  ↓
✅ 「已加入保密柜！内容已加密」
```

### 场景 2: 用户未验证（Require Auth）

```
用户点击「加入保密柜」
  ↓ (vaultStore.isUnlocked = false)
自动弹出 VaultVerifyDialog
  ↓ (用户输入 2FA 代码)
验证成功
  ↓ (触发 vault-verification-success)
自动执行待处理的加密操作
  ↓
✅ 「已加入保密柜！内容已加密」
(无需用户再操作)
```

### 场景 3: 验证失败后重试

```
用户输入错误的 2FA 代码
  ↓
验证失败，保留待处理操作
  ↓ (用户重新输入)
验证成功
  ↓
自动执行加密
  ↓
✅ 完成
```

## 代码改动总结

### 新增文件
- `frontend/src/stores/vault.js` (已创建)

### 修改文件
- `frontend/src/components/layout/SecondaryPanel.vue`
  - 添加 vaultStore 导入和初始化
  - 修改 handleToggleSecret() 实现智能流程
  - 添加辅助函数 executeEncryptAndSave(), executeToggleSecretAPI(), refreshVaultData()

### 可选修改
- `frontend/src/components/common/VaultVerifyDialog.vue`
  - 在验证成功时触发自定义事件 `vault-verification-success`
  - 确保能获取 DEK 值并传递给事件

## Next Steps

1. 修改 SecondaryPanel.vue 中的 handleToggleSecret
2. 在 VaultVerifyDialog.vue 中添加验证成功事件触发
3. 测试完整流程
4. 构建并验证
