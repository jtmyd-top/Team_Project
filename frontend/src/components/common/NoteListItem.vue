<template>
  <div
    class="note-list-item"
    :class="{ 'is-active': active, 'is-dragging': isDragging }"
    draggable="true"
    @click="handleClick"
    @contextmenu.prevent="handleContextMenu"
    @dragstart="handleDragStart"
    @dragend="handleDragEnd"
  >
    <!-- 拖拽手柄 -->
    <div class="drag-handle" title="拖动到文件夹">
      <i class="fas fa-grip-vertical"></i>
    </div>

    <!-- 左侧内容 -->
    <div class="note-content">
      <!-- 标题 - 编辑状态 -->
      <input
        v-if="isEditing"
        ref="titleInput"
        v-model="editingTitle"
        type="text"
        class="note-title-edit"
        @click.stop
        @keyup.enter="saveRename"
        @keyup.esc="cancelRename"
        @blur="saveRename"
      />

      <!-- 标题 - 正常状态 -->
      <h4 v-else class="note-title">{{ note.title || '无标题' }}</h4>

      <!-- 元信息 -->
      <div class="note-meta">
        <!-- 文件夹信息 -->
        <span v-if="showFolder && note.folder" class="folder-tag">
          <i class="fas fa-folder"></i>
          {{ note.folder.name }}
        </span>

        <!-- 更新时间 -->
        <span class="update-time">
          {{ showTrashActions ? note.trashed_at : note.updated_at }}
        </span>
      </div>
    </div>
    
    <!-- 右侧操作 -->
    <div class="note-actions" @click.stop>
      <!-- 常规操作 -->
      <template v-if="!showTrashActions">
        <!-- 收藏按钮 -->
        <button 
          class="action-btn favorite-btn"
          :class="{ 'is-favorited': note.is_favorited }"
          @click="handleFavorite"
          :title="note.is_favorited ? '取消收藏' : '收藏'"
        >
          <i class="fas" :class="note.is_favorited ? 'fa-star' : 'fa-star'"></i>
        </button>
        
        <!-- 删除按钮 -->
        <button 
          class="action-btn delete-btn"
          @click="handleTrash"
          title="移入回收站"
        >
          <i class="fas fa-trash"></i>
        </button>
      </template>
      
      <!-- 回收站操作 -->
      <template v-else>
        <!-- 恢复按钮 -->
        <button 
          class="action-btn restore-btn"
          @click="handleRestore"
          title="恢复"
        >
          <i class="fas fa-undo"></i>
        </button>
        
        <!-- 永久删除按钮 -->
        <button 
          class="action-btn delete-btn"
          @click="handleDelete"
          title="永久删除"
        >
          <i class="fas fa-trash-alt"></i>
        </button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  note: {
    type: Object,
    required: true
  },
  active: {
    type: Boolean,
    default: false
  },
  showFolder: {
    type: Boolean,
    default: false
  },
  showTrashActions: {
    type: Boolean,
    default: false
  },
  editingNoteId: {
    type: [Number, String],
    default: null
  }
})

const emit = defineEmits(['click', 'favorite', 'trash', 'restore', 'delete', 'contextmenu', 'rename'])

// 拖拽状态
const isDragging = ref(false)

// 编辑状态
const isEditing = ref(false)
const editingTitle = ref('')
const titleInput = ref(null)

// 监听 editingNoteId 的变化
watch(() => props.editingNoteId, (newVal) => {
  if (newVal === props.note.id) {
    startEditing()
  } else if (isEditing.value) {
    cancelRename()
  }
})

// 开始编辑
function startEditing() {
  isEditing.value = true
  editingTitle.value = props.note.title || ''
  nextTick(() => {
    titleInput.value?.focus()
    titleInput.value?.select()
  })
}

// 保存重命名
function saveRename() {
  if (!isEditing.value) return

  const newTitle = editingTitle.value.trim()
  if (newTitle && newTitle !== props.note.title) {
    emit('rename', props.note, newTitle)
  }

  isEditing.value = false
  editingTitle.value = ''
}

// 取消重命名
function cancelRename() {
  isEditing.value = false
  editingTitle.value = ''
}

// 开始拖拽
function handleDragStart(event) {
  isDragging.value = true

  const noteData = {
    type: 'NOTE_ITEM',
    id: props.note.id,
    title: props.note.title,
    currentFolderId: props.note.folder?.id || null
  }

  // 设置拖拽数据
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('application/json', JSON.stringify(noteData))

  // 派发全局事件，通知浮动面板显示
  window.dispatchEvent(new CustomEvent('note-drag-start', {
    detail: {
      noteId: props.note.id,
      noteTitle: props.note.title,
      currentFolderId: props.note.folder?.id || null
    }
  }))
}

// 结束拖拽
function handleDragEnd(event) {
  isDragging.value = false

  // 派发全局事件，通知浮动面板隐藏
  window.dispatchEvent(new CustomEvent('note-drag-end'))
}

function handleClick() {
  emit('click', props.note)
}

function handleContextMenu(event) {
  emit('contextmenu', {
    note: props.note,
    x: event.clientX,
    y: event.clientY
  })
}

function handleFavorite() {
  emit('favorite', props.note)
}

function handleTrash() {
  emit('trash', props.note)
}

function handleRestore() {
  emit('restore', props.note)
}

function handleDelete() {
  emit('delete', props.note)
}
</script>

<style scoped>
.note-list-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.2s, opacity 0.2s, transform 0.2s;
  border-bottom: 1px solid var(--border-light, rgba(0,0,0,0.05));
}

.note-list-item:hover {
  background: var(--hover-bg, rgba(0,0,0,0.03));
}

.note-list-item:hover .note-actions {
  opacity: 1;
}

.note-list-item:hover .drag-handle {
  opacity: 1;
}

.note-list-item.is-active {
  background: var(--primary-bg, rgba(64, 158, 255, 0.1));
  border-left: 3px solid var(--primary-color, #409eff);
  padding-left: 13px;
}

/* 拖拽状态 */
.note-list-item.is-dragging {
  opacity: 0.5;
  background: var(--primary-bg, rgba(64, 158, 255, 0.1));
  transform: scale(0.98);
}

/* 拖拽手柄 */
.drag-handle {
  width: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary, #ccc);
  cursor: grab;
  opacity: 0;
  transition: opacity 0.2s;
  flex-shrink: 0;
  margin-right: 4px;
}

.drag-handle:active {
  cursor: grabbing;
}

.note-list-item.is-dragging .drag-handle {
  opacity: 1;
}

.note-content {
  flex: 1;
  min-width: 0;
}

.note-title {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.note-title-edit {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #333);
  border: 1px solid var(--primary-color, #409eff);
  border-radius: 4px;
  padding: 2px 6px;
  width: 100%;
  outline: none;
  background: var(--bg-primary, #fff);
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.note-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-secondary, #999);
}

.folder-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--bg-tertiary, #f0f0f0);
  padding: 1px 6px;
  border-radius: 4px;
}

.folder-tag i {
  font-size: 10px;
  color: var(--warning-color, #e6a23c);
}

.update-time {
  color: var(--text-tertiary, #bbb);
}

.note-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.action-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #999);
  font-size: 12px;
  border-radius: 4px;
  transition: all 0.2s;
}

.action-btn:hover {
  background: var(--hover-bg, rgba(0,0,0,0.1));
}

.favorite-btn:hover,
.favorite-btn.is-favorited {
  color: var(--warning-color, #e6a23c);
}

.favorite-btn.is-favorited i {
  font-weight: 900;
}

.restore-btn:hover {
  color: var(--success-color, #67c23a);
}

.delete-btn:hover {
  color: var(--error-color, #f56c6c);
}

/* 激活状态下操作按钮始终可见 */
.note-list-item.is-active .note-actions {
  opacity: 1;
}
</style>
