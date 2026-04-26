<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-header">
        <h3>
          <i class="fas fa-fire-alt"></i>
          阅后即焚设置
        </h3>
        <button class="close-btn" @click="$emit('close')">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="modal-body">
        <div class="toggle-row">
          <div class="toggle-info">
            <h4>开启阅后即焚</h4>
            <p>对方阅读消息后，消息将在设定时间内自动从双方视图中销毁。</p>
          </div>
          <label class="switch">
            <input type="checkbox" v-model="enabled" />
            <span class="slider"></span>
          </label>
        </div>

        <div v-if="enabled" class="ttl-section">
          <label class="field-label">销毁倒计时</label>
          <div class="ttl-options">
            <label
              v-for="opt in options"
              :key="opt.value"
              class="ttl-option"
              :class="{ active: ttl === opt.value }"
            >
              <input type="radio" v-model="ttl" :value="opt.value" />
              <span>{{ opt.label }}</span>
            </label>
          </div>

          <div class="warning">
            <i class="fas fa-exclamation-triangle"></i>
            本功能仅影响当前对话双方已读消息的自动销毁逻辑。已被导出或截图的内容将无法撤销。
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button class="cancel-btn" @click="$emit('close')">取消</button>
        <button class="save-btn" @click="save" :disabled="saving">
          <i v-if="saving" class="fas fa-spinner fa-spin"></i>
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  peerId: { type: Number, required: true },
  initialEnabled: { type: Boolean, default: false },
  initialTtl: { type: Number, default: 86400 },
  csrfToken: { type: String, default: '' },
})

const emit = defineEmits(['close', 'saved'])

const enabled = ref(props.initialEnabled)
const ttl = ref(props.initialTtl || 86400)
const saving = ref(false)

const options = [
  { value: 0, label: '阅读后立即' },
  { value: 3600, label: '1 小时' },
  { value: 86400, label: '24 小时' },
  { value: 604800, label: '7 天' },
]

async function save() {
  saving.value = true
  try {
    const r = await fetch('/api/messages/conversation/disappearing/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken,
      },
      body: JSON.stringify({
        user_id: props.peerId,
        enabled: enabled.value,
        ttl_seconds: ttl.value,
      }),
    })
    const d = await r.json().catch(() => ({}))
    if (r.ok) {
      ElMessage.success(enabled.value ? '阅后即焚已开启' : '阅后即焚已关闭')
      emit('saved', { enabled: enabled.value, ttl: ttl.value })
      emit('close')
    } else {
      ElMessage.error(d.error || '保存失败')
    }
  } catch (e) {
    ElMessage.error('网络错误')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10001;
  animation: fade-in 0.2s;
}

@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal {
  width: 90%;
  max-width: 440px;
  background: var(--bg-primary);
  border-radius: 14px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.28);
  overflow: hidden;
  animation: slide-up 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes slide-up {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 22px;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 10px;
}

.modal-header i {
  color: #f59e0b;
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  cursor: pointer;
}

.close-btn:hover {
  background: var(--bg-tertiary);
}

.modal-body {
  padding: 20px 22px;
}

.toggle-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-light, var(--border-color));
}

.toggle-info h4 {
  margin: 0 0 4px 0;
  font-size: 14px;
  color: var(--text-primary);
}

.toggle-info p {
  margin: 0;
  font-size: 12.5px;
  color: var(--text-tertiary);
  line-height: 1.5;
}

.switch {
  position: relative;
  width: 42px;
  height: 22px;
  flex-shrink: 0;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  inset: 0;
  background: var(--border-color);
  border-radius: 22px;
  cursor: pointer;
  transition: 0.2s;
}

.slider::before {
  content: '';
  position: absolute;
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background: white;
  border-radius: 50%;
  transition: 0.2s;
}

.switch input:checked + .slider {
  background: #f59e0b;
}

.switch input:checked + .slider::before {
  transform: translateX(20px);
}

.ttl-section {
  margin-top: 16px;
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.ttl-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 14px;
}

.ttl-option {
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-primary);
  transition: all 0.15s;
}

.ttl-option input {
  display: none;
}

.ttl-option:hover {
  border-color: #f59e0b;
}

.ttl-option.active {
  border-color: #f59e0b;
  background: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
  font-weight: 500;
}

.warning {
  padding: 10px 12px;
  background: rgba(245, 158, 11, 0.1);
  border-left: 3px solid #f59e0b;
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.warning i {
  color: #f59e0b;
  margin-top: 2px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 22px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.cancel-btn,
.save-btn {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  border: none;
  display: flex;
  align-items: center;
  gap: 6px;
}

.cancel-btn {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
}

.save-btn {
  background: #f59e0b;
  color: #fff;
}

.save-btn:hover:not(:disabled) {
  background: #d97706;
}

.save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
