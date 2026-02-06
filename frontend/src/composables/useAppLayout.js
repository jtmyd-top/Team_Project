import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useUserStore } from '@stores/user.js'

/**
 * AppLayout 组件的业务逻辑
 * @param {Object} props - 组件 props
 * @param {Function} emit - 组件 emit 函数
 * @returns {Object} 组件所需的状态和方法
 */
export function useAppLayout(props, emit) {
  // 使用 Pinia store
  const userStore = useUserStore()

  // 本地状态
  const searchQuery = ref('')
  const activeNav = ref(userStore.activeTab || 'all')
  const draggingItemId = ref(null)
  const folderPickerVisible = ref(false)
  const folderPickerPosition = ref({ x: 0, y: 0 })

  // 计算属性
  const isSidebarCollapsed = computed(() => userStore.isSidebarCollapsed)
  const expandedFolderIds = computed(() => userStore.expandedFolderIds)

  // 主题类
  const themeClass = computed(() => {
    const mode = userStore.theme?.mode || 'system'
    if (mode === 'system') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark-theme' : 'light-theme'
    }
    return mode === 'dark' ? 'dark-theme' : 'light-theme'
  })

  // 方法
  const toggleSidebar = () => {
    userStore.toggleSidebar()
  }

  const handleNavChange = (navId) => {
    activeNav.value = navId
    userStore.setActiveTab(navId)
    emit('nav-change', navId)

    // 自动展开侧边栏
    if (userStore.isSidebarCollapsed && navId !== 'settings') {
      userStore.setSidebarCollapsed(false)
    }
  }

  const handleSelect = (item) => {
    emit('select', item)
  }

  const handleCreateNew = () => {
    emit('create-new')
  }

  const handleToggleExpand = (folderId) => {
    userStore.toggleFolderExpanded(folderId)
  }

  const handleAddChild = (folder) => {
    emit('add-child', folder)
  }

  const handleMoreAction = (item) => {
    emit('more-action', item)
  }

  const handleBreadcrumbClick = (crumb, index, event) => {
    // 如果是最后一个面包屑(当前位置)，显示文件夹选择器
    if (index === props.breadcrumbs.length - 1 && event) {
      const rect = event.target.getBoundingClientRect()
      folderPickerPosition.value = {
        x: rect.left,
        y: rect.bottom + 8
      }
      folderPickerVisible.value = true
    } else {
      emit('breadcrumb-click', { crumb, index })
    }
  }

  const handleUserClick = () => {
    emit('user-click')
  }

  const handleViewChange = (view) => {
    emit('view-change', view)
  }

  const handleMoveItem = (moveData) => {
    emit('move-item', moveData)
  }

  const handleFolderSelect = (folder) => {
    emit('folder-select', folder)
  }

  const handleCreateFolder = () => {
    emit('create-folder')
  }

  // 键盘快捷键处理
  const handleKeydown = (event) => {
    // Ctrl+N: 新建笔记
    if ((event.ctrlKey || event.metaKey) && event.key === 'n') {
      event.preventDefault()
      handleCreateNew()
    }
    // Ctrl+B: 切换侧边栏
    if ((event.ctrlKey || event.metaKey) && event.key === 'b') {
      event.preventDefault()
      toggleSidebar()
    }
    // Ctrl+K: 聚焦搜索
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
      event.preventDefault()
      emit('search')
    }
  }

  // 监听系统主题变化和键盘事件
  onMounted(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQuery.addEventListener('change', () => {
      // 触发重新计算主题类
    })

    // 添加键盘事件监听
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
  })

  return {
    // Store
    userStore,
    // 状态
    searchQuery,
    activeNav,
    draggingItemId,
    folderPickerVisible,
    folderPickerPosition,
    // 计算属性
    isSidebarCollapsed,
    expandedFolderIds,
    themeClass,
    // 方法
    toggleSidebar,
    handleNavChange,
    handleSelect,
    handleCreateNew,
    handleToggleExpand,
    handleAddChild,
    handleMoreAction,
    handleBreadcrumbClick,
    handleUserClick,
    handleViewChange,
    handleMoveItem,
    handleFolderSelect,
    handleCreateFolder
  }
}
