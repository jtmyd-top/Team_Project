<template>
  <div class="dialog-overlay" @click.self="closeDialog">
    <div class="dialog-content">
      <div class="dialog-header">
        <h3>开始新的对话</h3>
        <button class="close-btn" @click="closeDialog">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <!-- 搜索用户 -->
      <div class="search-section">
        <input
          v-model="searchInput"
          type="text"
          placeholder="搜索用户..."
          class="search-input"
          @input="searchUsers">
        <i class="fas fa-search"></i>
      </div>

      <!-- 搜索结果或最近联系人 -->
      <div class="users-list">
        <div v-if="isSearching" class="loading">
          <i class="fas fa-spinner fa-spin"></i>
          搜索中...
        </div>

        <div v-else-if="displayUsers.length === 0" class="empty-search">
          <i class="fas fa-user-slash"></i>
          <p>未找到用户</p>
        </div>

        <div
          v-for="user in displayUsers"
          :key="user.id"
          class="user-item"
          @click="selectUser(user)">
          <img :src="user.avatar" :alt="user.username" class="user-avatar">
          <div class="user-details">
            <h4>{{ user.username }}</h4>
            <p v-if="user.bio">{{ user.bio }}</p>
          </div>
          <i class="fas fa-chevron-right"></i>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const emit = defineEmits(['close', 'select'])

const searchInput = ref('')
const isSearching = ref(false)
const users = ref([])
const recentUsers = ref([])

// 显示的用户列表
const displayUsers = computed(() => {
  if (searchInput.value.trim()) {
    return users.value
  }
  return recentUsers.value
})

// 关闭对话框
const closeDialog = () => {
  emit('close')
}

// 搜索用户
const searchUsers = async () => {
  if (!searchInput.value.trim()) {
    users.value = []
    return
  }

  isSearching.value = true
  try {
    // TODO: 实现搜索用户API
    // 目前直接调用一个获取所有用户的端点或通过现有API
    const response = await fetch(`/api/users/search/?q=${encodeURIComponent(searchInput.value)}`)
    if (response.ok) {
      const data = await response.json()
      users.value = data.users || []
    }
  } catch (error) {
    console.error('搜索用户失败:', error)
  } finally {
    isSearching.value = false
  }
}

// 选择用户
const selectUser = (user) => {
  emit('select', user.id)
}

// 初始化：加载最近联系人
const loadRecentUsers = async () => {
  try {
    const response = await fetch('/api/messages/conversations/')
    if (response.ok) {
      const data = await response.json()
      // 转换对话列表为用户列表
      recentUsers.value = data.conversations.slice(0, 5).map(conv => ({
        id: conv.user_id,
        username: conv.username,
        avatar: conv.avatar,
        bio: '',
      }))
    }
  } catch (error) {
    console.error('加载最近联系人失败:', error)
  }
}

onMounted(() => {
  loadRecentUsers()
})

import { onMounted } from 'vue'
</script>

<style scoped>
.dialog-overlay {
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

.dialog-content {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 400px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
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

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e9ecef;
}

.dialog-header h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 20px;
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
}

.search-section {
  padding: 16px;
  border-bottom: 1px solid #e9ecef;
  position: relative;
}

.search-input {
  width: 100%;
  padding: 10px 16px;
  padding-left: 36px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: all 0.2s;
}

.search-input:focus {
  border-color: #409eff;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.1);
}

.search-section i {
  position: absolute;
  left: 28px;
  top: 50%;
  transform: translateY(-50%);
  color: #999;
  font-size: 14px;
}

.users-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.user-item {
  display: grid;
  grid-template-columns: 48px 1fr 24px;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  align-items: center;
}

.user-item:hover {
  background: #f5f5f5;
}

.user-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
}

.user-details {
  min-width: 0;
}

.user-details h4 {
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 4px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-details p {
  font-size: 12px;
  color: #999;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.loading,
.empty-search {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
  gap: 12px;
}

.loading i {
  font-size: 24px;
}

.empty-search i {
  font-size: 48px;
  opacity: 0.3;
}
</style>
