/**
 * FolderTree 逻辑层
 * 处理文件夹树的展开/收起、节点选择、拖拽移动等功能
 */

import { ref } from 'vue'

export function useFolderTree(props, emit) {
  // 本地拖拽状态
  const dragOverId = ref(null)

  // ==================== 节点操作 ====================
  // 检查节点是否展开
  const isExpanded = (id) => {
    return props.expandedIds.includes(id)
  }

  // 切换展开状态
  const toggleExpand = (id) => {
    emit('toggle-expand', id)
  }

  // 点击节点
  const handleClick = (item) => {
    if (item.type === 'folder') {
      toggleExpand(item.id)
    }
    emit('select', item)
  }

  // ==================== 图标获取 ====================
  const getIcon = (item) => {
    if (item.icon) return item.icon

    if (item.type === 'folder') {
      return isExpanded(item.id) ? 'fas fa-folder-open' : 'fas fa-folder'
    }

    // 根据类型返回不同图标
    const iconMap = {
      note: 'fas fa-file-alt',
      document: 'fas fa-file-word',
      image: 'fas fa-file-image',
      code: 'fas fa-file-code',
      default: 'fas fa-file'
    }

    return iconMap[item.type] || iconMap.default
  }

  // ==================== 拖拽操作 ====================
  // 拖拽开始
  const handleDragStart = (event, item) => {
    if (!props.draggable || item.type === 'folder') {
      event.preventDefault()
      return
    }

    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('application/json', JSON.stringify({
      id: item.id,
      type: item.type,
      title: item.title || item.name
    }))

    emit('update:dragging-id', item.id)
  }

  // 拖拽结束
  const handleDragEnd = () => {
    emit('update:dragging-id', null)
    dragOverId.value = null
  }

  // 拖拽经过
  const handleDragOver = (event, item) => {
    // 只有文件夹可以作为放置目标
    if (item.type !== 'folder') return
    // 不能拖到正在拖拽的元素本身
    if (item.id === props.draggingId) return

    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
    dragOverId.value = item.id
  }

  // 拖拽离开
  const handleDragLeave = () => {
    dragOverId.value = null
  }

  // 放置
  const handleDrop = (event, targetFolder) => {
    event.preventDefault()
    dragOverId.value = null

    // 只有文件夹可以作为放置目标
    if (targetFolder.type !== 'folder') return

    try {
      const data = JSON.parse(event.dataTransfer.getData('application/json'))

      // 不能移动到自己
      if (data.id === targetFolder.id) return

      emit('move-item', {
        itemId: data.id,
        itemType: data.type,
        itemTitle: data.title,
        targetFolderId: targetFolder.id,
        targetFolderTitle: targetFolder.title || targetFolder.name
      })
    } catch (e) {
      console.error('Drop failed:', e)
    }
  }

  // ==================== 返回 ====================
  return {
    dragOverId,
    isExpanded,
    toggleExpand,
    handleClick,
    getIcon,
    handleDragStart,
    handleDragEnd,
    handleDragOver,
    handleDragLeave,
    handleDrop
  }
}
