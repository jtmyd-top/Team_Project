<template>
  <div class="folder-tree-item" :class="{ 'is-expanded': isExpanded }">
    <div
      class="folder-row"
      :class="{ 'is-editing': isEditing, 'is-drop-target': isDragOver }"
      @click="handleClick"
      @contextmenu.prevent="showContextMenu"
      @dragover.prevent="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <!-- 展开/收起图标 -->
      <button 
        v-if="hasChildren"
        class="toggle-btn"
        @click.stop="toggleExpand"
      >
        <i class="fas" :class="isExpanded ? 'fa-chevron-down' : 'fa-chevron-right'"></i>
      </button>
      <span v-else class="toggle-placeholder"></span>
      
      <!-- 文件夹图标 -->
      <i class="fas folder-icon" :class="isExpanded ? 'fa-folder-open' : 'fa-folder'"></i>
      
      <!-- 名称（编辑模式） -->
      <input
        v-if="isEditing"
        ref="nameInput"
        v-model="editName"
        class="name-input"
        @blur="finishEdit"
        @keyup.enter="finishEdit"
        @keyup.escape="cancelEdit"
        @click.stop
      />
      
      <!-- 名称（显示模式） -->
      <span v-else class="folder-name">{{ folder.name }}</span>
      
      <!-- 笔记数量 -->
      <span v-if="folder.notes_count > 0" class="notes-count">
        {{ folder.notes_count }}
      </span>
      
      <!-- 操作按钮 -->
      <div class="folder-actions" @click.stop>
        <button class="action-btn" @click="startEdit" title="重命名">
          <i class="fas fa-pen"></i>
        </button>
        <button class="action-btn" @click="handleCreateSubfolder" title="新建子文件夹">
          <i class="fas fa-folder-plus"></i>
        </button>
        <button class="action-btn delete-btn" @click="handleDelete" title="删除">
          <i class="fas fa-trash"></i>
        </button>
      </div>
    </div>
    
    <!-- 子文件夹 -->
    <div v-if="hasChildren && isExpanded" class="folder-children">
      <FolderTreeItem
        v-for="child in folder.children"
        :key="child.id"
        :folder="child"
        @click="$emit('click', $event)"
        @rename="$emit('rename', $event.folder, $event.newName)"
        @delete="$emit('delete', $event)"
        @create-subfolder="$emit('create-subfolder', $event)"
        @note-drop="$emit('note-drop', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'

const props = defineProps({
  folder: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['click', 'rename', 'delete', 'create-subfolder', 'note-drop'])

// 状态
const isExpanded = ref(false)
const isEditing = ref(false)
const editName = ref('')
const nameInput = ref(null)
const isDragOver = ref(false)

// 计算属性
const hasChildren = computed(() => {
  return props.folder.children && props.folder.children.length > 0
})

// 拖拽相关方法
function handleDragOver(event) {
  event.dataTransfer.dropEffect = 'move'
  isDragOver.value = true
}

function handleDragLeave(event) {
  // 确保只在真正离开时才取消高亮（避免进入子元素时触发）
  const rect = event.currentTarget.getBoundingClientRect()
  const x = event.clientX
  const y = event.clientY

  if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
    isDragOver.value = false
  }
}

function handleDrop(event) {
  isDragOver.value = false

  const data = event.dataTransfer.getData('application/json')
  if (!data) return

  try {
    const payload = JSON.parse(data)

    // 确保拖拽的是笔记
    if (payload.type === 'NOTE_ITEM') {
      // 如果已经在这个文件夹中，不执行移动
      if (payload.currentFolderId === props.folder.id) {
        console.log('笔记已在此文件夹中，无需移动')
        return
      }

      // 发出事件，让父组件处理 API 调用
      emit('note-drop', {
        noteId: payload.id,
        noteTitle: payload.title,
        targetFolderId: props.folder.id,
        targetFolderName: props.folder.name
      })
    }
  } catch (e) {
    console.error('解析拖拽数据失败:', e)
  }
}

// 方法
function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

function handleClick() {
  if (!isEditing.value) {
    emit('click', props.folder)
  }
}

function startEdit() {
  editName.value = props.folder.name
  isEditing.value = true
  nextTick(() => {
    nameInput.value?.focus()
    nameInput.value?.select()
  })
}

function finishEdit() {
  if (editName.value.trim() && editName.value !== props.folder.name) {
    emit('rename', { folder: props.folder, newName: editName.value.trim() })
  }
  isEditing.value = false
}

function cancelEdit() {
  isEditing.value = false
  editName.value = ''
}

function handleDelete() {
  emit('delete', props.folder)
}

function handleCreateSubfolder() {
  emit('create-subfolder', props.folder)
}

function showContextMenu(e) {
  // 可以扩展为显示右键菜单
}
</script>

<style scoped>
.folder-tree-item {
  user-select: none;
}

.folder-row {
  display: flex;
  align-items: center;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
  gap: 6px;
}

.folder-row:hover {
  background: var(--hover-bg, rgba(0,0,0,0.05));
}

/* 拖拽放置目标高亮 */
.folder-row.is-drop-target {
  background: var(--primary-bg, rgba(64, 158, 255, 0.15));
  border: 2px dashed var(--primary-color, #409eff);
  border-radius: 6px;
  color: var(--primary-color, #409eff);
}

.folder-row.is-drop-target .folder-icon {
  color: var(--primary-color, #409eff);
  transform: scale(1.1);
}

.folder-row.is-drop-target .folder-name {
  color: var(--primary-color, #409eff);
  font-weight: 600;
}

.folder-row:hover .folder-actions {
  opacity: 1;
}

.toggle-btn {
  width: 20px;
  height: 20px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #999);
  font-size: 10px;
  border-radius: 4px;
  flex-shrink: 0;
}

.toggle-btn:hover {
  background: var(--hover-bg, rgba(0,0,0,0.1));
}

.toggle-placeholder {
  width: 20px;
  flex-shrink: 0;
}

.folder-icon {
  color: var(--warning-color, #e6a23c);
  font-size: 14px;
  flex-shrink: 0;
}

.folder-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.name-input {
  flex: 1;
  border: 1px solid var(--primary-color, #409eff);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 13px;
  outline: none;
  background: var(--bg-primary, #fff);
}

.notes-count {
  font-size: 11px;
  color: var(--text-secondary, #999);
  background: var(--bg-tertiary, #e0e0e0);
  padding: 1px 6px;
  border-radius: 8px;
  flex-shrink: 0;
}

.folder-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.2s;
}

.folder-actions .action-btn {
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #999);
  font-size: 11px;
  border-radius: 4px;
}

.folder-actions .action-btn:hover {
  background: var(--hover-bg, rgba(0,0,0,0.1));
  color: var(--primary-color, #409eff);
}

.folder-actions .delete-btn:hover {
  color: var(--error-color, #f56c6c);
}

.folder-children {
  padding-left: 20px;
}
</style>
