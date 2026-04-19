<template>
  <div v-if="isVisible" class="user-card-modal-overlay" @click.self="closeModal">
    <div class="user-card-modal" :class="{ 'modal-entering': isEntering }">
      <!-- 头部 -->
      <div class="modal-header">
        <button class="close-btn" @click="closeModal">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <!-- 用户信息 -->
      <div class="user-info">
        <div class="avatar-wrapper">
          <img :src="userInfo.avatar" :alt="userInfo.username" class="user-avatar">
        </div>
        <h3 class="user-name">{{ userInfo.username }}</h3>
        <p v-if="userInfo.bio" class="user-bio">{{ userInfo.bio }}</p>
        <p v-else class="user-bio placeholder">这个人很懒，什么都没写...</p>

        <!-- 用户统计 -->
        <div class="user-stats">
          <div class="stat-item">
            <span class="stat-label">笔记</span>
            <span class="stat-value">{{ userInfo.notes_count || 0 }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">阅读</span>
            <span class="stat-value">{{ userInfo.views_count || 0 }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">点赞</span>
            <span class="stat-value">{{ userInfo.likes_count || 0 }}</span>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-buttons">
        <!-- 私信按钮 -->
        <button
          v-if="isCurrentUser === false"
          class="action-btn message-btn"
          @click="openMessageModal"
          title="私信此用户">
          <i class="fas fa-envelope"></i>
          <span>私信</span>
        </button>

        <!-- 查看主页 -->
        <button
          class="action-btn profile-btn"
          @click="goToProfile"
          title="查看用户主页">
          <i class="fas fa-user-circle"></i>
          <span>主页</span>
        </button>

        <!-- 屏蔽/取消屏蔽 -->
        <button
          v-if="isCurrentUser === false"
          class="action-btn block-btn"
          :class="{ 'is-blocked': isBlocked }"
          @click="toggleBlock"
          :title="isBlocked ? '取消屏蔽' : '屏蔽用户'">
          <i :class="isBlocked ? 'fas fa-check-circle' : 'fas fa-ban'"></i>
          <span>{{ isBlocked ? '已屏蔽' : '屏蔽' }}</span>
        </button>
      </div>

      <!-- 提示信息 -->
      <div v-if="isBlocked" class="info-message warning">
        <i class="fas fa-info-circle"></i>
        你已屏蔽此用户
      </div>

      <div v-if="messagePreference && !messagePreference.allow_messages" class="info-message">
        <i class="fas fa-lock"></i>
        此用户已禁用私信功能
      </div>
    </div>

    <!-- 私信窗口 -->
    <MessageModal
      v-if="showMessageModal"
      :recipient="userInfo"
      @close="closeMessageModal"
      @sent="onMessageSent"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import MessageModal from '@components/messages/MessageModal/index.vue'

const props = defineProps({
  userId: Number,
  isVisible: {
    type: Boolean,
    default: false
  },
  currentUserId: Number,
})

const emit = defineEmits(['close', 'message-sent'])

const isEntering = ref(false)
const showMessageModal = ref(false)
const isBlocked = ref(false)

const userInfo = reactive({
  username: '',
  avatar: '',
  bio: '',
  notes_count: 0,
  views_count: 0,
  likes_count: 0,
})

const messagePreference = ref(null)

const isCurrentUser = computed(() => {
  if (!props.userId || !props.currentUserId) return null
  return props.userId === props.currentUserId
})

// 加载用户信息
const loadUserInfo = async () => {
  try {
    const response = await fetch(`/api/users/${props.userId}/profile/`)
    if (response.ok) {
      const data = await response.json()
      Object.assign(userInfo, {
        username: data.username,
        avatar: data.avatar,
        bio: data.bio,
        notes_count: data.notes_count,
        views_count: data.views_count,
        likes_count: data.likes_count,
      })
    }
  } catch (error) {
    console.error('加载用户信息失败:', error)
  }
}

// 加载私信偏好设置
const loadMessagePreference = async () => {
  try {
    const response = await fetch(`/api/messages/preference/?user_id=${props.userId}`)
    if (response.ok) {
      const data = await response.json()
      messagePreference.value = data.preference
    }
  } catch (error) {
    console.error('加载私信设置失败:', error)
  }
}

// 关闭弹窗
const closeModal = () => {
  isEntering.value = false
  setTimeout(() => {
    emit('close')
  }, 300)
}

// 打开私信窗口
const openMessageModal = () => {
  showMessageModal.value = true
}

// 关闭私信窗口
const closeMessageModal = () => {
  showMessageModal.value = false
}

// 消息发送回调
const onMessageSent = () => {
  emit('message-sent')
  closeMessageModal()
}

// 导航到用户主页
const goToProfile = () => {
  window.location.href = `/user/${props.userId}/`
}

// 切换屏蔽状态
const toggleBlock = async () => {
  try {
    const endpoint = isBlocked.value ? '/api/users/unblock/' : '/api/users/block/'
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ user_id: props.userId })
    })

    if (response.ok) {
      isBlocked.value = !isBlocked.value
    }
  } catch (error) {
    console.error('屏蔽操作失败:', error)
  }
}

// 获取CSRF令牌
const getCsrfToken = () => {
  return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
         document.querySelector('[name=csrf]')?.value || ''
}

// 初始化
const initialize = () => {
  if (props.isVisible) {
    isEntering.value = true
    loadUserInfo()
    loadMessagePreference()
  }
}

// 监听props变化
import { watch } from 'vue'
watch(() => props.isVisible, (newVal) => {
  if (newVal) {
    initialize()
  }
})
</script>

<style scoped>
.user-card-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
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

.user-card-modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  animation: slideUp 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  max-height: 90vh;
  overflow-y: auto;
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
  justify-content: flex-end;
  margin-bottom: 16px;
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
  background: #f0f0f0;
  color: #333;
}

.user-info {
  text-align: center;
  margin-bottom: 24px;
}

.avatar-wrapper {
  margin-bottom: 16px;
}

.user-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid #409eff;
}

.user-name {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 8px 0;
  color: #333;
}

.user-bio {
  font-size: 14px;
  color: #666;
  margin: 0 0 16px 0;
  line-height: 1.5;
}

.user-bio.placeholder {
  color: #999;
  font-style: italic;
}

.user-stats {
  display: flex;
  justify-content: space-around;
  padding: 16px;
  background: #f5f5f5;
  border-radius: 8px;
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.action-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

.action-btn {
  padding: 12px 16px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}

.message-btn {
  grid-column: 1;
  background: #409eff;
  color: white;
  border: 1px solid #409eff;
}

.message-btn:hover {
  background: #66b1ff;
  transform: translateY(-2px);
}

.profile-btn {
  grid-column: 2;
  background: #f0f0f0;
  color: #333;
  border: 1px solid #ddd;
}

.profile-btn:hover {
  background: #e8e8e8;
  transform: translateY(-2px);
}

.block-btn {
  grid-column: 1 / -1;
  background: white;
  color: #f56c6c;
  border: 1px solid #f56c6c;
}

.block-btn:hover {
  background: #fef0f0;
}

.block-btn.is-blocked {
  background: #f0f0f0;
  color: #666;
  border-color: #ddd;
}

.info-message {
  padding: 12px 16px;
  background: #f0f9ff;
  border-left: 3px solid #409eff;
  border-radius: 4px;
  font-size: 13px;
  color: #666;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.info-message.warning {
  background: #fef0f0;
  border-left-color: #f56c6c;
  color: #f56c6c;
}
</style>
