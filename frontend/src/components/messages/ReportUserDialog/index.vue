<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-header">
        <h3>
          <i class="fas fa-flag"></i>
          举报用户
        </h3>
        <button class="close-btn" @click="$emit('close')">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="modal-body">
        <div class="target-hint">
          举报对象：<strong>{{ targetUsername }}</strong>
          <span v-if="messageSnippet" class="snippet">
            关联消息："{{ messageSnippet.slice(0, 40) }}{{ messageSnippet.length > 40 ? '...' : '' }}"
          </span>
        </div>

        <label class="field-label">请选择举报原因</label>
        <div class="reasons">
          <label
            v-for="r in reasons"
            :key="r.value"
            class="reason-option"
            :class="{ active: selectedReason === r.value }"
          >
            <input type="radio" v-model="selectedReason" :value="r.value" />
            <span class="radio-dot"></span>
            <span class="label">{{ r.label }}</span>
          </label>
        </div>

        <label class="field-label">补充说明（可选）</label>
        <textarea
          v-model="detail"
          class="detail-input"
          placeholder="请描述具体情况，将帮助我们更快处理..."
          maxlength="500"
        ></textarea>
        <div class="detail-count">{{ detail.length }}/500</div>
      </div>

      <div class="modal-footer">
        <button class="cancel-btn" @click="$emit('close')">取消</button>
        <button class="submit-btn" @click="submit" :disabled="submitting">
          <i v-if="submitting" class="fas fa-spinner fa-spin"></i>
          {{ submitting ? '提交中...' : '提交举报' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  targetUserId: { type: Number, required: true },
  targetUsername: { type: String, default: '' },
  messageId: { type: Number, default: null },
  messageSnippet: { type: String, default: '' },
  csrfToken: { type: String, default: '' },
})

const emit = defineEmits(['close', 'submitted'])

const selectedReason = ref('spam')
const detail = ref('')
const submitting = ref(false)

const reasons = [
  { value: 'spam', label: '垃圾广告' },
  { value: 'abuse', label: '辱骂骚扰' },
  { value: 'porn', label: '色情低俗' },
  { value: 'scam', label: '诈骗欺诈' },
  { value: 'other', label: '其他' },
]

async function submit() {
  submitting.value = true
  try {
    const r = await fetch('/api/users/report/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken,
      },
      body: JSON.stringify({
        user_id: props.targetUserId,
        message_id: props.messageId,
        reason: selectedReason.value,
        detail: detail.value.trim(),
      }),
    })
    const d = await r.json().catch(() => ({}))
    if (r.ok) {
      ElMessage.success(d.message || '举报已提交')
      emit('submitted')
      emit('close')
    } else {
      ElMessage.error(d.message || d.error || '举报失败')
    }
  } catch (e) {
    ElMessage.error('网络错误，请重试')
  } finally {
    submitting.value = false
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
  max-width: 460px;
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
  color: var(--danger-color, #ef4444);
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: var(--bg-tertiary);
}

.modal-body {
  padding: 20px 22px;
}

.target-hint {
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  margin-bottom: 18px;
}

.target-hint strong {
  color: var(--text-primary);
}

.snippet {
  display: block;
  color: var(--text-tertiary);
  margin-top: 4px;
  font-size: 12px;
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.reasons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 20px;
}

.reason-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 13px;
  color: var(--text-primary);
}

.reason-option:hover {
  border-color: var(--primary-color);
}

.reason-option.active {
  border-color: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color, #2563eb) 10%, transparent);
}

.reason-option input {
  display: none;
}

.radio-dot {
  width: 14px;
  height: 14px;
  border: 1.5px solid var(--border-color);
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
  transition: all 0.15s;
}

.reason-option.active .radio-dot {
  border-color: var(--primary-color);
}

.reason-option.active .radio-dot::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary-color);
}

.detail-input {
  width: 100%;
  min-height: 80px;
  max-height: 160px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-family: inherit;
  font-size: 13px;
  resize: vertical;
  outline: none;
}

.detail-input:focus {
  border-color: var(--primary-color);
}

.detail-count {
  text-align: right;
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 4px;
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
.submit-btn {
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

.cancel-btn:hover {
  border-color: var(--text-secondary);
}

.submit-btn {
  background: var(--danger-color, #ef4444);
  color: #fff;
}

.submit-btn:hover:not(:disabled) {
  background: #dc2626;
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
