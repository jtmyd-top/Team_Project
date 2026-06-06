<template>
  <div class="message-modal-overlay" @click.self="closeModal">
    <div class="message-modal" :class="{ 'modal-entering': isEntering }">
      <!-- 头部 -->
      <div class="modal-header">
        <div class="recipient-info">
          <img :src="recipient.avatar" :alt="recipient.username" class="recipient-avatar">
          <div class="recipient-details">
            <h3 class="recipient-name">{{ recipient.username }}</h3>
            <span class="modal-label">私信</span>
          </div>
        </div>
        <button class="close-btn" @click="closeModal">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <!-- 消息输入区 -->
      <div class="message-input-section">
        <textarea
          v-model="messageContent"
          class="message-textarea"
          placeholder="输入你的私信内容..."
          @keydown.ctrl.enter="sendMessage"
          @keydown.meta.enter="sendMessage"
          maxlength="5000"
        ></textarea>
        <div class="input-footer">
          <span class="char-count">{{ messageContent.length }}/5000</span>
          <button
            class="send-btn"
            @click="sendMessage"
            :disabled="isSending || !messageContent.trim()">
            <i v-if="!isSending" class="fas fa-paper-plane"></i>
            <i v-else class="fas fa-spinner fa-spin"></i>
            <span>{{ isSending ? '发送中...' : '发送' }}</span>
          </button>
        </div>
      </div>

      <!-- 错误提示 -->
      <div v-if="errorMessage" class="error-message">
        <i class="fas fa-exclamation-circle"></i>
        {{ errorMessage }}
      </div>

      <!-- 成功提示 -->
      <div v-if="successMessage" class="success-message">
        <i class="fas fa-check-circle"></i>
        {{ successMessage }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { getCsrfToken } from '@utils/csrf'

const props = defineProps({
  recipient: {
    type: Object,
    required: true,
    properties: {
      id: Number,
      username: String,
      avatar: String,
    }
  }
})

const emit = defineEmits(['close', 'sent'])

const isEntering = ref(true)
const messageContent = ref('')
const isSending = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

// 关闭弹窗
const closeModal = () => {
  isEntering.value = false
  setTimeout(() => {
    emit('close')
  }, 300)
}

// 发送消息
const sendMessage = async () => {
  if (!messageContent.value.trim()) {
    errorMessage.value = '消息内容不能为空'
    return
  }

  isSending.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    const response = await fetch('/api/messages/send/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({
        recipient_id: props.recipient.id,
        content: messageContent.value.trim(),
      })
    })

    const data = await response.json()

    if (response.ok) {
      successMessage.value = '消息已发送'
      messageContent.value = ''
      emit('sent', data.message)
      // 3秒后关闭
      setTimeout(() => {
        closeModal()
      }, 1500)
    } else {
      errorMessage.value = data.message || data.error || '发送失败，请重试'
    }
  } catch (error) {
    console.error('发送消息失败:', error)
    errorMessage.value = '网络错误，请重试'
  } finally {
    isSending.value = false
  }
}
</script>

<style scoped>
.message-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.message-modal {
  background: white;
  border-radius: 16px;
  width: 90%;
  max-width: 500px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  overflow: hidden;
  animation: slideUp 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.modal-entering {
  animation: slideUp 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes slideUp {
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
  padding: 20px;
  background: #f5f5f5;
  border-bottom: 1px solid #eee;
}

.recipient-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.recipient-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
}

.recipient-details {
  flex: 1;
}

.recipient-name {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: #333;
}

.modal-label {
  font-size: 12px;
  color: #999;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #e8e8e8;
  color: #333;
}

.message-input-section {
  padding: 20px;
}

.message-textarea {
  width: 100%;
  min-height: 150px;
  max-height: 300px;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-family: inherit;
  font-size: 14px;
  resize: vertical;
  transition: all 0.2s;
}

.message-textarea:focus {
  outline: none;
  border-color: #409eff;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.1);
}

.input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.char-count {
  font-size: 12px;
  color: #999;
}

.send-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #66b1ff;
  transform: translateY(-2px);
}

.send-btn:disabled {
  background: #d4d4d4;
  cursor: not-allowed;
  color: #999;
}

.error-message {
  padding: 12px 20px;
  margin: 0 20px 20px;
  background: #fef0f0;
  color: #f56c6c;
  border-left: 3px solid #f56c6c;
  border-radius: 4px;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.success-message {
  padding: 12px 20px;
  margin: 0 20px 20px;
  background: #f0f9ff;
  color: #67c23a;
  border-left: 3px solid #67c23a;
  border-radius: 4px;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
