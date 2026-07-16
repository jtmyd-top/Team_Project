<template>
  <section class="knowledge-center">
    <header class="center-header">
      <div>
        <p class="center-kicker">消息提醒</p>
        <h2>通知中心</h2>
        <span>{{ unreadCount }} 条未读</span>
      </div>
      <div class="center-actions">
        <button
          v-for="item in filters"
          :key="item.value"
          class="segment-btn"
          :class="{ active: activeFilter === item.value }"
          @click="setFilter(item.value)"
        >
          {{ item.label }}
        </button>
        <button class="primary-action" :disabled="!unreadCount || loading" @click="markAllRead">
          全部已读
        </button>
      </div>
    </header>

    <div v-if="loading && !notifications.length" class="center-state">
      <i class="fas fa-spinner fa-spin"></i>
      <span>加载中...</span>
    </div>

    <div v-else-if="error && !notifications.length" class="center-state error">
      <i class="fas fa-circle-exclamation"></i>
      <span>{{ error }}</span>
      <button @click="fetchNotifications">重试</button>
    </div>

    <div v-else-if="notifications.length === 0" class="center-state">
      <i class="fas fa-bell-slash"></i>
      <span>{{ activeFilter === 'unread' ? '暂无未读通知' : '暂无通知' }}</span>
    </div>

    <div v-else class="center-list">
      <article
        v-for="item in notifications"
        :key="item.id"
        class="notice-row"
        :class="{ unread: !item.is_read }"
        @click="openNotification(item)"
      >
        <div class="notice-icon">
          <i :class="kindIcon(item.kind)"></i>
        </div>
        <div class="notice-body">
          <div class="notice-title-line">
            <h3>{{ item.title || '系统通知' }}</h3>
            <time>{{ formatMonthDayShortTime(item.created_at) }}</time>
          </div>
          <p>{{ item.body || '无更多内容' }}</p>
        </div>
        <button
          v-if="!item.is_read"
          class="ghost-action"
          @click.stop="markOneRead(item)"
        >
          标为已读
        </button>
      </article>
      <button
        v-if="pagination.has_next"
        class="load-more"
        :disabled="loadingMore"
        @click="loadMore"
      >
        <i v-if="loadingMore" class="fas fa-spinner fa-spin"></i>
        <span>{{ loadingMore ? '加载中...' : '加载更多' }}</span>
      </button>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { formatMonthDayShortTime } from '@/utils/datetime'
import { extractApiErrorMessage } from '@/utils/apiError'

const filters = [
  { label: '全部', value: 'all' },
  { label: '未读', value: 'unread' },
]

const notifications = ref([])
const unreadCount = ref(0)
const activeFilter = ref('all')
const loading = ref(false)
const loadingMore = ref(false)
const error = ref('')
const pagination = ref({
  page: 1,
  has_next: false,
})

function getCSRFToken() {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

async function fetchNotifications(options = {}) {
  const append = options?.append === true
  const targetPage = Number(options?.page || 1)
  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
    error.value = ''
  }
  try {
    const params = new URLSearchParams({ page_size: '40', page: String(targetPage) })
    if (activeFilter.value === 'unread') params.set('unread', '1')
    const response = await fetch(`/api/notifications/?${params.toString()}`)
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.status === 'error') {
      throw new Error(extractApiErrorMessage(data, '通知加载失败'))
    }
    const nextItems = data.notifications || []
    notifications.value = append ? [...notifications.value, ...nextItems] : nextItems
    unreadCount.value = data.unread_count || 0
    pagination.value = data.pagination || { page: targetPage, has_next: false }
  } catch (err) {
    error.value = err?.message || '通知加载失败'
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function setFilter(value) {
  if (activeFilter.value === value) return
  activeFilter.value = value
  fetchNotifications({ page: 1 })
}

function loadMore() {
  if (loading.value || loadingMore.value || !pagination.value.has_next) return
  fetchNotifications({ page: pagination.value.page + 1, append: true })
}

async function markRead(payload) {
  const response = await fetch('/api/notifications/mark-read/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCSRFToken(),
    },
    body: JSON.stringify(payload),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok || data.status === 'error') {
    throw new Error(extractApiErrorMessage(data, '操作失败'))
  }
  unreadCount.value = data.unread_count || 0
  return data
}

async function markAllRead() {
  try {
    await markRead({ all: true })
    notifications.value = notifications.value.map(item => ({ ...item, is_read: true }))
    if (activeFilter.value === 'unread') notifications.value = []
    ElMessage.success('已全部标为已读')
  } catch (err) {
    ElMessage.error(err?.message || '操作失败')
  }
}

async function markOneRead(item) {
  try {
    await markRead({ notification_ids: [item.id] })
    item.is_read = true
    if (activeFilter.value === 'unread') {
      notifications.value = notifications.value.filter(notification => notification.id !== item.id)
    }
  } catch (err) {
    ElMessage.error(err?.message || '操作失败')
  }
}

async function openNotification(item) {
  if (!item.is_read) {
    await markOneRead(item)
  }
  const data = item.data || {}
  if (data.url) {
    window.location.href = data.url
  } else if (data.note_id) {
    window.location.href = `/knowledge/?note=${data.note_id}`
  } else if (data.group_id || data.message_id || item.kind === 'new_message') {
    window.location.href = '/messages/'
  }
}

function kindIcon(kind) {
  const map = {
    message: 'fas fa-message',
    new_message: 'fas fa-message',
    comment: 'fas fa-comment-dots',
    report: 'fas fa-shield-halved',
    sanction: 'fas fa-ban',
    note_copied: 'fas fa-copy',
    note_revision_restored: 'fas fa-clock-rotate-left',
    profile: 'fas fa-user',
  }
  return map[kind] || 'fas fa-bell'
}

onMounted(fetchNotifications)
</script>

<style scoped>
.knowledge-center {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 28px;
  background: #f8fafc;
  overflow: hidden;
}

.center-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid #e5e7eb;
}

.center-kicker {
  margin: 0 0 6px;
  color: #64748b;
  font-size: 13px;
}

.center-header h2 {
  margin: 0 0 8px;
  color: #0f172a;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 0;
}

.center-header span {
  color: #64748b;
  font-size: 14px;
}

.center-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.segment-btn,
.primary-action,
.ghost-action,
.center-state button {
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  cursor: pointer;
  font-size: 14px;
  height: 34px;
  padding: 0 12px;
}

.segment-btn.active,
.primary-action {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.primary-action:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.center-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 18px 0 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notice-row {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}

.notice-row.unread {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.notice-icon {
  width: 42px;
  height: 42px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: #2563eb;
  background: #dbeafe;
}

.notice-body {
  min-width: 0;
}

.notice-title-line {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: baseline;
}

.notice-title-line h3 {
  margin: 0;
  font-size: 15px;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notice-title-line time {
  flex: 0 0 auto;
  color: #94a3b8;
  font-size: 12px;
}

.notice-body p {
  margin: 6px 0 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.5;
}

.ghost-action {
  color: #2563eb;
}

.load-more {
  align-self: center;
  min-height: 36px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  color: #2563eb;
  cursor: pointer;
  font-size: 14px;
  padding: 0 18px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.load-more:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.center-state {
  flex: 1;
  display: grid;
  place-content: center;
  gap: 12px;
  color: #64748b;
  text-align: center;
}

.center-state i {
  font-size: 28px;
}

.center-state.error {
  color: #dc2626;
}

@media (max-width: 720px) {
  .knowledge-center {
    padding: 18px;
  }

  .center-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .notice-row {
    grid-template-columns: 36px minmax(0, 1fr);
  }

  .ghost-action {
    grid-column: 2;
    justify-self: start;
  }
}
</style>
