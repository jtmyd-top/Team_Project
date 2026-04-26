<template>
  <div class="dialog-overlay" @click.self="closeDialog">
    <div class="dialog-content">
      <div class="dialog-header">
        <h3>开始新的对话</h3>
        <button class="close-btn" @click="closeDialog">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <!-- 精准搜索区 -->
      <div class="search-section">
        <div class="search-row">
          <input
            ref="inputRef"
            v-model="searchInput"
            type="text"
            placeholder="输入完整用户名 / 邮箱 / 8 位搜索码"
            class="search-input"
            autocomplete="off"
            @keydown.enter.prevent="doSearch"
            @input="searchError = ''">
          <button class="search-btn" :disabled="isSearching || !canSearch" @click="doSearch">
            <i :class="isSearching ? 'fas fa-spinner fa-spin' : 'fas fa-search'"></i>
            <span>{{ isSearching ? '搜索中' : '搜索' }}</span>
          </button>
        </div>
        <div class="search-hint">
          <i class="fas fa-shield-alt"></i>
          为防止用户枚举，仅支持精准匹配。对方须开启相应的可发现性，或你拥有对方分享的搜索码。
        </div>
      </div>

      <!-- 结果区 -->
      <div class="users-list">
        <template v-if="hasSearched">
          <div v-if="isSearching" class="loading">
            <i class="fas fa-spinner fa-spin"></i>
            搜索中...
          </div>

          <div v-else-if="searchResult" class="user-item" @click="selectUser(searchResult)">
            <img :src="searchResult.avatar" :alt="searchResult.username" class="user-avatar">
            <div class="user-details">
              <h4>
                {{ searchResult.username }}
                <span v-if="searchResult.matched_by" class="matched-by">
                  匹配：{{ matchedByLabel(searchResult.matched_by) }}
                </span>
              </h4>
              <p v-if="searchResult.bio">{{ searchResult.bio }}</p>
            </div>
            <i class="fas fa-chevron-right"></i>
          </div>

          <div v-else class="empty-search">
            <i class="fas fa-user-slash"></i>
            <p>未找到用户</p>
            <p class="neutral-hint">请确认输入的内容完全正确，或对方已允许被搜索</p>
          </div>
        </template>

        <template v-else>
          <div class="recent-title" v-if="recentUsers.length">最近联系人</div>
          <div
            v-for="user in recentUsers"
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

          <div v-if="!recentUsers.length" class="empty-search">
            <i class="fas fa-comment-dots"></i>
            <p>还没有对话，先用上方搜索框找到对方吧</p>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'

const emit = defineEmits(['close', 'select'])

const searchInput = ref('')
const isSearching = ref(false)
const hasSearched = ref(false)
const searchResult = ref(null)
const searchError = ref('')
const recentUsers = ref([])
const inputRef = ref(null)

const canSearch = computed(() => searchInput.value.trim().length >= 3)

const matchedByLabel = (via) => {
  if (via === 'username') return '用户名'
  if (via === 'email') return '邮箱'
  if (via === 'code') return '搜索码'
  return via
}

const closeDialog = () => {
  emit('close')
}

const doSearch = async () => {
  const q = searchInput.value.trim()
  if (q.length < 3) return
  isSearching.value = true
  hasSearched.value = true
  searchResult.value = null
  try {
    const response = await fetch(`/api/users/search/?q=${encodeURIComponent(q)}`)
    if (response.ok) {
      const data = await response.json()
      const users = data.users || []
      searchResult.value = users.length ? users[0] : null
    } else {
      searchResult.value = null
    }
  } catch (error) {
    console.error('搜索用户失败:', error)
    searchResult.value = null
  } finally {
    isSearching.value = false
  }
}

const selectUser = (user) => {
  emit('select', user.id)
}

const loadRecentUsers = async () => {
  try {
    const response = await fetch('/api/messages/conversations/')
    if (response.ok) {
      const data = await response.json()
      recentUsers.value = (data.conversations || []).slice(0, 5).map(conv => ({
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
  nextTick(() => inputRef.value?.focus())
})
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
  background: var(--bg-primary);
  border-radius: 12px;
  width: 90%;
  max-width: 440px;
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
  border-bottom: 1px solid var(--border-color);
}

.dialog-header h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

.close-btn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: var(--text-secondary);
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s;
}

.close-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.search-section {
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.search-row {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.search-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  background: var(--bg-secondary);
  color: var(--text-primary);
  transition: all 0.2s;
}

.search-input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary-color, #2563eb) 15%, transparent);
}

.search-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 14px;
  border: 1px solid var(--primary-color, #2563eb);
  background: var(--primary-color, #2563eb);
  color: #fff;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.search-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.search-btn:not(:disabled):hover {
  filter: brightness(1.08);
}

.search-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  display: flex;
  align-items: flex-start;
  gap: 6px;
  line-height: 1.5;
}

.search-hint i {
  color: var(--primary-color, #2563eb);
  margin-top: 2px;
}

.users-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.recent-title {
  font-size: 12px;
  color: var(--text-tertiary);
  padding: 6px 10px;
  margin-top: 4px;
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
  color: var(--text-primary);
}

.user-item:hover {
  background: var(--bg-tertiary);
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
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.matched-by {
  font-size: 11px;
  background: var(--bg-tertiary);
  color: var(--text-tertiary);
  padding: 2px 6px;
  border-radius: 999px;
  font-weight: 400;
}

.user-details p {
  font-size: 12px;
  color: var(--text-tertiary);
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
  color: var(--text-tertiary);
  gap: 10px;
  padding: 20px;
  text-align: center;
}

.empty-search p {
  margin: 0;
}

.empty-search .neutral-hint {
  font-size: 12px;
  opacity: 0.8;
}

.loading i {
  font-size: 24px;
}

.empty-search i {
  font-size: 48px;
  opacity: 0.3;
}
</style>
