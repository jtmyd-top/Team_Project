import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'

/**
 * FolderPicker 组件的业务逻辑
 * @param {Object} props - 组件 props
 * @param {Function} emit - 组件 emit 函数
 * @returns {Object} 组件所需的状态和方法
 */
export function useFolderPicker(props, emit) {
  const searchQuery = ref('')
  const searchInput = ref(null)

  /**
   * 计算弹窗位置样式
   */
  const popupStyle = computed(() => {
    return {
      left: `${props.anchorPosition.x}px`,
      top: `${props.anchorPosition.y}px`
    }
  })

  /**
   * 扁平化文件夹树
   * @param {Array} items - 文件夹树
   * @param {Array} result - 结果数组
   * @param {number} depth - 当前深度
   * @returns {Array} 扁平化后的文件夹列表
   */
  const flattenFolders = (items, result = [], depth = 0) => {
    for (const item of items) {
      if (item.type === 'folder') {
        result.push({
          ...item,
          depth,
          displayTitle: '  '.repeat(depth) + (item.title || item.name)
        })
        if (item.children && item.children.length) {
          flattenFolders(item.children, result, depth + 1)
        }
      }
    }
    return result
  }

  /**
   * 所有文件夹（扁平化）
   */
  const allFolders = computed(() => flattenFolders(props.folders))

  /**
   * 过滤后的文件夹列表
   */
  const filteredFolders = computed(() => {
    if (!searchQuery.value) return allFolders.value

    const query = searchQuery.value.toLowerCase()
    return allFolders.value.filter(folder =>
      (folder.title || folder.name || '').toLowerCase().includes(query)
    )
  })

  /**
   * 选择文件夹
   * @param {Object} folder - 选中的文件夹
   */
  const selectFolder = (folder) => {
    if (folder.id === props.currentFolderId) return
    emit('select', folder)
    handleClose()
  }

  /**
   * 关闭弹窗
   */
  const handleClose = () => {
    searchQuery.value = ''
    emit('close')
  }

  /**
   * 创建文件夹
   */
  const handleCreateFolder = () => {
    emit('create-folder')
  }

  /**
   * 键盘事件处理
   * @param {KeyboardEvent} event - 键盘事件
   */
  const handleKeydown = (event) => {
    if (!props.visible) return

    if (event.key === 'Escape') {
      handleClose()
    }
  }

  // 监听 visible 变化，自动聚焦搜索框
  watch(() => props.visible, (newVal) => {
    if (newVal) {
      nextTick(() => {
        searchInput.value?.focus()
      })
    }
  })

  // 生命周期钩子
  onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
  })

  return {
    searchQuery,
    searchInput,
    popupStyle,
    filteredFolders,
    selectFolder,
    handleClose,
    handleCreateFolder
  }
}
