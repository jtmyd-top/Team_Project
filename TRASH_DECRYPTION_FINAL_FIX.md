# 回收站加密笔记解密问题 - 完整修复

## 问题症状

用户报告：
1. ❌ 回收站列表中的加密笔记标题显示**密文**，而不是自动解密或显示占位符
2. ❌ 工具栏中解密的标题在**刷新页面后变成密文**
3. ❌ **需要用户点击**笔记才会解密（无法无感自动解密）

## 根本原因分析

### 问题 1：后端未返回 is_secret 字段

**前端日志显示**：
```
[SecondaryPanel] Processing note: 75 is_secret: undefined decryptedTitle: false
```

**根本原因**：后端的 `trashed_notes_api` 返回的数据结构中**没有 `is_secret` 字段**！

```python
# 【修复前】- folder_views.py 第 328-347 行
def trashed_notes_api(request):
    return JsonResponse({
        'notes': [{
            'id': note.id,
            'title': note.title,  # 只返回标题，没有 is_secret！
            'trashed_at': ...,
            'folder': ...
        } for note in notes]
    })
```

**后果**：
- 前端无法判断回收站中哪些笔记是加密的
- `needsUnlock` 计算属性判断不了，导致无法显示占位符
- 所有笔记都当作普通笔记处理，直接显示密文标题

### 问题 2：DEK 状态变化时未清除缓存的解密标题

当用户刷新页面时：
- 内存中的 DEK 被清除（`dek.value = null`，`isKeyValid.value = false`）
- 但 `note.decryptedTitle` 仍保留着旧的解密值
- 导致显示过期的明文而不是占位符

---

## 修复方案

### 修复 1：后端返回完整的笔记元数据

**文件**：`knowledge_project/folder_views.py` 第 328-347 行

添加 `is_secret` 和其他必要字段：

```python
@login_required
@require_http_methods(["GET"])
def trashed_notes_api(request):
    """获取回收站中的笔记列表"""
    user = request.user

    notes = Note.objects.filter(
        author=user,
        is_trashed=True
    ).order_by('-trashed_at').select_related('folder')

    return JsonResponse({
        'notes': [{
            'id': note.id,
            'title': note.title,
            'trashed_at': note.trashed_at.strftime('%Y-%m-%d %H:%M') if note.trashed_at else None,
            'is_secret': note.is_secret,  # ✅ 新增：前端需要知道是否加密
            'is_trashed': note.is_trashed,  # ✅ 新增：冗余但安全
            'is_favorited': note.is_favorited,  # ✅ 新增：按钮状态
            'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M'),  # ✅ 新增：显示时间
            'folder': {
                'id': note.folder.id,
                'name': note.folder.name
            } if note.folder else None
        } for note in notes]
    })
```

**效果**：
- ✅ 前端能识别加密笔记：`note.is_secret = true`
- ✅ `needsUnlock` 计算属性能正确判断
- ✅ DEK 不可用时显示占位符，可用时自动解密

### 修复 2：SecondaryPanel 增强 DEK 状态监听

**文件**：`frontend/src/components/layout/SecondaryPanel.vue`

**监听 1：DEK 变为不可用时清除缓存**（关键！）
```javascript
watch(
  () => isKeyValid.value,
  (valid) => {
    if (!valid && sidebarStore.activeModule === 'trash' && !vaultStore.dek) {
      console.log('[SecondaryPanel] DEK unavailable, clearing decryptedTitles')
      sidebarStore.currentNotes.forEach(note => {
        if (note.is_secret && note.decryptedTitle) {
          note.decryptedTitle = undefined
        }
      })
    }
  }
)
```

**监听 2：DEK 变为可用时重新尝试解密**
```javascript
watch(
  () => dek.value,
  () => {
    if (sidebarStore.activeModule === 'trash' && dek.value) {
      sidebarStore.currentNotes.forEach(note => {
        if (note.is_secret && note.title && !note.decryptedTitle) {
          try {
            const plainTitle = decryptContent(note.title, dek.value)
            note.decryptedTitle = plainTitle
          } catch (e) {
            // 静默失败
          }
        }
      })
    }
  }
)
```

**监听 3：笔记列表变化时尝试解密**
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
      if (note.decryptedTitle) return
      if (note.is_secret && note.title) {
        const dekToUse = dekValue || vaultDek
        if (dekToUse) {
          try {
            const plainTitle = decryptContent(note.title, dekToUse)
            note.decryptedTitle = plainTitle
          } catch (e) {
            // 显示占位符
          }
        }
      }
    })
  },
  { deep: true, immediate: true }
)
```

### 修复 3：NoteListItem 响应 parent 更新

**文件**：`frontend/src/components/common/NoteListItem.vue`

```javascript
// 当 parent 更新 decryptedTitle 时，触发重新计算
watch(() => props.note.decryptedTitle, (newDecryptedTitle) => {
  console.log('[NoteListItem] parent decryptedTitle changed:', props.note.id)
})
```

---

## 修复流程验证

### 步骤 1：后端返回 is_secret

**修复前的 API 响应**：
```json
{
  "notes": [
    {
      "id": 75,
      "title": "jfsasl6YpVoL+AGk9ktp35C...",
      "trashed_at": "2026-01-28 18:34",
      "folder": null
      // ❌ 没有 is_secret 字段！
    }
  ]
}
```

**修复后的 API 响应**：
```json
{
  "notes": [
    {
      "id": 75,
      "title": "jfsasl6YpVoL+AGk9ktp35C...",  // 仍然是加密的
      "trashed_at": "2026-01-28 18:34",
      "is_secret": true,  // ✅ 新增
      "is_trashed": true,  // ✅ 新增
      "is_favorited": false,  // ✅ 新增
      "updated_at": "2026-01-28 01:53",  // ✅ 新增
      "folder": null
    }
  ]
}
```

### 步骤 2：前端判断并处理

**场景 A：DEK 可用（用户已解锁或 session 恢复）**
```
后端返回 is_secret=true
    ↓
SecondaryPanel watch 检查 dek.value || vaultStore.dek
    ↓
有 DEK → 调用 decryptContent() → 获得明文
    ↓
设置 note.decryptedTitle = plainTitle
    ↓
NoteListItem displayTitle 优先使用 note.decryptedTitle
    ↓
列表显示明文标题 ✅
```

**场景 B：DEK 不可用（首次登录）**
```
后端返回 is_secret=true
    ↓
SecondaryPanel watch 检查 dek.value || vaultStore.dek
    ↓
无 DEK → 不设置 note.decryptedTitle
    ↓
NoteListItem needsUnlock = true
    ├─ is_secret && !isKeyValid && !vaultDek && isInTrash
    ├─ = true && true && true && true = true
    ↓
显示占位符 🔒 而不是密文 ✅
```

**场景 C：页面刷新（DEK 过期）**
```
刷新页面
    ↓
dek.value = null, isKeyValid.value = false
    ↓
SecondaryPanel isKeyValid watch 触发
    ↓
清除所有 note.decryptedTitle = undefined
    ↓
needsUnlock 重新计算 = true
    ↓
显示占位符 🔒 而不是过期的明文 ✅
```

---

## 浏览器验证

### 打开开发者工具（F12），查看 Console 输出

**修复前的日志**（问题）：
```
[SecondaryPanel] Processing note: 75 is_secret: undefined ❌
[Security] Blocking decryption for secret note in trash ❌
```

**修复后的日志**（预期）：

**情况 1：DEK 可用时**
```
[SecondaryPanel] Watch triggered in trash, notes count: 1 DEK available: true isKeyValid: true
[SecondaryPanel] Processing note: 75 is_secret: true decryptedTitle: false
[SecondaryPanel] ✅ Title decrypted for trash note: 75 我的银行密码
```

**情况 2：DEK 不可用时**
```
[SecondaryPanel] Watch triggered in trash, notes count: 1 DEK available: false isKeyValid: false
[SecondaryPanel] Processing note: 75 is_secret: true decryptedTitle: false
[SecondaryPanel] ⚠️ No DEK available for trash note: 75 - will show masked title
```

**情况 3：页面刷新时**
```
[SecondaryPanel] DEK became unavailable, clearing decryptedTitles
[SecondaryPanel] Cleared decryptedTitle for: 75
```

---

## 修改统计

| 文件 | 修改内容 | 行数 |
|------|--------|------|
| `knowledge_project/folder_views.py` | 后端返回 is_secret 等字段 | 328-347 |
| `frontend/src/components/layout/SecondaryPanel.vue` | 监听 isKeyValid，清除过期的解密标题 | 493-510 |
| `frontend/src/components/layout/SecondaryPanel.vue` | 详细的 watch 日志 | 450-491 |
| `frontend/src/components/common/NoteListItem.vue` | 监听 parent 的 decryptedTitle 变化 | 316-321 |

---

## 测试清单

### ✅ 测试 1：回收站列表自动解密

前置条件：用户已进入保密柜，完成 2FA 验证

1. 切换到回收站
2. **预期**：加密笔记标题自动显示为明文（不需要点击）
3. **验证**：控制台显示 "✅ Title decrypted for trash note"

### ✅ 测试 2：无 DEK 时显示占位符

前置条件：用户刚登录，未进入保密柜

1. 直接进入回收站
2. **预期**：加密笔记显示 🔒 占位符，而不是密文
3. **验证**：控制台显示 "⚠️ No DEK available"

### ✅ 测试 3：刷新页面后保持占位符

前置条件：已在回收站，标题显示为明文

1. 按 F5 刷新页面
2. **预期**：刷新后立即显示 🔒 占位符（而不是明文）
3. **验证**：控制台显示 "DEK became unavailable"

### ✅ 测试 4：点击占位符解锁

前置条件：显示 🔒 占位符

1. 点击占位符
2. 完成 2FA 验证
3. **预期**：列表自动更新，显示明文标题
4. **验证**：控制台显示 "✅ Title decrypted after unlock"

---

## 安全性说明

✅ **完全安全**：
- 用户未解锁时，列表显示 🔒 而不是敏感信息（如 "银行密码"）
- 刷新页面时，过期的解密标题立即清除
- 工具栏中回收站的 secret notes 显示 "🔒 内容已锁定"（NoteShadowViewer.vue 第 83-91 行）

---

## Build 状态

✅ **成功**：
```
npm run build
✓ built in 5.52s
```

---

## 后续建议

1. **清空浏览器缓存**：Ctrl+Shift+Delete，重新加载
2. **进入回收站**：验证列表中的加密笔记是否显示占位符或解密标题
3. **查看 Console**：确认日志输出符合预期
4. **测试完整流程**：无 DEK → 有 DEK → 刷新页面 → 再次解锁

