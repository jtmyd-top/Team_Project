import { computed } from 'vue'

export function useMoveFolderItem(props, emit) {
  const hasChildren = computed(() => {
    return props.folder.children && props.folder.children.length > 0
  })

  const isExpanded = computed(() => {
    return props.expandedIds.has(props.folder.id)
  })

  function handleClick() {
    // 如果是当前文件夹，不允许选择
    if (props.currentFolderId === props.folder.id) return

    emit('select', props.folder.id, props.folder.name)
  }

  return {
    hasChildren,
    isExpanded,
    handleClick
  }
}
