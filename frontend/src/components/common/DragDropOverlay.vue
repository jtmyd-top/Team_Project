<template>
  <Teleport to="body">
    <Transition name="slide-fade">
      <div v-if="isVisible" class="drag-drop-overlay">
        <div class="overlay-panel">
          <div class="panel-header">
            <i class="fas fa-folder-tree"></i>
            <span>移动到...</span>
          </div>

          <div class="panel-content">
            <!-- 未分类笔记 -->
            <div
              class="drop-item inbox-item"
              :class="{ 'is-drop-target': dropTargetId === 'inbox' }"
              @dragover.prevent="handleDragOver('inbox', $event)"
              @dragleave="handleDragLeave"
              @drop="handleDrop(null, '未分类笔记', $event)"
            >
              <i class="fas fa-inbox"></i>
              <span>未分类笔记</span>
              <span v-if="inboxCount > 0" class="item-count">{{ inboxCount }}</span>
            </div>

            <div class="divider"></div>

            <!-- 文件夹树 -->
            <div v-if="folders.length > 0" class="folder-list">
              <DropFolderItem
                v-for="folder in folders"
                :key="folder.id"
                :folder="folder"
                :drop-target-id="dropTargetId"
                :current-folder-id="currentFolderId"
                @dragover="handleDragOver"
                @dragleave="handleDragLeave"
                @drop="handleDrop"
              />
            </div>

            <!-- 空状态 -->
            <div v-else class="empty-state">
              <p>暂无文件夹</p>
            </div>
          </div>

          <div class="panel-footer">
            <i class="fas fa-info-circle"></i>
            <span>拖动笔记到文件夹上松开即可移动</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useSidebarStore } from '@/stores/sidebar'
import { useVaultEncryption } from '@/composables/useVaultEncryption'
import { useClientCrypto } from '@/composables/useClientCrypto'
import { ElMessage } from 'element-plus'
import DropFolderItem from './DropFolderItem.vue'

const sidebarStore = useSidebarStore()

// 加密相关
const { isKeyValid, dek, tryRecoverKeyFromSession, getCsrfToken } = useVaultEncryption()
const { decryptContent, looksLikeEncrypted } = useClientCrypto()

// 状态
const isVisible = ref(false)
const dropTargetId = ref(null)
const draggedNoteData = ref(null)
const currentFolderId = ref(null)
const folders = ref([])
const inboxCount = ref(0)

// 加载文件夹数据
async function loadFolders() {
  try {
    const response = await fetch('/api/folders/')
    const data = await response.json()
    folders.value = data.folders || []
    inboxCount.value = data.inbox_count || 0
  } catch (e) {
    console.error('加载文件夹列表失败:', e)
  }
}

// 全局拖拽事件处理
function handleGlobalDragStart(event) {
  // 检查是否是笔记拖拽
  const data = event.dataTransfer.getData('application/json')
  if (!data) {
    // 在 dragstart 时 getData 可能返回空，使用自定义事件
    return
  }
}

// 自定义事件：笔记开始拖拽
function handleNoteDragStart(event) {
  const { noteId, noteTitle, currentFolderId: noteFolderId, isSecret } = event.detail
  draggedNoteData.value = { noteId, noteTitle, isSecret }
  currentFolderId.value = noteFolderId
  isVisible.value = true
  loadFolders()
}

// 自定义事件：笔记拖拽结束
function handleNoteDragEnd() {
  isVisible.value = false
  dropTargetId.value = null
  draggedNoteData.value = null
}

// 拖拽悬停
function handleDragOver(folderId, event) {
  event?.preventDefault?.()
  dropTargetId.value = folderId
}

// 拖拽离开
function handleDragLeave() {
  dropTargetId.value = null
}

// 放置
async function handleDrop(folderId, folderName, event) {
  event?.preventDefault?.()
  dropTargetId.value = null

  if (!draggedNoteData.value) return

  // 如果已经在这个文件夹中，不执行移动
  if (folderId === currentFolderId.value) {
    ElMessage.info('笔记已在此文件夹中')
    return
  }

  try {
    const noteId = draggedNoteData.value.noteId
    const isSecret = draggedNoteData.value.isSecret

    // 如果是保密柜笔记，需要先解密再移动
    if (isSecret) {
      console.log('[Vault] Moving secret note out of vault, need to decrypt first')

      // 检查 DEK 是否有效
      if (!isKeyValid.value) {
        // 尝试从 session 恢复
        const recovered = await tryRecoverKeyFromSession()
        if (!recovered || !isKeyValid.value) {
          ElMessage.error('保密柜已锁定，请先解锁保密柜后再移动笔记')
          return
        }
      }

      // 获取笔记完整内容
      const noteResponse = await fetch(`/api/notes/${noteId}/?full_content=true`)
      if (!noteResponse.ok) {
        throw new Error('获取笔记内容失败')
      }
      const noteData = await noteResponse.json()

      // 解密标题和内容
      let decryptedTitle = noteData.title
      let decryptedContent = noteData.content

      try {
        if (noteData.title && looksLikeEncrypted(noteData.title)) {
          decryptedTitle = decryptContent(noteData.title, dek.value)
          console.log('[Vault] Title decrypted for move')
        }
      } catch (e) {
        console.warn('[Vault] Failed to decrypt title, using original:', e.message)
      }

      try {
        if (noteData.content && looksLikeEncrypted(noteData.content)) {
          decryptedContent = decryptContent(noteData.content, dek.value)
          console.log('[Vault] Content decrypted for move')
        }
      } catch (e) {
        console.warn('[Vault] Failed to decrypt content, using original:', e.message)
      }

      // 更新笔记：解密后的内容 + is_secret = false + 新的 folder_id
      const csrfToken = getCsrfToken()
      const updateResponse = await fetch(`/api/notes/${noteId}/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          title: decryptedTitle,
          content: decryptedContent,
          is_secret: false,
          folder_id: folderId
        })
      })

      if (!updateResponse.ok) {
        throw new Error('更新笔记失败')
      }

      console.log('[Vault] Note decrypted and moved out of vault successfully')

      // 【P0】触发事件：笔记从保密柜移出
      window.dispatchEvent(new CustomEvent('note-moved-from-vault', {
        detail: { noteId }
      }))

      // 【P1】触发事件：笔记文件夹已变更
      window.dispatchEvent(new CustomEvent('note-folder-changed', {
        detail: { noteId, oldFolderId: currentFolderId.value, newFolderId: folderId }
      }))

      ElMessage.success(`已从保密柜移出到「${folderName}」`)

      // 刷新当前视图
      await sidebarStore.loadModuleData()
    } else {
      // 普通笔记，直接移动
      await sidebarStore.moveNoteToFolder(noteId, folderId)

      // 【P1】触发事件：笔记文件夹已变更
      window.dispatchEvent(new CustomEvent('note-folder-changed', {
        detail: { noteId, oldFolderId: currentFolderId.value, newFolderId: folderId }
      }))

      ElMessage.success(`已移动到「${folderName}」`)
    }
  } catch (e) {
    console.error('移动笔记失败:', e)
    ElMessage.error('移动失败，请重试')
  }
}

// 生命周期
onMounted(() => {
  // 监听自定义事件
  window.addEventListener('note-drag-start', handleNoteDragStart)
  window.addEventListener('note-drag-end', handleNoteDragEnd)
  // 监听 ESC 键取消拖拽
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('note-drag-start', handleNoteDragStart)
  window.removeEventListener('note-drag-end', handleNoteDragEnd)
  window.removeEventListener('keydown', handleKeydown)
})

// ESC 键取消拖拽
function handleKeydown(event) {
  if (event.key === 'Escape' && isVisible.value) {
    // 关闭面板
    isVisible.value = false
    dropTargetId.value = null
    draggedNoteData.value = null
    // 派发取消事件
    window.dispatchEvent(new CustomEvent('note-drag-cancel'))
  }
}
</script>

<style scoped>
.drag-drop-overlay {
  position: fixed;
  top: calc(64px + 50px); /* 顶部导航栏 + 工具栏高度 */
  left: 304px; /* 一级侧边栏(64px) + 二级侧边栏(240px) */
  z-index: 1000;
  pointer-events: auto;
}

.overlay-panel {
  width: 280px;
  max-height: calc(100vh - 120px);
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1);
  border: 1px solid var(--border-color, #e0e0e0);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  background: var(--bg-secondary, #f5f5f5);
}

.panel-header i {
  color: var(--primary-color, #409eff);
  font-size: 16px;
}

.panel-header span {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.drop-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: copy;
  transition: all 0.2s;
  border: 2px solid transparent;
}

.drop-item:hover {
  background: var(--hover-bg, rgba(0,0,0,0.03));
}

.drop-item.is-drop-target {
  background: var(--primary-bg, rgba(64, 158, 255, 0.15));
  border-color: var(--primary-color, #409eff);
  cursor: move;
  transform: scale(1.02);
}

.drop-item.is-drop-target i {
  color: var(--primary-color, #409eff);
}

.drop-item.is-drop-target span {
  color: var(--primary-color, #409eff);
  font-weight: 600;
}

.inbox-item i {
  color: var(--primary-color, #409eff);
  font-size: 14px;
}

.inbox-item span {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary, #333);
}

.item-count {
  background: var(--bg-tertiary, #eee);
  color: var(--text-secondary, #666);
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
}

.divider {
  height: 1px;
  background: var(--border-color, #e0e0e0);
  margin: 8px 4px;
}

.folder-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.empty-state {
  padding: 20px;
  text-align: center;
  color: var(--text-secondary, #999);
  font-size: 13px;
}

.panel-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border-color, #e0e0e0);
  background: var(--bg-secondary, #f8f8f8);
  font-size: 12px;
  color: var(--text-secondary, #999);
}

.panel-footer i {
  font-size: 12px;
}

/* 过渡动画 */
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}

.slide-fade-leave-active {
  transition: all 0.2s ease-in;
}

.slide-fade-enter-from {
  transform: translateY(-10px);
  opacity: 0;
}

.slide-fade-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}
</style>
