import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useSidebarStore } from '@/stores/sidebar'

export function useMoveToDialog(props, emit) {
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
        await sidebarStore.copyNoteToFolder(props.note.id, selectedFolderId.value)
        ElMessage.success(`已复制到「${selectedFolderName.value}」`)
      }

      emit('confirm', {
        noteId: props.note.id,
        folderId: selectedFolderId.value,
        folderName: selectedFolderName.value
      })
      emit('close')
    } catch (e) {
      console.error('操作失败:', e)
      ElMessage.error(e.message || '操作失败，请重试')
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

  return {
    // 状态
    searchQuery,
    selectedFolderId,
    selectedFolderName,
    folders,
    inboxCount,
    isLoading,
    expandedIds,
    searchInput,
    dialogRef,
    // 计算属性
    filteredFolders,
    canConfirm,
    // 方法
    selectFolder,
    toggleExpand,
    handleClose,
    handleConfirm
  }
}
