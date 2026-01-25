# 保险柜功能完整实现 - 前端集成指南

**更新时间**: 2026-01-25
**目标**: 在笔记列表中添加右键菜单，支持加入/移出保险柜

---

## 📋 已完成的后端改动

✅ **API 更新**:
- ✓ `get_all_notes_api`: 现在返回 `is_secret` 字段并过滤掉保密笔记
- ✓ `folder_notes_api`: 添加 `is_secret` 字段到响应
- ✓ `inbox_notes_api`: 过滤掉保密笔记，添加 `is_secret` 字段
- ✓ `vault_notes_list`: 返回完整的笔记信息（包括 `is_secret`, `folder_id` 等）
- ✓ `create_note_api`: 支持 `is_secret` 参数，在保险柜中创建的笔记自动标记
- ✓ `note_toggle_secret`: 切换笔记保密状态（已存在）

---

## 🎯 前端需要实现的功能

### 1. NoteListItem.vue 修改

**添加**:
- 保密笔记的锁定图标 indicator
- 右键菜单支持

```vue
<template>
  <div class="note-item" @contextmenu.prevent="handleContextMenu">
    <!-- 现有内容 -->
    <div class="note-title">
      <!-- 添加锁定图标 -->
      <i v-if="note.is_secret" class="fas fa-lock vault-icon" title="保密笔记"></i>
      {{ note.title }}
    </div>
  </div>
</template>

<script setup>
// 添加
const handleContextMenu = (e) => {
  emit('context-menu', {
    x: e.clientX,
    y: e.clientY,
    noteId: note.id,
    isSecret: note.is_secret
  })
}
</script>

<style scoped>
.vault-icon {
  color: #f56c6c;
  margin-right: 4px;
  font-size: 12px;
}
</style>
```

### 2. NoteContextMenu.vue 修改

**添加** "加入保险柜" / "移出保险柜" 选项:

```vue
<template>
  <div class="context-menu" v-if="visible" :style="{ top: y + 'px', left: x + 'px' }">
    <!-- 现有菜单项 -->

    <!-- 新增：保险柜选项 -->
    <div class="menu-divider"></div>
    <div class="menu-item" @click="handleToggleSecret">
      <i :class="isSecret ? 'fas fa-unlock' : 'fas fa-lock'"></i>
      {{ isSecret ? '移出保险柜' : '加入保险柜' }}
    </div>
  </div>
</template>

<script setup>
const emit = defineEmits(['toggle-secret'])
const isSecret = computed(() => contextMenuData.value?.isSecret || false)

const handleToggleSecret = async () => {
  emit('toggle-secret', noteId.value)
  close()
}
</script>
```

### 3. SecondaryPanel.vue 修改

**笔记列表中添加右键菜单回调**:

```javascript
const handleNoteContextMenu = ({ x, y, noteId, isSecret }) => {
  // 显示右键菜单
  showContextMenu(x, y, noteId, isSecret)
}

const handleToggleSecret = async (noteId) => {
  try {
    const response = await fetch(`/api/notes/${noteId}/toggle-secret/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
        'Content-Type': 'application/json'
      }
    })

    const data = await response.json()
    if (data.status === 'success') {
      ElMessage.success(data.message)

      // 刷新笔记列表
      await loadNotes()
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}
```

### 4. KnowledgeList.vue 修改

**在保险柜视图中创建笔记时，自动设置 is_secret=True**:

```javascript
const handleCreateNote = async (folderId = null) => {
  // 检查是否在保险柜视图中
  const isVaultView = sidebarStore.activeModule === 'vault'

  try {
    const response = await fetch('/api/notes/create/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        title: '无标题笔记',
        content: '',
        folder_id: folderId,
        is_secret: isVaultView  // 在保险柜中创建时自动标记为保密
      })
    })

    const data = await response.json()
    // ... 处理响应
  } catch (error) {
    ElMessage.error('创建失败')
  }
}
```

---

## 📝 实现步骤

### 步骤 1: 修改 NoteListItem.vue

**文件**: `frontend/src/components/common/NoteListItem.vue`

在模板中添加锁定图标：

```vue
<template>
  <div class="note-item-wrapper" @contextmenu.prevent="handleContextMenu">
    <div class="note-item">
      <!-- 锁定图标 -->
      <span v-if="note.is_secret" class="vault-badge" title="保密笔记">
        <i class="fas fa-lock"></i>
      </span>

      <!-- 现有的标题和信息 -->
      <span class="note-title">{{ note.title }}</span>

      <!-- ... 其他内容 ... -->
    </div>
  </div>
</template>

<script setup>
// 属性
const props = defineProps({
  note: {
    type: Object,
    required: true
  }
})

// 事件
const emit = defineEmits(['context-menu', 'select'])

// 右键菜单
const handleContextMenu = (e) => {
  emit('context-menu', {
    event: e,
    noteId: props.note.id,
    isSecret: props.note.is_secret
  })
}
</script>

<style scoped>
.vault-badge {
  color: #f56c6c;
  margin-right: 4px;
  font-size: 0.85em;
}
</style>
```

### 步骤 2: 修改 NoteContextMenu.vue

**文件**: `frontend/src/components/common/NoteContextMenu.vue`

在菜单中添加保险柜选项：

```vue
<template>
  <div class="context-menu" v-if="visible" :style="position">
    <!-- 现有菜单项 -->
    <div class="menu-item" @click="handleFavorite">
      <i class="fas fa-star"></i>
      {{ isFavorited ? '取消收藏' : '添加到收藏' }}
    </div>

    <!-- 分隔线 -->
    <div class="menu-divider"></div>

    <!-- 保险柜选项 (新增) -->
    <div class="menu-item" @click="handleToggleSecret">
      <i :class="isSecret ? 'fas fa-unlock' : 'fas fa-lock'"></i>
      {{ isSecret ? '移出保险柜' : '加入保险柜' }}
    </div>

    <!-- 其他菜单项... -->
  </div>
</template>

<script setup>
const props = defineProps({
  noteId: [String, Number],
  isSecret: Boolean
})

const emit = defineEmits(['toggle-secret', 'favorite', 'delete'])

const handleToggleSecret = () => {
  emit('toggle-secret')
  close()
}

const close = () => {
  visible.value = false
}
</script>
```

### 步骤 3: 修改 SecondaryPanel.vue

**文件**: `frontend/src/components/layout/SecondaryPanel.vue`

添加右键菜单处理和切换保险柜逻辑：

```javascript
// 右键菜单处理
const handleNoteContextMenu = (data) => {
  contextMenuPos.value = {
    x: data.event.clientX,
    y: data.event.clientY
  }
  selectedNoteForMenu.value = {
    id: data.noteId,
    isSecret: data.isSecret
  }
  showContextMenu.value = true
}

// 切换保险柜
const handleToggleVault = async () => {
  try {
    const noteId = selectedNoteForMenu.value.id
    const response = await fetch(`/api/notes/${noteId}/toggle-secret/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrfToken(),
        'Content-Type': 'application/json'
      }
    })

    const data = await response.json()
    if (data.status === 'success') {
      ElMessage.success(data.message)

      // 刷新当前视图的笔记列表
      await loadNotes()
    }
  } catch (error) {
    console.error('切换保险柜失败:', error)
    ElMessage.error('切换保险柜失败')
  }
}
```

### 步骤 4: 修改 KnowledgeList.vue

**文件**: `frontend/src/components/knowledge/KnowledgeList.vue`

修改创建笔记逻辑以支持保险柜：

```javascript
const handleCreateNote = async (folderId = null) => {
  // 如果有未保存的更改，提示保存
  if (hasUnsavedChanges.value) {
    try {
      await ElMessageBox.confirm('当前笔记有未保存的更改，是否保存？', '提示', {
        confirmButtonText: '保存',
        cancelButtonText: '放弃',
        type: 'warning'
      })
      await handleSave()
    } catch (e) {
      if (e !== 'cancel') {
        hasUnsavedChanges.value = false
      } else {
        return
      }
    }
  }

  try {
    // 检查是否在保险柜视图中
    const isVaultModule = sidebarStore.activeModule === 'vault'

    const response = await fetch('/api/notes/create/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrfToken(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        title: '无标题笔记',
        content: '',
        folder_id: folderId || null,
        is_secret: isVaultModule  // 在保险柜中创建时自动标记
      })
    })

    if (!response.ok) throw new Error('创建笔记失败')

    const data = await response.json()

    // 新创建的笔记设为当前笔记
    currentNoteId.value = data.id
    currentNoteData.value = {
      id: data.id,
      title: data.title,
      content: '',
      toc: [],
      updated_at: new Date().toISOString(),
      author: request.user,
      is_public: false,
      is_secret: isVaultModule  // 记录保密状态
    }

    viewMode.value = 'edit'
    hasUnsavedChanges.value = false

    // 刷新笔记列表
    await sidebarStore.loadModuleData()

    ElMessage.success('笔记已创建')
  } catch (error) {
    console.error('创建笔记失败:', error)
    ElMessage.error('创建笔记失败')
  }
}
```

---

## 🔌 API 集成

### 添加 API 调用函数

**文件**: `frontend/src/api/note.js` (如果不存在则创建)

```javascript
// 切换笔记保密状态
export const toggleNoteSecret = (noteId) => {
  return fetch(`/api/notes/${noteId}/toggle-secret/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCsrfToken(),
      'Content-Type': 'application/json'
    }
  }).then(r => r.json())
}

// 创建笔记
export const createNote = (title = '无标题笔记', content = '', folderId = null, isSecret = false) => {
  return fetch('/api/notes/create/', {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCsrfToken(),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      title,
      content,
      folder_id: folderId,
      is_secret: isSecret
    })
  }).then(r => r.json())
}
```

---

## ✨ 最终效果

### 功能清单

- ✓ 笔记列表项显示锁定图标（保密笔记）
- ✓ 右键菜单显示 "加入保险柜" / "移出保险柜" 选项
- ✓ 点击菜单项切换笔记保密状态
- ✓ 在保险柜中创建的笔记自动标记为保密
- ✓ 保密笔记不出现在"全部笔记"视图中
- ✓ 保密笔记只出现在"保险柜"视图中
- ✓ 成功/失败提示信息

### 用户流程

```
1. 用户在笔记列表中右键点击某笔记
2. 右键菜单出现，显示"加入保险柜"选项
3. 用户点击该选项
4. API 调用切换笔记状态
5. 笔记自动从"全部笔记"移到"保险柜"
6. 笔记项显示锁定图标

反向流程：
1. 在保险柜视图中右键点击笔记
2. 右键菜单显示"移出保险柜"选项
3. 点击后笔记恢复到普通状态
4. 笔记从"保险柜"移回"全部笔记"
```

---

## 📚 参考

### API 端点

```
POST /api/notes/<id>/toggle-secret/      # 切换保密状态
POST /api/notes/create/                  # 创建笔记（支持 is_secret）
GET  /api/vault/notes/                   # 获取保险柜笔记
GET  /api/notes/all/                     # 获取所有笔记（不含保密）
GET  /api/folders/<id>/notes/            # 获取文件夹笔记（不含保密）
GET  /api/folders/inbox/notes/           # 获取收件箱笔记（不含保密）
```

### 返回值示例

```json
{
  "id": 123,
  "title": "My Secret Note",
  "is_secret": true,
  "created_at": "2026-01-25T10:00:00Z",
  "updated_at": "2026-01-25T10:00:00Z",
  "folder_id": null,
  "is_favorited": false
}
```

---

## 🔒 安全考虑

- ✓ 保密笔记使用 is_secret 字段标记
- ✓ 服务器端验证用户权限
- ✓ 2FA 验证保护保险柜访问
- ✓ 中间件防止未授权访问

---

**实现完成后需要提交 Git！**

```bash
git add .
git commit -m "前端：添加保险柜功能 - 右键菜单和可视化指示器"
git push origin main
```

---

**文档版本**: 1.0
**最后更新**: 2026-01-25
