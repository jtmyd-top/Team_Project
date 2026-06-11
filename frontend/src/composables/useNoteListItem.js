/**
 * NoteListItem 逻辑层
 * 处理笔记列表项的交互、解密、拖拽等功能
 */

import { ref, watch, nextTick, computed } from 'vue'
import { useClientCrypto } from '@composables/useClientCrypto'
import { useVaultStore } from '@/stores/vault'

export function useNoteListItem(props, emit) {
  const LONG_PRESS_DELAY_MS = 520
  const LONG_PRESS_MOVE_THRESHOLD_PX = 12

  // ==================== 状态 ====================
  const isDragging = ref(false)
  const isEditing = ref(false)
  const editingTitle = ref('')
  const titleInput = ref(null)
  const decryptedTitle = ref('')
  let longPressTimer = null
  let touchStartPoint = null
  let suppressNextClick = false

  // ==================== Composables ====================
  const { decryptContent } = useClientCrypto()
  const vaultStore = useVaultStore()

  // ==================== 计算属性 ====================
  const displayTitle = computed(() => {
    if (!props.note.is_secret) {
      return props.note.title || '无标题'
    }

    if (props.note.decryptedTitle) {
      return props.note.decryptedTitle
    }

    if (decryptedTitle.value) {
      return decryptedTitle.value
    }

    return props.note.title || '无标题'
  })

  const isInTrash = computed(() => props.showTrashActions)

  const needsUnlock = computed(() => {
    return props.note.is_secret && !vaultStore.isUnlocked && isInTrash.value
  })

  // ==================== 解密逻辑 ====================
  // latestDecryptId 用于竞态保护：快速切换笔记时丢弃旧的 await 结果
  let latestDecryptId = 0
  async function decryptNoteTitle() {
    if (!props.note.is_secret) {
      decryptedTitle.value = ''
      return
    }

    if (!props.note.title) {
      decryptedTitle.value = ''
      return
    }

    if (!vaultStore.isUnlocked) {
      const recovered = await vaultStore.recoverKey()
      if (!recovered || !vaultStore.isUnlocked) {
        decryptedTitle.value = ''
        return
      }
    }

    const requestId = ++latestDecryptId
    const capturedNoteId = props.note.id
    try {
      const plainTitle = await decryptContent(props.note.title)
      // 如果期间切换了笔记或发起了新请求，忽略本次结果
      if (requestId !== latestDecryptId || capturedNoteId !== props.note.id) return
      decryptedTitle.value = plainTitle
    } catch (e) {
      if (requestId !== latestDecryptId || capturedNoteId !== props.note.id) return
      decryptedTitle.value = ''
    }
  }

  // ==================== 监听器 ====================
  watch(() => props.editingNoteId, (newVal) => {
    if (newVal === props.note.id) {
      startEditing()
    } else if (isEditing.value) {
      cancelRename()
    }
  })

  watch(() => props.active, (isActive) => {
    if (isActive && props.note.is_secret && !decryptedTitle.value) {
      decryptNoteTitle()
    }
  })

  watch(() => props.note.id, () => {
    decryptedTitle.value = ''
    if (props.note.is_secret && vaultStore.isUnlocked) {
      decryptNoteTitle()
    }
  })

  watch(() => vaultStore.isUnlocked, (valid) => {
    if (valid && props.note.is_secret && props.note.title) {
      decryptNoteTitle()
    } else if (!valid && props.note.is_secret) {
      decryptedTitle.value = ''
    }
  })

  watch(() => props.note, (note) => {
    if (note.is_secret && note.title && vaultStore.isUnlocked) {
      decryptNoteTitle()
    }
  }, { immediate: true })

  watch(() => props.note.title, () => {
    if (props.note.is_secret) {
      decryptNoteTitle()
    }
  })

  watch(() => props.showTrashActions, () => {
    if (props.note.is_secret) {
      decryptNoteTitle()
    }
  })

  watch(() => props.note.decryptedTitle, (newDecryptedTitle) => {
    // parent set decryptedTitle
  })

  // ==================== 编辑逻辑 ====================
  function startEditing() {
    isEditing.value = true
    editingTitle.value = decryptedTitle.value || props.note.title || ''
    nextTick(() => {
      titleInput.value?.focus()
      titleInput.value?.select()
    })
  }

  function saveRename() {
    if (!isEditing.value) return

    const newTitle = editingTitle.value.trim()
    if (newTitle && newTitle !== props.note.title) {
      emit('rename', props.note, newTitle)
    }

    isEditing.value = false
    editingTitle.value = ''
  }

  function cancelRename() {
    isEditing.value = false
    editingTitle.value = ''
  }

  // ==================== 拖拽逻辑 ====================
  function handleDragStart(event) {
    isDragging.value = true

    const noteData = {
      type: 'NOTE_ITEM',
      id: props.note.id,
      title: props.note.title,
      currentFolderId: props.note.folder?.id || null,
      isSecret: props.note.is_secret || false
    }

    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('application/json', JSON.stringify(noteData))

    window.dispatchEvent(new CustomEvent('note-drag-start', {
      detail: {
        noteId: props.note.id,
        noteTitle: props.note.title,
        currentFolderId: props.note.folder?.id || null,
        isSecret: props.note.is_secret || false
      }
    }))
  }

  function handleDragEnd(event) {
    isDragging.value = false
    window.dispatchEvent(new CustomEvent('note-drag-end'))
  }

  // ==================== 事件处理 ====================
  function handleClick(event) {
    if (suppressNextClick) {
      suppressNextClick = false
      return
    }

    // 【关键修复】如果是回收站中的加密笔记且未解锁，先触发解锁流程
    if (props.note.is_secret && isInTrash.value && !vaultStore.isUnlocked) {
      console.log('[NoteListItem] Encrypted note in trash clicked without DEK, triggering unlock')
      handleUnlockVault()
      return
    }
    emit('click', props.note)
    if (isMobileDevice()) {
      openContextMenuFromEvent(event)
    }
  }

  function handleContextMenu(event) {
    openContextMenuFromEvent(event)
  }

  function openContextMenuFromEvent(event) {
    const x = Number.isFinite(event?.clientX) && event.clientX > 0
      ? event.clientX
      : Math.round(window.innerWidth / 2)
    const y = Number.isFinite(event?.clientY) && event.clientY > 0
      ? event.clientY
      : Math.round(window.innerHeight / 2)
    openContextMenuAt(x, y)
  }

  function openContextMenuAt(x, y) {
    emit('contextmenu', {
      note: props.note,
      x,
      y
    })
  }

  function clearLongPressTimer() {
    if (longPressTimer) {
      clearTimeout(longPressTimer)
      longPressTimer = null
    }
  }

  function isInteractiveTouchTarget(target) {
    return !!target?.closest?.('button, input, textarea, select, a, .note-actions, .drag-handle')
  }

  function isMobileDevice() {
    const coarsePointer = window.matchMedia?.('(pointer: coarse)').matches
    const narrowViewport = window.matchMedia?.('(max-width: 768px)').matches
    const touchDevice = navigator.maxTouchPoints > 0
    const mobileUA = /Android|iPhone|iPad|iPod|Mobile|Windows Phone/i.test(navigator.userAgent || '')
    return !!((touchDevice && coarsePointer) || (touchDevice && narrowViewport) || mobileUA)
  }

  function handleTouchStart(event) {
    if (isEditing.value || event.touches.length !== 1 || isInteractiveTouchTarget(event.target)) return

    const touch = event.touches[0]
    touchStartPoint = { x: touch.clientX, y: touch.clientY }
    clearLongPressTimer()
    longPressTimer = window.setTimeout(() => {
      if (!touchStartPoint) return
      suppressNextClick = true
      openContextMenuAt(touchStartPoint.x, touchStartPoint.y)
      if (navigator.vibrate) navigator.vibrate(10)
      clearLongPressTimer()
    }, LONG_PRESS_DELAY_MS)
  }

  function handleTouchMove(event) {
    if (!touchStartPoint || event.touches.length !== 1) {
      clearLongPressTimer()
      return
    }

    const touch = event.touches[0]
    const dx = touch.clientX - touchStartPoint.x
    const dy = touch.clientY - touchStartPoint.y
    if (Math.hypot(dx, dy) > LONG_PRESS_MOVE_THRESHOLD_PX) {
      touchStartPoint = null
      clearLongPressTimer()
    }
  }

  function handleTouchEnd() {
    touchStartPoint = null
    clearLongPressTimer()
  }

  function handleTouchCancel() {
    touchStartPoint = null
    clearLongPressTimer()
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

  function handleUnlockVault() {
    window.dispatchEvent(new CustomEvent('request-vault-unlock', {
      detail: { fromTrash: true, noteId: props.note.id }
    }))
  }

  // ==================== 返回 ====================
  return {
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
  }
}
