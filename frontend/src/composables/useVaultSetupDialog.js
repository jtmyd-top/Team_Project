import { computed } from 'vue'

/**
 * VaultSetupDialog composable
 * @param {Object} props - Component props
 * @param {Function} emit - Emit function
 * @returns {Object} - Composable state and methods
 */
export function useVaultSetupDialog(props, emit) {
  const dialogVisible = computed({
    get: () => props.modelValue,
    set: (val) => emit('update:modelValue', val)
  })

  const handleGoToSettings = () => {
    emit('go-to-settings')
    dialogVisible.value = false
  }

  const handleClose = () => {
    emit('cancel')
  }

  return {
    dialogVisible,
    handleGoToSettings,
    handleClose
  }
}
