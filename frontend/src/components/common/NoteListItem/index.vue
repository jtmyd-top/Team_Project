<template>
  <div
    class="note-list-item"
    :class="{ 'is-active': active, 'is-dragging': isDragging }"
    draggable="true"
    @click="handleClick"
    @contextmenu.prevent="handleContextMenu"
    @touchstart="handleTouchStart"
    @touchmove="handleTouchMove"
    @touchend="handleTouchEnd"
    @touchcancel="handleTouchCancel"
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
      <div v-else class="note-title-wrapper">
        <!-- 保密图标 -->
        <i v-if="note.is_secret" class="fas fa-lock vault-badge" title="保密笔记"></i>

        <!-- 标题内容 -->
        <h4
          v-if="!needsUnlock"
          class="note-title"
        >
          {{ displayTitle }}
        </h4>

        <!-- 未解锁时显示模糊占位符 -->
        <h4
          v-else
          class="note-title locked"
          @click.stop="handleUnlockVault"
          :title="isInTrash ? '在回收站中查看加密笔记需要先解锁保密柜' : '查看加密笔记需要先解锁保密柜'"
        >
          <span class="lock-icon">🔒</span>
          <span class="mask-text">加密笔记{{ isInTrash ? ' - 点击解锁' : '' }}</span>
        </h4>
      </div>

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
          v-if="!note.is_secret"
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
          :disabled="note.is_secret && !vaultStore.isUnlocked"
          :title="note.is_secret && !vaultStore.isUnlocked ? '需要先解锁保密柜' : '恢复'"
        >
          <i class="fas fa-undo"></i>
        </button>

        <!-- 永久删除按钮 -->
        <button
          class="action-btn delete-btn"
          @click="handleDelete"
          :disabled="note.is_secret && !vaultStore.isUnlocked"
          :title="note.is_secret && !vaultStore.isUnlocked ? '需要先解锁保密柜' : '永久删除'"
        >
          <i class="fas fa-trash-alt"></i>
        </button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { useVaultStore } from '@/stores/vault'
import { useNoteListItem } from '@/composables/useNoteListItem'

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

const vaultStore = useVaultStore()

const {
  isDragging,
  isEditing,
  editingTitle,
  titleInput,
  displayTitle,
  isInTrash,
  needsUnlock,
  startEditing,
  saveRename,
  cancelRename,
  handleDragStart,
  handleDragEnd,
  handleClick,
  handleContextMenu,
  handleTouchStart,
  handleTouchMove,
  handleTouchEnd,
  handleTouchCancel,
  handleFavorite,
  handleTrash,
  handleRestore,
  handleDelete,
  handleUnlockVault
} = useNoteListItem(props, emit)
</script>

<style scoped>
.note-list-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.2s, opacity 0.2s, transform 0.2s;
  border-bottom: 1px solid var(--border-light, rgba(0,0,0,0.05));
  -webkit-touch-callout: none;
  touch-action: pan-y;
  user-select: none;
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

.note-list-item.is-dragging {
  opacity: 0.5;
  background: var(--primary-bg, rgba(64, 158, 255, 0.1));
  transform: scale(0.98);
}

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

.note-title-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.vault-badge {
  color: #f56c6c;
  font-size: 11px;
  flex-shrink: 0;
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

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  pointer-events: none;
}

.action-btn:disabled:hover {
  background: transparent;
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

.delete-btn {
  color: #f56c6c;
  background: linear-gradient(135deg, #f56c6c 0%, #e74c3c 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.delete-btn:hover {
  color: #e74c3c;
  background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  transform: scale(1.2);
}

.note-list-item.is-active .note-actions {
  opacity: 1;
}
</style>
