# 快速测试清单 - 回收站加密笔记三大修复

## 🔧 修复已完成

### ✅ 后端修复
```
knowledge_project/folder_views.py: trashed_notes_api 返回 is_secret 等字段
```

### ✅ 前端修复（KnowledgeList.vue）
```
1. handleNoteSelect 改进：支持 vaultStore.dek 备用源
2. decryptNoteTitle 增强：双重 DEK 源检查
3. watch isKeyValid 改进：智能清除逻辑
4. watch dek.value 新增：捕捉 DEK 恢复时刻
```

### ✅ 前端修复（SecondaryPanel.vue）
```
1. watch isKeyValid 新增：清除不可用时的缓存标题
2. watch currentNotes 改进：详细的自动解密逻辑
```

### ✅ 前端修复（NoteListItem.vue）
```
1. watch parent.decryptedTitle：响应 parent 更新
```

---

## 🧪 快速验证（3 分钟测试）

### 步骤 1：进入回收站（已解锁）
```
前置：在保密柜完成 2FA 验证
操作：导航到"回收站"
检查：
  ✅ 加密笔记标题显示为明文（如"我的银行密码"）
  ✅ 不是密文（如"jfsasl6YpVoL..."）
  ✅ Console 显示：[SecondaryPanel] ✅ Title decrypted
```

### 步骤 2：刷新页面
```
操作：按 F5 刷新页面
检查：
  ✅ 回收站列表标题仍显示明文（不变成密文）
  ✅ 工具栏（预览区）标题仍显示明文（不变成密文）
  ✅ Console 显示：[Vault] Key recovered from session
  ✅ Console 显示：Title decrypted successfully
```

### 步骤 3：未解锁状态测试
```
操作：
  1. 登出应用
  2. 重新登录
  3. 不进入保密柜，直接进入回收站
检查：
  ✅ 加密笔记显示 🔒 占位符（不是密文）
  ✅ Console 显示：⚠️ No DEK available
```

### 步骤 4：点击占位符解锁
```
操作：
  1. 点击 🔒 占位符
  2. 完成 2FA
检查：
  ✅ 列表自动更新，显示明文标题
  ✅ 工具栏自动更新，显示明文标题
  ✅ Console 显示：✅ Title decrypted after unlock
```

---

## 📊 最终状态

| 问题 | 修复前 | 修复后 |
|------|-------|-------|
| 列表标题显示 | 密文 ❌ | 明文 ✅ 或占位符 ✅ |
| 工具栏刷新后 | 变密文 ❌ | 保持明文 ✅ |
| 自动解密能力 | 无（需点击）❌ | 完全自动 ✅ |
| 占位符显示 | 无❌ | 完整 ✅ |

---

## 📝 Build 状态

```
✓ built in 4.95s
```

---

## 🎯 关键要点

1. **后端返回 is_secret** → 前端能判断加密笔记
2. **双重 DEK 源** → `dek.value` 和 `vaultStore.dek` 都检查
3. **监听 dek.value** → 捕捉 session 恢复或 2FA 成功
4. **不无条件清除** → 刷新时保留解密标题，等待 DEK 恢复
5. **列表自动解密** → 进入回收站立即尝试解密

---

## 📚 详细文档

- **TRASH_ENCRYPTION_FIXES_SUMMARY.md** - 完整总结
- **TRASH_DECRYPTION_FINAL_FIX.md** - 修复 #1：后端 + 列表
- **TOOLBAR_TITLE_REFRESH_FIX.md** - 修复 #2：工具栏刷新
- **TRASH_AUTO_DECRYPT_DEBUG.md** - 修复 #3：自动解密

---

## ✅ 所有修复已完成并编译成功！

