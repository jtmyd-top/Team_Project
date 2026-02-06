import { ref, computed, onUnmounted } from 'vue'

export function useDropFolderItem(props, emit) {
  // 状态
  const isExpanded = ref(true) // 默认展开
  let springLoadTimer = null // Spring-loading 定时器

  // 计算属性
  const hasChildren = computed(() => {
    return props.folder.children && props.folder.children.length > 0
  })

  // 方法
  function toggleExpand() {
    isExpanded.value = !isExpanded.value
  }

  function handleDragOver(event) {
    emit('dragover', props.folder.id, event)

    // Spring-loading: 悬停 500ms 后自动展开
    if (hasChildren.value && !isExpanded.value && !springLoadTimer) {
      springLoadTimer = setTimeout(() => {
        isExpanded.value = true
        springLoadTimer = null
      }, 500)
    }
  }

  function handleDragLeave() {
    // 清除 spring-loading 定时器
    if (springLoadTimer) {
      clearTimeout(springLoadTimer)
      springLoadTimer = null
    }
    emit('dragleave')
  }

  function handleDrop(event) {
    // 清除 spring-loading 定时器
    if (springLoadTimer) {
      clearTimeout(springLoadTimer)
      springLoadTimer = null
    }
    emit('drop', props.folder.id, props.folder.name, event)
  }

  // 清理定时器
  onUnmounted(() => {
    if (springLoadTimer) {
      clearTimeout(springLoadTimer)
    }
  })

  return {
    isExpanded,
    hasChildren,
    toggleExpand,
    handleDragOver,
    handleDragLeave,
    handleDrop
  }
}
