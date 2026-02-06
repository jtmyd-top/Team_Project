import { ref, computed, nextTick } from 'vue'

export function useFolderTreeItem(props, emit) {
  // 状态
  const isExpanded = ref(false)
  const isEditing = ref(false)
  const editName = ref('')
  const nameInput = ref(null)
  const isDragOver = ref(false)

  // 计算属性
  const hasChildren = computed(() => {
    return props.folder.children && props.folder.children.length > 0
  })

  // 拖拽相关方法
  function handleDragOver(event) {
    event.dataTransfer.dropEffect = 'move'
    isDragOver.value = true
  }

  function handleDragLeave(event) {
    // 确保只在真正离开时才取消高亮（避免进入子元素时触发）
    const rect = event.currentTarget.getBoundingClientRect()
    const x = event.clientX
    const y = event.clientY

    if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
      isDragOver.value = false
    }
  }

  function handleDrop(event) {
    isDragOver.value = false

    const data = event.dataTransfer.getData('application/json')
    if (!data) return

    try {
      const payload = JSON.parse(data)

      // 确保拖拽的是笔记
      if (payload.type === 'NOTE_ITEM') {
        // 如果已经在这个文件夹中，不执行移动
        if (payload.currentFolderId === props.folder.id) {
          console.log('笔记已在此文件夹中，无需移动')
          return
        }

        // 发出事件，让父组件处理 API 调用
        emit('note-drop', {
          noteId: payload.id,
          noteTitle: payload.title,
          targetFolderId: props.folder.id,
          targetFolderName: props.folder.name
        })
      }
    } catch (e) {
      console.error('解析拖拽数据失败:', e)
    }
  }

  // 方法
  function toggleExpand() {
    isExpanded.value = !isExpanded.value
  }

  function handleClick() {
    if (!isEditing.value) {
      emit('click', props.folder)
    }
  }

  function startEdit() {
    editName.value = props.folder.name
    isEditing.value = true
    nextTick(() => {
      nameInput.value?.focus()
      nameInput.value?.select()
    })
  }

  function finishEdit() {
    if (editName.value.trim() && editName.value !== props.folder.name) {
      emit('rename', { folder: props.folder, newName: editName.value.trim() })
    }
    isEditing.value = false
  }

  function cancelEdit() {
    isEditing.value = false
    editName.value = ''
  }

  function handleDelete() {
    emit('delete', props.folder)
  }

  function handleCreateSubfolder() {
    emit('create-subfolder', props.folder)
  }

  function showContextMenu(e) {
    // 可以扩展为显示右键菜单
  }

  return {
    isExpanded,
    isEditing,
    editName,
    nameInput,
    isDragOver,
    hasChildren,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    toggleExpand,
    handleClick,
    startEdit,
    finishEdit,
    cancelEdit,
    handleDelete,
    handleCreateSubfolder,
    showContextMenu
  }
}
