# 保险柜前端功能实现检查清单

**完成时间**: 2026-01-25
**后端**: ✅ 已完成
**前端**: 🔄 需要实现

---

## 📋 后端更改总结

| 文件 | 改动 | 状态 |
|-----|------|------|
| `views.py` | 修改 `create_note_api` 支持 `is_secret` 参数 | ✅ |
| `views.py` | 修改 `get_all_notes_api` 过滤+返回 `is_secret` | ✅ |
| `views.py` | 修改 `vault_notes_list` 返回完整字段 | ✅ |
| `folder_views.py` | 修改 `folder_notes_api` 返回 `is_secret` | ✅ |
| `folder_views.py` | 修改 `inbox_notes_api` 过滤+返回 `is_secret` | ✅ |

**已有功能（无需修改）**:
- ✅ `note_toggle_secret`: 切换保密状态 API
- ✅ 2FA 保护保险柜访问
- ✅ 中间件防止未授权访问

---

## 🎯 前端需要实现的功能

### ✅ 检查清单

#### 1. 笔记列表项 (NoteListItem.vue)
- [ ] 添加 `is_secret` 属性支持
- [ ] 显示锁定图标（当 is_secret=true）
- [ ] 添加右键菜单事件处理
- [ ] 样式：锁定图标为红色，位于标题前

#### 2. 右键菜单 (NoteContextMenu.vue)
- [ ] 接收 `isSecret` 参数
- [ ] 添加分隔线
- [ ] 添加"加入保险柜"/"移出保险柜"菜单项
- [ ] 添加 `@toggle-secret` 事件发射
- [ ] 图标：lock/unlock

#### 3. 笔记列表面板 (SecondaryPanel.vue)
- [ ] 监听 NoteListItem 的 `@context-menu` 事件
- [ ] 显示右键菜单
- [ ] 处理 `@toggle-secret` 事件
- [ ] 调用 API 切换保密状态
- [ ] 刷新笔记列表

#### 4. 笔记编辑器 (KnowledgeList.vue)
- [ ] 修改 `handleCreateNote()` 检查是否在保险柜视图
- [ ] 在保险柜中创建时传递 `is_secret: true`
- [ ] 保存 `is_secret` 到 `currentNoteData`

---

## 📝 前端代码修改示例

### 1️⃣ NoteListItem.vue

**修改位置**：`frontend/src/components/common/NoteListItem.vue`

```vue
<template>
  <div class="note-item" @contextmenu.prevent="handleContextMenu" @click="selectNote">
    <!-- 保密图标 -->
    <span v-if="note.is_secret" class="vault-badge" title="保密笔记">
      <i class="fas fa-lock"></i>
    </span>

    <!-- 标题 -->
    <span class="note-title">{{ note.title }}</span>

    <!-- 时间戳等其他内容保持不变 -->
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  note: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['context-menu', 'select'])

// 处理右键菜单
const handleContextMenu = (e) => {
  emit('context-menu', {
    event: e,
    noteId: props.note.id,
    isSecret: props.note.is_secret || false
  })
}

// 选择笔记
const selectNote = () => {
  emit('select', props.note.id)
}
</script>

<style scoped>
.note-item {
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.note-item:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

.vault-badge {
  color: #f56c6c;
  margin-right: 6px;
  font-size: 0.9em;
  flex-shrink: 0;
}

.note-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
```

### 2️⃣ NoteContextMenu.vue

**修改位置**：`frontend/src/components/common/NoteContextMenu.vue`

```vue
<template>
  <div v-if="visible" class="context-menu" :style="{ top: `${y}px`, left: `${x}px` }">
    <!-- 现有菜单项 -->
    <div class="menu-item" @click="handleFavorite">
      <i class="fas fa-star"></i>
      {{ isFavorited ? '取消收藏' : '添加收藏' }}
    </div>

    <!-- 分隔线 -->
    <div class="menu-divider"></div>

    <!-- 保险柜菜单项 (新增) -->
    <div class="menu-item" @click="handleToggleSecret">
      <i :class="isSecret ? 'fas fa-unlock' : 'fas fa-lock'"></i>
      {{ isSecret ? '移出保险柜' : '加入保险柜' }}
    </div>

    <!-- 其他菜单项 -->
    <div class="menu-item danger" @click="handleDelete">
      <i class="fas fa-trash"></i>
      删除
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  visible: Boolean,
  x: Number,
  y: Number,
  noteId: [String, Number],
  isSecret: Boolean,
  isFavorited: Boolean
})

const emit = defineEmits(['toggle-secret', 'favorite', 'delete', 'close'])

const isSecret = computed(() => props.isSecret || false)
const isFavorited = computed(() => props.isFavorited || false)

const handleToggleSecret = () => {
  emit('toggle-secret')
  emit('close')
}

const handleFavorite = () => {
  emit('favorite')
  emit('close')
}

const handleDelete = () => {
  emit('delete')
  emit('close')
}
</script>

<style scoped>
.context-menu {
  position: fixed;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  min-width: 180px;
  z-index: 1000;
}

.menu-item {
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: background-color 0.2s;
  font-size: 14px;
}

.menu-item:hover {
  background-color: #f5f5f5;
}

.menu-item.danger {
  color: #f56c6c;
}

.menu-divider {
  height: 1px;
  background-color: #e0e0e0;
  margin: 4px 0;
}
</style>
```

### 3️⃣ SecondaryPanel.vue

**修改位置**：`frontend/src/components/layout/SecondaryPanel.vue`

```javascript
// 在 <script setup> 中添加：

const showContextMenu = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextMenuData = ref({})

// 处理右键菜单
const handleNoteContextMenu = ({ event, noteId, isSecret }) => {
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  contextMenuData.value = { noteId, isSecret }
  showContextMenu.value = true
}

// 切换保密状态
const handleToggleSecret = async () => {
  try {
    const noteId = contextMenuData.value.noteId
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
      // 刷新笔记列表
      await loadNotes()
    }
  } catch (error) {
    ElMessage.error('操作失败')
    console.error(error)
  }
}

// 辅助函数获取 CSRF Token
const getCsrfToken = () => {
  return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
         document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.split('=')[1] ||
         ''
}

// 在模板中添加右键菜单组件：
// <NoteContextMenu
//   :visible="showContextMenu"
//   :x="contextMenuX"
//   :y="contextMenuY"
//   :note-id="contextMenuData.noteId"
//   :is-secret="contextMenuData.isSecret"
//   @toggle-secret="handleToggleSecret"
//   @close="showContextMenu = false"
// />
```

### 4️⃣ KnowledgeList.vue

**修改位置**：`frontend/src/components/knowledge/KnowledgeList.vue`

```javascript
// 修改 handleCreateNote 函数：

async function handleCreateNote(folderId = null) {
  // 保存检查
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
    // 检查是否在保险柜视图
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
        is_secret: isVaultModule  // 关键：在保险柜中创建时自动标记为保密
      })
    })

    if (!response.ok) throw new Error('创建笔记失败')

    const data = await response.json()

    // 设置当前笔记
    isLoadingNote.value = true
    currentNoteId.value = data.id
    currentNoteData.value = {
      id: data.id,
      title: data.title,
      content: '',
      toc: [],
      updated_at: new Date().toISOString(),
      author: request.user.username,
      is_public: false,
      is_secret: isVaultModule,  // 保存保密状态
      public_url: ''
    }

    viewMode.value = 'edit'
    hasUnsavedChanges.value = false
    isLoadingNote.value = false

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

## 🔌 组件通信

### 事件流

```
NoteListItem
  ├─ @context-menu
  │  └─> SecondaryPanel (handleNoteContextMenu)
  │      └─> 显示 NoteContextMenu
  │
NoteContextMenu
  ├─ @toggle-secret
  │  └─> SecondaryPanel (handleToggleSecret)
  │      └─> API: POST /api/notes/<id>/toggle-secret/
  │          └─> 刷新笔记列表

KnowledgeList
  ├─ 创建笔记 (handleCreateNote)
  │  └─> 检查 sidebarStore.activeModule === 'vault'
  │      └─> API: POST /api/notes/create/
  │          └─> is_secret: true (在保险柜中)
```

---

## 💾 保存检查清单

完成以上修改后，依次检查：

- [ ] NoteListItem.vue 显示锁定图标
- [ ] 右键点击笔记显示菜单
- [ ] 菜单显示"加入保险柜"/"移出保险柜"
- [ ] 点击菜单项切换保密状态
- [ ] 保密笔记自动移到保险柜
- [ ] 在保险柜中创建笔记时自动标记为保密
- [ ] 保密笔记不出现在"全部笔记"中
- [ ] 保密笔记只出现在"保险柜"中

---

## 🚀 提交代码

完成所有修改后：

```bash
# 1. 查看改动
git status

# 2. 添加前端文件
git add frontend/src/components/

# 3. 提交
git commit -m "前端：实现保险柜功能 - 右键菜单和笔记隐藏

- 添加 NoteListItem 锁定图标指示
- 添加右键菜单选项：加入/移出保险柜
- 实现切换保密状态功能
- 创建笔记时自动设置 is_secret（保险柜）
- 前端过滤保密笔记的显示

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

# 4. 推送
git push origin main
```

---

**完成所有前端改动后，整个保险柜功能就完全实现了！** ✨

---

**文档版本**: 1.0
**最后更新**: 2026-01-25
