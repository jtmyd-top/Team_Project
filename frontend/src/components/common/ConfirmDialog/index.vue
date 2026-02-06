<template>
  <Teleport to="body">
    <transition name="fade">
      <div v-if="isVisible" class="confirm-dialog-overlay" @click.self="handleCancel">
        <div class="confirm-dialog-box">
          <div class="confirm-dialog-header">
            <h3>{{ title }}</h3>
          </div>
          <div class="confirm-dialog-body">
            <p>{{ message }}</p>
          </div>
          <div class="confirm-dialog-footer">
            <button class="btn btn-text" @click="handleCancel">
              {{ cancelText }}
            </button>
            <button
              class="btn"
              :class="confirmClass"
              @click="handleConfirm"
            >
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import '@/assets/styles/components/confirm-dialog.css'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: '确认'
  },
  message: {
    type: String,
    required: true
  },
  confirmText: {
    type: String,
    default: '确定'
  },
  cancelText: {
    type: String,
    default: '取消'
  },
  type: {
    type: String,
    default: 'primary',
    validator: (value) => ['primary', 'danger', 'warning'].includes(value)
  }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const {
  isVisible,
  confirmClass,
  show,
  handleConfirm,
  handleCancel
} = useConfirmDialog(props, emit)

defineExpose({
  show
})
</script>
