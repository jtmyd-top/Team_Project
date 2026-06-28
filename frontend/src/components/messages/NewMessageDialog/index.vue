<template>
  <div class="dialog-overlay" @click.self="closeDialog">
    <div class="dialog-content">
      <div class="dialog-header">
        <h3>{{ dialogTitle }}</h3>
        <button class="close-btn" @click="closeDialog">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="mode-tabs">
        <button class="mode-tab" :class="{ active: mode === 'direct' }" @click="mode = 'direct'">
          <i class="fas fa-user"></i>
          私信
        </button>
        <button class="mode-tab" :class="{ active: mode === 'group' }" @click="mode = 'group'">
          <i class="fas fa-users"></i>
          群组
        </button>
      </div>

      <div v-if="mode === 'group' && !isForwardMode" class="group-policy">
        <template v-if="groupPolicy">
          <div class="policy-line" :class="{ ok: groupPolicy.eligible, blocked: !groupPolicy.eligible }">
            <i :class="groupPolicy.eligible ? 'fas fa-circle-check' : 'fas fa-circle-info'"></i>
            <span v-if="groupPolicy.enabled && groupPolicy.eligible">你已满足创建群组条件</span>
            <span v-else-if="groupPolicy.enabled">创建群组需同时满足以下条件</span>
            <span v-else>管理员已暂时关闭用户创建群组</span>
          </div>
          <div class="policy-progress">
            <span :class="{ ok: publicNotesRequirementMet, blocked: !publicNotesRequirementMet }">
              公开文章 {{ groupPolicy.stats.public_notes }}/{{ groupPolicy.min_public_notes }}
            </span>
            <span :class="{ ok: followersRequirementMet, blocked: !followersRequirementMet }">
              关注者 {{ groupPolicy.stats.followers }}/{{ groupPolicy.min_followers }}
            </span>
            <span :class="{ ok: ownedGroupRequirementMet, blocked: !ownedGroupRequirementMet }">
              已创建群聊 {{ groupPolicy.owned_group_count ?? 0 }}/{{ groupPolicy.max_owned_groups ?? 3 }}
            </span>
          </div>
        </template>
        <div v-else class="policy-line">
          <i class="fas fa-spinner fa-spin"></i>
          加载群组策略...
        </div>
      </div>

      <div v-if="mode === 'group' && !isForwardMode" class="group-name-row">
        <input
          v-model="groupName"
          type="text"
          class="search-input"
          placeholder="群组名称"
          maxlength="80"
        />
      </div>

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
            @input="searchError = ''"
          >
          <button class="search-btn" :disabled="isSearching || !canSearch" @click="doSearch">
            <i :class="isSearching ? 'fas fa-spinner fa-spin' : 'fas fa-search'"></i>
            <span>{{ isSearching ? '搜索中' : '搜索' }}</span>
          </button>
        </div>
        <div class="search-hint">
          <i class="fas fa-shield-alt"></i>
          {{ searchHintText }}
        </div>
      </div>

      <div class="users-list">
        <template v-if="hasSearched">
          <div v-if="isSearching" class="loading">
            <i class="fas fa-spinner fa-spin"></i>
            搜索中...
          </div>

          <div v-else-if="searchResult" class="user-item" @click="handleUserClick(searchResult)">
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
            <i :class="mode === 'group' && !isForwardMode ? 'fas fa-plus' : (isForwardMode ? 'fas fa-share' : 'fas fa-chevron-right')"></i>
          </div>

          <div v-else-if="searchError" class="empty-search">
            <i class="fas fa-triangle-exclamation"></i>
            <p>{{ searchError }}</p>
          </div>

          <div v-else class="empty-search">
            <i class="fas fa-user-slash"></i>
            <p>未找到用户</p>
            <p class="neutral-hint">{{ emptySearchHint }}</p>
          </div>
        </template>

        <template v-else-if="isForwardMode && mode === 'group'">
          <div v-if="recentGroups.length" class="recent-title">最近群组</div>
          <div
            v-for="group in recentGroups"
            :key="group.id"
            class="user-item"
            @click="selectGroup(group)"
          >
            <img :src="group.avatar" :alt="group.name" class="user-avatar">
            <div class="user-details">
              <h4>{{ group.name }}</h4>
              <p>{{ group.member_count ? `${group.member_count} 名成员` : '群组会话' }}</p>
            </div>
            <i class="fas fa-share"></i>
          </div>

          <div v-if="!recentGroups.length" class="empty-search">
            <i class="fas fa-users-slash"></i>
            <p>暂无可转发的群组</p>
            <p class="neutral-hint">你加入的群组会显示在这里</p>
          </div>
        </template>

        <template v-else>
          <div v-if="recentUsers.length" class="recent-title">{{ isForwardMode ? '最近私信' : '最近联系人' }}</div>
          <div
            v-for="user in recentUsers"
            :key="user.id"
            class="user-item"
            @click="handleUserClick(user)"
          >
            <img :src="user.avatar" :alt="user.username" class="user-avatar">
            <div class="user-details">
              <h4>{{ user.username }}</h4>
              <p v-if="user.bio">{{ user.bio }}</p>
            </div>
            <i :class="mode === 'group' && !isForwardMode ? 'fas fa-plus' : (isForwardMode ? 'fas fa-share' : 'fas fa-chevron-right')"></i>
          </div>

          <div v-if="!recentUsers.length" class="empty-search">
            <i class="fas fa-comment-dots"></i>
            <p>还没有对话，先用上方搜索框找到对方吧</p>
          </div>
        </template>
      </div>

      <div v-if="mode === 'group' && !isForwardMode" class="group-footer">
        <div class="selected-members">
          <span v-if="selectedMembers.length === 0" class="selected-empty">至少选择 1 名成员</span>
          <button
            v-for="member in selectedMembers"
            :key="member.id"
            class="member-chip"
            @click="removeMember(member.id)"
          >
            <span>{{ member.username }}</span>
            <i class="fas fa-times"></i>
          </button>
        </div>
        <button class="create-group-btn" :disabled="!canCreateGroup || creatingGroup" @click="createGroup">
          <i :class="creatingGroup ? 'fas fa-spinner fa-spin' : 'fas fa-users'"></i>
          <span>{{ creatingGroup ? '创建中' : '创建群组' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  purpose: {
    type: String,
    default: 'new',
  },
})
const emit = defineEmits(['close', 'select', 'group-created'])

const mode = ref('direct')
const searchInput = ref('')
const isSearching = ref(false)
const hasSearched = ref(false)
const searchResult = ref(null)
const searchError = ref('')
const recentUsers = ref([])
const recentGroups = ref([])
const inputRef = ref(null)
const groupPolicy = ref(null)
const groupName = ref('')
const selectedMembers = ref([])
const creatingGroup = ref(false)

const isForwardMode = computed(() => props.purpose === 'forward')
const dialogTitle = computed(() => {
  if (isForwardMode.value) return '选择转发对象'
  return mode.value === 'group' ? '创建群组' : '开始新的对话'
})
const searchHintText = computed(() => {
  if (isForwardMode.value && mode.value === 'group') return '可选择已有群组，或搜索用户后转发给私信对象。'
  return '为防止用户枚举，仅支持精准匹配。对方须开启相应的可发现性，或你拥有对方分享的搜索码。'
})
const emptySearchHint = computed(() => (
  isForwardMode.value ? '请确认输入的用户信息完全正确，或从最近列表中选择目标' : '请确认输入的内容完全正确，或对方已允许被搜索'
))
const canSearch = computed(() => searchInput.value.trim().length >= 3)
const canCreateGroup = computed(() =>
  !!groupPolicy.value?.enabled &&
  !!groupPolicy.value?.eligible &&
  groupName.value.trim().length > 0 &&
  selectedMembers.value.length > 0
)
const publicNotesRequirementMet = computed(() => {
  const policy = groupPolicy.value
  return policy?.reasons?.public_notes ?? ((policy?.stats?.public_notes ?? 0) >= (policy?.min_public_notes ?? 0))
})
const followersRequirementMet = computed(() => {
  const policy = groupPolicy.value
  return policy?.reasons?.followers ?? ((policy?.stats?.followers ?? 0) >= (policy?.min_followers ?? 0))
})
const ownedGroupRequirementMet = computed(() => {
  const policy = groupPolicy.value
  const ownedCount = Number(policy?.owned_group_count ?? 0)
  const maxOwnedGroups = Number(policy?.max_owned_groups ?? 3)
  if (Number.isFinite(ownedCount) && Number.isFinite(maxOwnedGroups)) {
    return ownedCount < maxOwnedGroups
  }
  return policy?.reasons?.owned_groups ?? true
})

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
  searchError.value = ''

  try {
    const response = await fetch(`/api/users/search/?q=${encodeURIComponent(q)}`)
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      searchError.value = data.error || data.message || '搜索失败，请稍后重试'
      return
    }

    const data = await response.json()
    const users = data.users || []
    searchResult.value = users.length ? users[0] : null
  } catch (error) {
    console.error('搜索用户失败:', error)
    searchError.value = '网络错误，请稍后重试'
  } finally {
    isSearching.value = false
  }
}

const selectUser = (user) => {
  emit('select', isForwardMode.value ? { type: 'user', id: user.id, user } : user.id)
}

const selectGroup = (group) => {
  emit('select', { type: 'group', id: group.id, group })
}

const handleUserClick = (user) => {
  if (mode.value === 'group' && !isForwardMode.value) {
    addMember(user)
    return
  }
  selectUser(user)
}

const addMember = (user) => {
  if (!user?.id || selectedMembers.value.some(member => member.id === user.id)) return
  selectedMembers.value = [...selectedMembers.value, user]
}

const removeMember = (userId) => {
  selectedMembers.value = selectedMembers.value.filter(member => member.id !== userId)
}

const loadGroupPolicy = async () => {
  try {
    const response = await fetch('/api/messages/groups/policy/')
    if (!response.ok) return
    const data = await response.json()
    groupPolicy.value = data.policy || null
  } catch (error) {
    console.error('加载群组策略失败:', error)
  }
}

const createGroup = async () => {
  if (!canCreateGroup.value) return
  creatingGroup.value = true
  try {
    const response = await fetch('/api/messages/groups/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken(),
      },
      body: JSON.stringify({
        name: groupName.value.trim(),
        member_ids: selectedMembers.value.map(member => member.id),
      }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      ElMessage.error(data.error || data.message || '创建群组失败')
      if (data.policy) groupPolicy.value = data.policy
      return
    }
    ElMessage.success('群组已创建')
    emit('group-created', data.group)
    emit('close')
  } catch (error) {
    ElMessage.error('网络错误，请重试')
  } finally {
    creatingGroup.value = false
  }
}

const getCSRFToken = () => {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

const loadRecentUsers = async () => {
  try {
    const response = await fetch('/api/messages/conversations/')
    if (response.ok) {
      const data = await response.json()
      const conversations = data.conversations || []
      recentUsers.value = (data.conversations || [])
        .filter(conv => conv.conversation_type !== 'group' && conv.user_id)
        .slice(0, 5)
        .map(conv => ({
          id: conv.user_id,
          username: conv.username,
          avatar: conv.avatar,
          bio: '',
        }))
      recentGroups.value = conversations
        .filter(conv => conv.conversation_type === 'group' && (conv.group_id || conv.id))
        .slice(0, 8)
        .map(conv => ({
          id: conv.group_id || conv.id,
          name: conv.group_name || conv.name || conv.username || '群组',
          avatar: conv.avatar,
          member_count: conv.member_count,
        }))
    }
  } catch (error) {
    console.error('加载最近联系人失败:', error)
  }
}

onMounted(() => {
  if (!isForwardMode.value) loadGroupPolicy()
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

.mode-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px 16px 0;
}

.mode-tab {
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  border-radius: 8px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
}

.mode-tab.active {
  border-color: var(--primary-color, #2563eb);
  color: var(--primary-color, #2563eb);
  background: color-mix(in srgb, var(--primary-color, #2563eb) 10%, transparent);
}

.group-policy {
  padding: 12px 16px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.policy-line {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: var(--text-secondary);
}

.policy-line.ok {
  color: #16a34a;
}

.policy-line.blocked {
  color: #d97706;
}

.policy-progress {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.policy-progress span {
  padding: 7px 9px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-tertiary);
  transition: background-color 0.2s, border-color 0.2s, color 0.2s;
}

.policy-progress span.ok {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #15803d;
}

.policy-progress span.blocked {
  border-color: #fecaca;
  background: #fef2f2;
  color: #dc2626;
  font-weight: 600;
}

.group-name-row {
  padding: 12px 16px 0;
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

.group-footer {
  border-top: 1px solid var(--border-color);
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.selected-members {
  min-height: 32px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.selected-empty {
  font-size: 12px;
  color: var(--text-tertiary);
}

.member-chip {
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--text-primary);
  border-radius: 999px;
  padding: 6px 9px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 12px;
}

.create-group-btn {
  height: 38px;
  border: none;
  border-radius: 8px;
  background: var(--primary-color, #2563eb);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}

.create-group-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
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
  margin: 0 0 4px;
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
