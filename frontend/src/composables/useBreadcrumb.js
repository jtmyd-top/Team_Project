import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useSidebarStore } from '@/stores/sidebar'

export function useBreadcrumb(props, emit) {
  const sidebarStore = useSidebarStore()

  // 状态
  const dropdownVisible = ref(false)
  const dropdownStyle = ref({})
  const currentItemId = ref(null)
  const siblingFolders = ref([])

  // 方法
  function handleRootClick() {
    sidebarStore.backToFolders()
    emit('navigate', null)
  }

  function handleItemClick(item, index) {
    // 如果是最后一项，不做任何处理
    if (index === props.items.length - 1) return

    // 导航到该文件夹
    sidebarStore.enterFolder(item.id)
    emit('navigate', item.id)
  }

  function toggleDropdown(item, event) {
    if (dropdownVisible.value && currentItemId.value === item.id) {
      closeDropdown()
      return
    }

    currentItemId.value = item.id

    // 获取同级文件夹
    fetchSiblingFolders(item)

    // 计算下拉菜单位置
    const rect = event.target.getBoundingClientRect()
    dropdownStyle.value = {
      top: `${rect.bottom + 5}px`,
      left: `${rect.left}px`
    }

    dropdownVisible.value = true
  }

  function closeDropdown() {
    dropdownVisible.value = false
    currentItemId.value = null
    siblingFolders.value = []
  }

  function fetchSiblingFolders(item) {
    // 从文件夹树中获取同级文件夹
    const findParentAndSiblings = (folders, targetId, parent = null) => {
      for (const folder of folders) {
        if (folder.id === targetId) {
          // 找到目标，返回父级的所有子项（即同级）
          return parent ? parent.children : folders
        }
        if (folder.children && folder.children.length > 0) {
          const result = findParentAndSiblings(folder.children, targetId, folder)
          if (result) return result
        }
      }
      return null
    }

    const siblings = findParentAndSiblings(sidebarStore.folders, item.id)
    siblingFolders.value = siblings || []
  }

  function handleSiblingSelect(folder) {
    sidebarStore.enterFolder(folder.id)
    emit('switch-folder', folder.id)
    closeDropdown()
  }

  // 关闭下拉菜单的键盘事件
  function handleKeydown(e) {
    if (e.key === 'Escape' && dropdownVisible.value) {
      closeDropdown()
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeydown)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('keydown', handleKeydown)
  })

  return {
    dropdownVisible,
    dropdownStyle,
    currentItemId,
    siblingFolders,
    handleRootClick,
    handleItemClick,
    toggleDropdown,
    closeDropdown,
    handleSiblingSelect
  }
}
