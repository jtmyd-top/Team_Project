import { ref, computed, watch } from 'vue'

/**
 * ConfirmDialog composable
 * @param {Object} props - Component props
 * @param {Function} emit - Emit function
 * @returns {Object} - Composable state and methods
 */
export function useConfirmDialog(props, emit) {
  const isVisible = ref(props.modelValue)
  const resolvePromise = ref(null)

  // 确认按钮样式
  const confirmClass = computed(() => {
    const classes = {
      primary: 'btn-primary',
      danger: 'btn-danger',
      warning: 'btn-warning'
    }
    return classes[props.type] || classes.primary
  })

  // 显示对话框（返回 Promise）
  const show = () => {
    return new Promise((resolve) => {
      isVisible.value = true
      resolvePromise.value = resolve
    })
  }

  // 确认
  const handleConfirm = () => {
    isVisible.value = false
    emit('update:modelValue', false)
    emit('confirm')
    if (resolvePromise.value) {
      resolvePromise.value(true)
    }
  }

  // 取消
  const handleCancel = () => {
    isVisible.value = false
    emit('update:modelValue', false)
    emit('cancel')
    if (resolvePromise.value) {
      resolvePromise.value(false)
    }
  }

  // 监听 modelValue 变化
  watch(() => props.modelValue, (newVal) => {
    isVisible.value = newVal
  })

  // 监听 isVisible 变化，同步到 modelValue
  watch(isVisible, (newVal) => {
    if (newVal !== props.modelValue) {
      emit('update:modelValue', newVal)
    }
  })

  return {
    isVisible,
    confirmClass,
    show,
    handleConfirm,
    handleCancel
  }
}
