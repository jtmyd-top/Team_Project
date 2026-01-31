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

        <!-- 【新增】未解锁时显示模糊占位符 -->
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
          :disabled="note.is_secret && !isKeyValid && !vaultStore.dek"
          :title="note.is_secret && !isKeyValid && !vaultStore.dek ? '需要先解锁保密柜' : '恢复'"
        >
          <i class="fas fa-undo"></i>
        </button>

        <!-- 永久删除按钮 -->
        <button
          class="action-btn delete-btn"
          @click="handleDelete"
          :disabled="note.is_secret && !isKeyValid && !vaultStore.dek"
          :title="note.is_secret && !isKeyValid && !vaultStore.dek ? '需要先解锁保密柜' : '永久删除'"
        >
          <i class="fas fa-trash-alt"></i>
        </button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import { useVaultEncryption } from '@/composables/useVaultEncryption'
import { useClientCrypto } from '@/composables/useClientCrypto'
import { useVaultStore } from '@/stores/vault'

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

// 解密状态
const { isKeyValid, dek } = useVaultEncryption()
const { decryptContent } = useClientCrypto()
const vaultStore = useVaultStore()
const decryptedTitle = ref('')

// 计算属性：显示的标题（已解密或原标题）
const displayTitle = computed(() => {
  // 如果不是加密笔记，直接返回原标题
  if (!props.note.is_secret) {
    return props.note.title || '无标题'
  }

  // 【新增】如果 parent 已经设置了解密后的标题，直接使用
  if (props.note.decryptedTitle) {
    return props.note.decryptedTitle
  }

  // 如果本地解密过，返回解密后的标题
  if (decryptedTitle.value) {
    return decryptedTitle.value
  }

  // 如果还没解密，返回原标题（可能是密文）
  return props.note.title || '无标题'
})

// 计算属性：是否在回收站
const isInTrash = computed(() => props.showTrashActions)

// 【新增】计算属性：是否需要解锁
// 条件：是保密笔记 + 未解锁 + 在回收站
const needsUnlock = computed(() => {
  return props.note.is_secret && !isKeyValid.value && !vaultStore.dek && isInTrash.value
})

// 【新增】处理解锁保密柜的请求
function handleUnlockVault() {
  console.log('[NoteListItem] User clicked to unlock vault for note:', props.note.id)
  // 触发全局解锁事件
  window.dispatchEvent(new CustomEvent('request-vault-unlock', {
    detail: { fromTrash: true, noteId: props.note.id }
  }))
}

// 解密笔记标题
function decryptNoteTitle() {
  // 如果不是加密笔记，不需要解密
  if (!props.note.is_secret) {
    decryptedTitle.value = ''
    return
  }

  // 如果没有标题，不需要解密
  if (!props.note.title) {
    decryptedTitle.value = ''
    return
  }

  // 【修复】尝试获取有效的 DEK
  // 首先尝试 useVaultEncryption 中的 DEK
  let dekToUse = dek.value

  // 如果 isKeyValid 为 false，尝试从 vaultStore 获取 DEK（可能在回收站中 isKeyValid 被重置）
  if (!isKeyValid.value && vaultStore.dek) {
    dekToUse = vaultStore.dek
  }

  // 如果仍然没有 DEK，无法解密
  if (!dekToUse) {
    decryptedTitle.value = ''
    console.warn('[Vault] No DEK available for decryption in trash:', props.note.id)
    return
  }

  try {
    // 尝试解密标题 【修复】使用 dekToUse 而不是 dek.value
    const plainTitle = decryptContent(props.note.title, dekToUse)
    decryptedTitle.value = plainTitle
    console.log('[Vault] Title decrypted successfully in NoteListItem:', props.note.id)
  } catch (e) {
    // 标题可能是明文（旧笔记），保留原值
    console.warn('[Vault] Failed to decrypt title in NoteListItem:', e.message)
    decryptedTitle.value = ''  // 让 displayTitle computed 显示原标题
  }
}

// 监听 editingNoteId 的变化
watch(() => props.editingNoteId, (newVal) => {
  if (newVal === props.note.id) {
    startEditing()
  } else if (isEditing.value) {
    cancelRename()
  }
})

// 【新增】监听 active 变化，当笔记被选中时尝试解密
watch(() => props.active, (isActive) => {
  if (isActive && props.note.is_secret && !decryptedTitle.value) {
    // 笔记被选中且是保密笔记且还未解密，立即尝试解密
    console.log('[NoteListItem] Attempting to decrypt title for active note:', props.note.id)
    decryptNoteTitle()
  }
})

// 监听 note 对象变化（切换笔记时重新解密）
watch(() => props.note.id, () => {
  decryptedTitle.value = ''
  // 【修复】尝试解密，即使 isKeyValid 为 false（可能在回收站中）
  if (props.note.is_secret && (isKeyValid.value || vaultStore.dek)) {
    decryptNoteTitle()
  }
})

// 监听 DEK 变化（保险柜解锁时自动解密标题）
watch(() => isKeyValid.value, (valid) => {
  if (valid && props.note.is_secret && props.note.title) {
    decryptNoteTitle()
  } else if (!valid && props.note.is_secret && !vaultStore.dek) {
    // 【修复】只有当 vaultStore.dek 也不可用时，才清除解密的标题
    decryptedTitle.value = ''
  } else if (!valid && props.note.is_secret && vaultStore.dek) {
    // 如果 isKeyValid 为 false，但 vaultStore.dek 仍有效，尝试使用 vaultStore.dek 解密
    decryptNoteTitle()
  }
})

// 组件挂载时，如果已解锁，立即解密标题
watch(() => props.note, (note) => {
  // 【修复】尝试解密，即使 isKeyValid 为 false（可能在回收站中）
  if (note.is_secret && note.title && (isKeyValid.value || vaultStore.dek)) {
    decryptNoteTitle()
  }
}, { immediate: true })

// 【新增】监听笔记标题更新事件，实时同步列表中的显示标题
watch(() => {
  // 监听全局标题更新事件
  // 这里只是为了触发重新计算，实际更新通过 props.note 传入
  return props.note.title
}, (newTitle) => {
  // 如果笔记被重命名或编辑器中的标题改变，重新解密显示
  if (props.note.is_secret) {
    decryptNoteTitle()
  }
})

// 【新增】监听 showTrashActions 变化，在回收站也解密标题
watch(() => props.showTrashActions, (isInTrash) => {
  // 【修复】不依赖 isKeyValid，因为在回收站中 isKeyValid 可能为 false
  // 只要 note 是 secret，就尝试解密（即使 isKeyValid 为 false）
  if (props.note.is_secret) {
    decryptNoteTitle()
  }
})

// 【新增】监听 props.note.decryptedTitle 变化，当 parent 更新时同步本地状态
watch(() => props.note.decryptedTitle, (newDecryptedTitle) => {
  console.log('[NoteListItem] parent decryptedTitle updated:', props.note.id, 'value:', newDecryptedTitle?.substring?.(0, 20))
  // 当 parent 设置了 decryptedTitle，触发计算属性重新计算
  // Vue 会自动处理这个，无需额外操作
})

// 开始编辑
function startEditing() {
  isEditing.value = true
  // 使用解密后的标题，如果没有解密则使用原标题
  editingTitle.value = decryptedTitle.value || props.note.title || ''
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
    currentFolderId: props.note.folder?.id || null,
    isSecret: props.note.is_secret || false
  }

  // 设置拖拽数据
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('application/json', JSON.stringify(noteData))

  // 派发全局事件，通知浮动面板显示
  window.dispatchEvent(new CustomEvent('note-drag-start', {
    detail: {
      noteId: props.note.id,
      noteTitle: props.note.title,
      currentFolderId: props.note.folder?.id || null,
      isSecret: props.note.is_secret || false
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

/* 【新增】加密笔记未解锁时的模糊显示 */
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

/* 【新增】禁用按钮样式 */
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

/* 激活状态下操作按钮始终可见 */
.note-list-item.is-active .note-actions {
  opacity: 1;
}
</style>
