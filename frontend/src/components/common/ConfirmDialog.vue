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
import { ref, computed, watch } from 'vue'

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

// 监 isVisible 变化，同步到 modelValue
watch(isVisible, (newVal) => {
  if (newVal !== props.modelValue) {
    emit('update:modelValue', newVal)
  }
})

defineExpose({
  show
})
</script>

<style scoped>
.confirm-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.confirm-dialog-box {
  background: var(--k-bg, #fff);
  border-radius: 8px;
  width: 90%;
  max-width: 400px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.confirm-dialog-header {
  padding: 20px 20px 10px;
}

.confirm-dialog-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--k-text, #1a1a1a);
}

.confirm-dialog-body {
  padding: 10px 20px 20px;
}

.confirm-dialog-body p {
  margin: 0;
  font-size: 14px;
  color: var(--k-text-sec, #666);
  line-height: 1.5;
}

.confirm-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 10px 20px;
  border-top: 1px solid var(--k-border, #e0e0e0);
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.btn-text {
  background: transparent;
  color: var(--k-text, #1a1a1a);
  border-color: transparent;
}

.btn-text:hover {
  background: var(--k-hover, #f5f5f5);
}

.btn-primary {
  background: var(--k-primary, #1890ff);
  color: white;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-danger {
  background: #ef4444;
  color: white;
}

.btn-danger:hover {
  background: #dc2626;
}

.btn-warning {
  background: #f59e0b;
  color: white;
}

.btn-warning:hover {
  background: #d97706;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
