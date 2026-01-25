<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="visible"
        class="move-dialog-overlay"
        @click.self="handleClose"
        @keydown.esc="handleClose"
      >
        <div class="move-dialog" ref="dialogRef">
          <!-- 头部 -->
          <div class="dialog-header">
            <i class="fas fa-folder-open"></i>
            <span>{{ mode === 'copy' ? '复制到' : '移动到' }}</span>
            <button class="close-btn" @click="handleClose">
              <i class="fas fa-times"></i>
            </button>
          </div>

          <!-- 当前笔记信息 -->
          <div class="note-info">
            <i class="fas fa-file-alt"></i>
            <span class="note-title">{{ note?.title || '无标题' }}</span>
          </div>

          <!-- 搜索框 -->
          <div class="search-box">
            <i class="fas fa-search"></i>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索文件夹..."
              ref="searchInput"
            />
            <button v-if="searchQuery" class="clear-btn" @click="searchQuery = ''">
              <i class="fas fa-times"></i>
            </button>
          </div>

          <!-- 文件夹列表 -->
          <div class="folder-list">
            <!-- 未分类笔记 -->
            <div
              class="folder-item inbox-item"
              :class="{
                'is-selected': selectedFolderId === null,
                'is-current': note?.folder?.id === null || !note?.folder
              }"
              @click="selectFolder(null, '未分类笔记')"
            >
              <span class="folder-indent"></span>
              <i class="fas fa-inbox folder-icon inbox-icon"></i>
              <span class="folder-name">未分类笔记</span>
              <span v-if="inboxCount > 0" class="folder-count">{{ inboxCount }}</span>
              <span v-if="!note?.folder" class="current-badge">当前</span>
            </div>

            <div class="list-divider"></div>

            <!-- 文件夹树 -->
            <template v-if="filteredFolders.length > 0">
              <MoveFolderItem
                v-for="folder in filteredFolders"
                :key="folder.id"
                :folder="folder"
                :selected-id="selectedFolderId"
                :current-folder-id="note?.folder?.id"
                :depth="0"
                :expanded-ids="expandedIds"
                @select="selectFolder"
                @toggle="toggleExpand"
              />
            </template>

            <!-- 空状态 -->
            <div v-else-if="!isLoading" class="empty-state">
              <p v-if="searchQuery">未找到匹配的文件夹</p>
              <p v-else>暂无文件夹</p>
            </div>

            <!-- 加载状态 -->
            <div v-if="isLoading" class="loading-state">
              <i class="fas fa-spinner fa-spin"></i>
              <span>加载中...</span>
            </div>
          </div>

          <!-- 底部操作 -->
          <div class="dialog-footer">
            <button class="btn-cancel" @click="handleClose">取消</button>
            <button
              class="btn-confirm"
              :disabled="!canConfirm"
              @click="handleConfirm"
            >
              {{ mode === 'copy' ? '复制' : '移动' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useSidebarStore } from '@/stores/sidebar'
import MoveFolderItem from './MoveFolderItem.vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  note: {
    type: Object,
    default: null
  },
  mode: {
    type: String,
    default: 'move', // 'move' or 'copy'
    validator: (v) => ['move', 'copy'].includes(v)
  }
})

const emit = defineEmits(['close', 'confirm'])

const sidebarStore = useSidebarStore()

// 状态
const searchQuery = ref('')
const selectedFolderId = ref(undefined) // undefined = 未选择, null = 未分类
const selectedFolderName = ref('')
const folders = ref([])
const inboxCount = ref(0)
const isLoading = ref(false)
const expandedIds = ref(new Set())
const searchInput = ref(null)
const dialogRef = ref(null)

// 计算属性
const filteredFolders = computed(() => {
  if (!searchQuery.value) {
    return folders.value
  }

  const query = searchQuery.value.toLowerCase()

  // 递归过滤文件夹
  function filterFolders(items) {
    return items.reduce((acc, folder) => {
      const nameMatches = folder.name.toLowerCase().includes(query)
      const filteredChildren = folder.children ? filterFolders(folder.children) : []

      if (nameMatches || filteredChildren.length > 0) {
        acc.push({
          ...folder,
          children: filteredChildren
        })
      }

      return acc
    }, [])
  }

  return filterFolders(folders.value)
})

const canConfirm = computed(() => {
  // 必须选择了一个文件夹
  if (selectedFolderId.value === undefined) return false

  // 不能移动到当前位置
  const currentFolderId = props.note?.folder?.id || null
  if (selectedFolderId.value === currentFolderId && props.mode === 'move') {
    return false
  }

  return true
})

// 方法
async function loadFolders() {
  isLoading.value = true
  try {
    const response = await fetch('/api/folders/')
    const data = await response.json()
    folders.value = data.folders || []
    inboxCount.value = data.inbox_count || 0

    // 默认展开所有文件夹
    expandAllFolders(folders.value)
  } catch (e) {
    console.error('加载文件夹失败:', e)
    ElMessage.error('加载文件夹列表失败')
  } finally {
    isLoading.value = false
  }
}

function expandAllFolders(items) {
  items.forEach(folder => {
    if (folder.children && folder.children.length > 0) {
      expandedIds.value.add(folder.id)
      expandAllFolders(folder.children)
    }
  })
}

function selectFolder(folderId, folderName) {
  // 不能选择当前文件夹（移动模式）
  const currentFolderId = props.note?.folder?.id || null
  if (folderId === currentFolderId && props.mode === 'move') {
    return
  }

  selectedFolderId.value = folderId
  selectedFolderName.value = folderName
}

function toggleExpand(folderId) {
  if (expandedIds.value.has(folderId)) {
    expandedIds.value.delete(folderId)
  } else {
    expandedIds.value.add(folderId)
  }
  // 触发响应式更新
  expandedIds.value = new Set(expandedIds.value)
}

function handleClose() {
  emit('close')
}

async function handleConfirm() {
  if (!canConfirm.value) return

  try {
    if (props.mode === 'move') {
      await sidebarStore.moveNoteToFolder(props.note.id, selectedFolderId.value)
      ElMessage.success(`已移动到「${selectedFolderName.value}」`)
    } else {
      // 复制功能 TODO: 实现复制 API
      ElMessage.info('复制功能开发中...')
    }

    emit('confirm', {
      noteId: props.note.id,
      folderId: selectedFolderId.value,
      folderName: selectedFolderName.value
    })
    emit('close')
  } catch (e) {
    console.error('操作失败:', e)
    ElMessage.error('操作失败，请重试')
  }
}

// 键盘事件
function handleKeydown(event) {
  if (!props.visible) return

  if (event.key === 'Escape') {
    handleClose()
  }
}

// 监听打开状态
watch(() => props.visible, async (newVal) => {
  if (newVal) {
    // 重置状态
    selectedFolderId.value = undefined
    selectedFolderName.value = ''
    searchQuery.value = ''

    // 加载文件夹
    await loadFolders()

    // 聚焦搜索框
    await nextTick()
    searchInput.value?.focus()
  }
})

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.move-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.move-dialog {
  width: 400px;
  max-width: 90vw;
  max-height: 80vh;
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dialog-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  background: var(--bg-secondary, #f5f5f5);
}

.dialog-header i:first-child {
  color: var(--primary-color, #409eff);
  font-size: 16px;
}

.dialog-header span {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.close-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #666);
  transition: all 0.2s;
}

.close-btn:hover {
  background: var(--hover-bg, rgba(0, 0, 0, 0.1));
  color: var(--text-primary, #333);
}

.note-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  background: var(--bg-tertiary, #f8f8f8);
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.note-info i {
  color: var(--text-secondary, #999);
  font-size: 14px;
}

.note-title {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.search-box i:first-child {
  color: var(--text-secondary, #999);
  font-size: 13px;
}

.search-box input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 13px;
  color: var(--text-primary, #333);
}

.search-box input::placeholder {
  color: var(--text-tertiary, #bbb);
}

.search-box .clear-btn {
  width: 20px;
  height: 20px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #999);
  border-radius: 4px;
}

.search-box .clear-btn:hover {
  background: var(--hover-bg, rgba(0, 0, 0, 0.1));
}

.folder-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
  min-height: 200px;
  max-height: 400px;
}

.folder-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
  transition: all 0.15s;
  gap: 8px;
}

.folder-item:hover {
  background: var(--hover-bg, rgba(0, 0, 0, 0.03));
}

.folder-item.is-selected {
  background: var(--primary-bg, rgba(64, 158, 255, 0.1));
}

.folder-item.is-selected .folder-name {
  color: var(--primary-color, #409eff);
  font-weight: 600;
}

.folder-item.is-current {
  opacity: 0.5;
  cursor: not-allowed;
}

.folder-indent {
  width: 0;
}

.folder-icon {
  color: var(--warning-color, #e6a23c);
  font-size: 14px;
  flex-shrink: 0;
}

.inbox-icon {
  color: var(--primary-color, #409eff);
}

.folder-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.folder-count {
  font-size: 11px;
  color: var(--text-secondary, #999);
  background: var(--bg-tertiary, #eee);
  padding: 2px 6px;
  border-radius: 8px;
  flex-shrink: 0;
}

.current-badge {
  font-size: 10px;
  color: var(--text-tertiary, #bbb);
  background: var(--bg-tertiary, #f0f0f0);
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.list-divider {
  height: 1px;
  background: var(--border-color, #e0e0e0);
  margin: 6px 16px;
}

.empty-state,
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  color: var(--text-secondary, #999);
  font-size: 13px;
  gap: 8px;
}

.loading-state i {
  font-size: 20px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color, #e0e0e0);
  background: var(--bg-secondary, #f8f8f8);
}

.btn-cancel,
.btn-confirm {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-cancel {
  border: 1px solid var(--border-color, #ddd);
  background: transparent;
  color: var(--text-secondary, #666);
}

.btn-cancel:hover {
  background: var(--hover-bg, rgba(0, 0, 0, 0.05));
}

.btn-confirm {
  border: none;
  background: var(--primary-color, #409eff);
  color: white;
}

.btn-confirm:hover {
  background: var(--primary-color-dark, #337ecc);
}

.btn-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 过渡动画 */
.modal-fade-enter-active {
  transition: opacity 0.2s ease;
}

.modal-fade-leave-active {
  transition: opacity 0.15s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-from .move-dialog {
  transform: scale(0.95) translateY(-10px);
}
</style>
