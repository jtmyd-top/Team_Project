import { ref, onMounted, onUnmounted } from 'vue'
import { useSidebarStore } from '@/stores/sidebar'
import { useVaultEncryption } from '@/composables/useVaultEncryption'
import { useClientCrypto } from '@/composables/useClientCrypto'
import { useVaultStore } from '@/stores/vault'
import { getCsrfToken } from '@utils/csrf'
import { extractApiErrorMessage } from '@utils/apiError'
import { ElMessage } from 'element-plus'

export function useDragDropOverlay() {
  const sidebarStore = useSidebarStore()
  const vaultStore = useVaultStore()

  // 加密相关
  const { isKeyValid, tryRecoverKeyFromSession } = useVaultEncryption()
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
        const noteData = await noteResponse.json().catch(() => ({}))
        if (!noteResponse.ok) {
          throw new Error(extractApiErrorMessage(noteData, '获取笔记内容失败'))
        }

        // 解密标题和内容
        let decryptedTitle = noteData.title
        let decryptedContent = noteData.content

        try {
          if (noteData.title && looksLikeEncrypted(noteData.title)) {
            decryptedTitle = await decryptContent(noteData.title)
            console.log('[Vault] Title decrypted for move')
          }
        } catch (e) {
          console.warn('[Vault] Failed to decrypt title, using original:', e.message)
        }

        try {
          if (noteData.content && looksLikeEncrypted(noteData.content)) {
            decryptedContent = await decryptContent(noteData.content)
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

        const updateData = await updateResponse.json().catch(() => ({}))
        if (!updateResponse.ok) {
          throw new Error(extractApiErrorMessage(updateData, '更新笔记失败'))
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
      ElMessage.error(e.message || '移动失败，请重试')
    }
  }

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

  return {
    // 状态
    isVisible,
    dropTargetId,
    currentFolderId,
    folders,
    inboxCount,
    // 方法
    handleDragOver,
    handleDragLeave,
    handleDrop
  }
}
