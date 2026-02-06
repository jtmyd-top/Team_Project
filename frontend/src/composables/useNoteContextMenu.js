import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'

export function useNoteContextMenu(props, emit) {
  const menuRef = ref(null)
  const adjustedX = ref(0)
  const adjustedY = ref(0)

  // 计算菜单位置，确保不超出屏幕
  const menuStyle = computed(() => {
    return {
      left: `${adjustedX.value}px`,
      top: `${adjustedY.value}px`
    }
  })

  // 调整菜单位置
  async function adjustPosition() {
    await nextTick()

    if (!menuRef.value) return

    const menuRect = menuRef.value.getBoundingClientRect()
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    let x = props.x
    let y = props.y

    // 如果菜单超出右边界，向左偏移
    if (x + menuRect.width > viewportWidth - 10) {
      x = viewportWidth - menuRect.width - 10
    }

    // 如果菜单超出下边界，向上偏移
    if (y + menuRect.height > viewportHeight - 10) {
      y = viewportHeight - menuRect.height - 10
    }

    // 确保不小于0
    adjustedX.value = Math.max(10, x)
    adjustedY.value = Math.max(10, y)
  }

  // 处理遮罩点击
  function handleOverlayClick() {
    emit('close')
  }

  // 处理菜单项点击
  function handleAction(action) {
    emit('action', action, props.note)
    emit('close')
  }

  // 处理键盘事件
  function handleKeydown(event) {
    if (!props.visible) return

    if (event.key === 'Escape') {
      emit('close')
    }
  }

  // 监听 visible 变化，调整位置
  watch(() => props.visible, (newVal) => {
    if (newVal) {
      adjustPosition()
    }
  })

  // 监听坐标变化
  watch([() => props.x, () => props.y], () => {
    if (props.visible) {
      adjustPosition()
    }
  })

  onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
  })

  return {
    menuRef,
    menuStyle,
    handleOverlayClick,
    handleAction
  }
}
