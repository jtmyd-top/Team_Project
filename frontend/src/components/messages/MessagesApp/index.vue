<template>
  <div class="messages-container">
    <!-- 左侧：对话列表 -->
    <aside class="conversations-sidebar">
      <div class="sidebar-header">
        <h2>私信</h2>
        <button class="new-message-btn" @click="showNewMessageDialog = true" title="新建私信">
          <i class="fas fa-pen-fancy"></i>
        </button>
      </div>

      <!-- 搜索框 -->
      <div class="search-box">
        <i class="fas fa-search"></i>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索对话..."
          @input="filterConversations">
      </div>

      <!-- 对话列表 -->
      <div class="conversations-list">
        <div
          v-if="filteredConversations.length === 0"
          class="empty-state">
          <i class="fas fa-inbox"></i>
          <p>{{ searchQuery ? '没有找到对话' : '还没有私信' }}</p>
        </div>

        <div
          v-for="conv in filteredConversations"
          :key="conv.user_id"
          class="conversation-item"
          :class="{ 'active': selectedUserId === conv.user_id }"
          @click="selectConversation(conv)">
          <img :src="conv.avatar" :alt="conv.username" class="conv-avatar">
          <div class="conv-info">
            <div class="conv-header">
              <h3 class="conv-name">{{ conv.username }}</h3>
              <span class="conv-time">{{ formatTime(conv.last_message_time) }}</span>
            </div>
            <p class="conv-message">{{ truncateMessage(conv.last_message) }}</p>
          </div>
          <div v-if="conv.unread_count > 0" class="unread-badge">
            {{ conv.unread_count }}
          </div>
        </div>
      </div>
    </aside>

    <!-- 右侧：对话详情或空状态 -->
    <main class="chat-area">
      <div v-if="selectedUserId" class="chat-container">
        <!-- 聊天头部 -->
        <div class="chat-header">
          <div class="chat-user-info">
            <img :src="selectedConversation?.avatar" :alt="selectedConversation?.username" class="chat-avatar">
            <h2>{{ selectedConversation?.username }}</h2>
          </div>
          <button class="close-chat-btn" @click="selectedUserId = null" title="关闭">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <!-- 消息列表 -->
        <div class="messages-list" ref="messagesListRef">
          <div v-if="messages.length === 0" class="no-messages">
            <p>暂无对话历史</p>
          </div>

          <div
            v-for="msg in messages"
            :key="msg.id"
            class="message-item"
            :class="{ 'own': msg.sender_id === currentUserId }">
            <img :src="msg.sender_avatar" :alt="msg.sender" class="message-avatar">
            <div class="message-content">
              <div class="message-text">{{ msg.content }}</div>
              <span class="message-time">{{ formatMessageTime(msg.created_at) }}</span>
            </div>
          </div>
        </div>

        <!-- 消息输入框 -->
        <div class="message-input-area">
          <textarea
            v-model="newMessage"
            class="message-input"
            placeholder="输入消息..."
            @keydown.ctrl.enter="sendMessage"
            @keydown.meta.enter="sendMessage"
            maxlength="5000">
          </textarea>
          <div class="input-actions">
            <span class="char-count">{{ newMessage.length }}/5000</span>
            <button
              class="send-btn"
              @click="sendMessage"
              :disabled="isSending || !newMessage.trim()">
              <i v-if="!isSending" class="fas fa-paper-plane"></i>
              <i v-else class="fas fa-spinner fa-spin"></i>
            </button>
          </div>
        </div>
      </div>

      <div v-else class="empty-chat-state">
        <i class="fas fa-comments"></i>
        <p>选择一个对话开始聊天</p>
      </div>
    </main>

    <!-- 新建私信对话对话框 -->
    <NewMessageDialog
      v-if="showNewMessageDialog"
      @close="showNewMessageDialog = false"
      @select="startNewConversation"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import NewMessageDialog from '@components/messages/NewMessageDialog/index.vue'

const searchQuery = ref('')
const showNewMessageDialog = ref(false)
const selectedUserId = ref(null)
const currentUserId = ref(null)

const conversations = ref([])
const messages = ref([])
const newMessage = ref('')
const isSending = ref(false)
const messagesListRef = ref(null)
const isLoadingMessages = ref(false)

// 过滤对话
const filteredConversations = computed(() => {
  if (!searchQuery.value) return conversations.value
  return conversations.value.filter(conv =>
    conv.username.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

// 选中的对话详情
const selectedConversation = computed(() => {
  return conversations.value.find(c => c.user_id === selectedUserId.value)
})

// 过滤对话
const filterConversations = () => {
  // 计算属性会自动过滤
}

// 选择对话
const selectConversation = (conv) => {
  selectedUserId.value = conv.user_id
  newMessage.value = ''
  loadMessages()
}

// 加载对话列表
const loadConversations = async () => {
  try {
    const response = await fetch('/api/messages/conversations/')
    if (response.ok) {
      const data = await response.json()
      conversations.value = data.conversations || []
    }
  } catch (error) {
    console.error('加载对话列表失败:', error)
  }
}

// 加载消息
const loadMessages = async () => {
  if (!selectedUserId.value) return

  isLoadingMessages.value = true
  try {
    const response = await fetch(`/api/messages/get/?user_id=${selectedUserId.value}`)
    if (response.ok) {
      const data = await response.json()
      messages.value = data.messages || []
      currentUserId.value = getUserId()
      // 滚动到底部
      await nextTick()
      scrollToBottom()
    }
  } catch (error) {
    console.error('加载消息失败:', error)
  } finally {
    isLoadingMessages.value = false
  }
}

// 发送消息
const sendMessage = async () => {
  if (!newMessage.value.trim() || !selectedUserId.value) return

  const content = newMessage.value.trim()
  isSending.value = true

  try {
    const response = await fetch('/api/messages/send/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({
        recipient_id: selectedUserId.value,
        content: content,
      })
    })

    if (response.ok) {
      const data = await response.json()
      messages.value.push(data.message)
      newMessage.value = ''
      await nextTick()
      scrollToBottom()
      // 刷新对话列表
      loadConversations()
    }
  } catch (error) {
    console.error('发送消息失败:', error)
  } finally {
    isSending.value = false
  }
}

// 开始新对话
const startNewConversation = (userId) => {
  selectedUserId.value = userId
  newMessage.value = ''
  showNewMessageDialog.value = false
  loadMessages()
  // 如果已有这个对话，刷新列表，否则等用户发送第一条消息
  loadConversations()
}

// 滚动到底部
const scrollToBottom = () => {
  if (messagesListRef.value) {
    messagesListRef.value.scrollTop = messagesListRef.value.scrollHeight
  }
}

// 格式化时间
const formatTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`

  return date.toLocaleDateString('zh-CN')
}

// 格式化消息时间
const formatMessageTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  return `${hours}:${minutes}`
}

// 截断消息
const truncateMessage = (msg) => {
  if (!msg) return '...'
  return msg.length > 50 ? msg.substring(0, 50) + '...' : msg
}

// 获取当前用户ID
const getUserId = () => {
  // 从窗口全局变量或隐藏的meta标签获取
  return window.currentUserId || parseInt(document.querySelector('meta[name="user-id"]')?.content || '0')
}

// 获取CSRF令牌
const getCsrfToken = () => {
  return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
         document.querySelector('[name=csrf]')?.value || ''
}

// 初始化
onMounted(() => {
  currentUserId.value = getUserId()
  loadConversations()
})
</script>

<style scoped>
.messages-container {
  display: grid;
  grid-template-columns: 320px 1fr;
  height: calc(100vh - 64px);
  background: white;
  gap: 1px;
}

/* ========== 左侧对话列表 ========== */
.conversations-sidebar {
  background: #f8f9fa;
  border-right: 1px solid #e9ecef;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e9ecef;
}

.sidebar-header h2 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.new-message-btn {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #409eff;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s;
}

.new-message-btn:hover {
  background: #e8f4ff;
}

.search-box {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  margin: 12px 12px 0;
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  gap: 8px;
}

.search-box i {
  color: #999;
}

.search-box input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 14px;
  background: none;
}

.conversations-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conversation-item {
  display: grid;
  grid-template-columns: 48px 1fr 24px;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  align-items: center;
}

.conversation-item:hover {
  background: #e8e8e8;
}

.conversation-item.active {
  background: #409eff;
  color: white;
}

.conv-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
}

.conv-info {
  min-width: 0;
}

.conv-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.conv-name {
  font-size: 14px;
  font-weight: 500;
  margin: 0;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-time {
  font-size: 12px;
  color: #999;
  white-space: nowrap;
}

.conversation-item.active .conv-time {
  color: rgba(255, 255, 255, 0.7);
}

.conv-message {
  font-size: 13px;
  color: #666;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conversation-item.active .conv-message {
  color: rgba(255, 255, 255, 0.8);
}

.unread-badge {
  width: 24px;
  height: 24px;
  background: #f56c6c;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}

.empty-state i {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.3;
}

/* ========== 右侧聊天区域 ========== */
.chat-area {
  display: flex;
  flex-direction: column;
  background: white;
  overflow: hidden;
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e9ecef;
}

.chat-user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
}

.chat-user-info h2 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.close-chat-btn {
  display: none;
}

@media (max-width: 768px) {
  .messages-container {
    grid-template-columns: 1fr;
  }

  .conversations-sidebar {
    display: none;
  }

  .close-chat-btn {
    display: flex;
    background: none;
    border: none;
    font-size: 20px;
    cursor: pointer;
    color: #666;
    width: 32px;
    height: 32px;
    align-items: center;
    justify-content: center;
  }
}

.messages-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.no-messages {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}

.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}

.message-item.own {
  justify-content: flex-end;
}

.message-item.own .message-avatar {
  order: 2;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.message-content {
  max-width: 60%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message-item.own .message-content {
  align-items: flex-end;
}

.message-text {
  padding: 10px 14px;
  border-radius: 8px;
  background: #f0f0f0;
  color: #333;
  word-break: break-word;
  line-height: 1.5;
}

.message-item.own .message-text {
  background: #409eff;
  color: white;
}

.message-time {
  font-size: 12px;
  color: #999;
}

.message-input-area {
  padding: 16px;
  border-top: 1px solid #e9ecef;
  background: white;
}

.message-input {
  width: 100%;
  min-height: 100px;
  max-height: 200px;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-family: inherit;
  font-size: 14px;
  resize: vertical;
  transition: all 0.2s;
}

.message-input:focus {
  outline: none;
  border-color: #409eff;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.1);
}

.input-actions {
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
  justify-content: center;
  gap: 8px;
  width: 40px;
  height: 40px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #66b1ff;
}

.send-btn:disabled {
  background: #d4d4d4;
  cursor: not-allowed;
}

.empty-chat-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}

.empty-chat-state i {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.3;
}
</style>
