<template>
  <div class="messages-container" :class="{ 'mobile-chat-open': mobileChatOpen }">
    <!-- 左侧：对话列表 -->
    <aside class="conversations-sidebar">
      <div class="sidebar-header">
        <h2>私信</h2>
        <button class="new-message-btn" @click="openNewMessageDialog" title="新建私信">
          <i class="fas fa-pen-to-square"></i>
        </button>
      </div>

      <div class="search-box">
        <i class="fas fa-search"></i>
        <input
          v-model="globalSearch"
          type="text"
          placeholder="搜索用户或消息内容..."
          @input="onGlobalSearchInput"
        />
        <button v-if="globalSearch" class="clear-btn" @click="clearGlobalSearch">
          <i class="fas fa-times-circle"></i>
        </button>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button
          v-for="t in tabs"
          :key="t.value"
          class="tab"
          :class="{ active: scope === t.value }"
          @click="switchScope(t.value)"
        >
          <i :class="t.icon"></i>
          <span>{{ t.label }}</span>
          <span v-if="t.value === 'unread' && totalUnread > 0" class="tab-badge">
            {{ totalUnread > 99 ? '99+' : totalUnread }}
          </span>
        </button>
      </div>

      <!-- 搜索结果 -->
      <div v-if="globalSearchResults !== null" class="search-results">
        <div class="search-results-header">
          <span>搜索结果</span>
          <button class="small-link" @click="clearGlobalSearch">
            <i class="fas fa-arrow-left"></i> 返回
          </button>
        </div>
        <div v-if="globalSearchResults.length === 0" class="empty-state">
          <i class="fas fa-search-minus"></i>
          <p>未找到相关内容</p>
        </div>
        <div
          v-for="r in globalSearchResults"
          :key="r.id"
          class="result-row"
          @click="jumpToResult(r)"
        >
          <img :src="r.peer_avatar" :alt="r.peer_username" class="result-avatar" />
          <div class="result-info">
            <div class="result-top">
              <h4>{{ r.peer_username }}</h4>
              <span class="time">{{ formatShortTime(r.created_at) }}</span>
            </div>
            <p class="result-snippet">
              <span v-if="r.is_own">我：</span>
              <span v-html="highlightText(r.content, globalSearch)"></span>
            </p>
          </div>
        </div>
      </div>

      <!-- 已屏蔽面板 -->
      <BlockedUsersPanel
        v-else-if="scope === 'blocked'"
        ref="blockedPanelRef"
        :csrf-token="csrfToken"
        @updated="loadConversations"
      />

      <!-- 对话列表 -->
      <div v-else class="conversations-list">
        <div v-if="loadingConversations" class="empty-state">
          <i class="fas fa-spinner fa-spin"></i>
        </div>
        <div v-else-if="filteredConversations.length === 0" class="empty-state">
          <i :class="emptyStateIcon"></i>
          <p>{{ emptyStateText }}</p>
        </div>
        <ConversationItem
          v-for="conv in filteredConversations"
          :key="conv.user_id"
          :conv="conv"
          :active="selectedUserId === conv.user_id"
          :current-user-id="currentUserId"
          @select="selectConversation"
          @context-menu="onConversationContextMenu"
        />
      </div>
    </aside>

    <!-- 右侧：聊天区域 -->
    <main class="chat-area">
      <!-- 未选中会话 -->
      <div v-if="!selectedUserId || scope === 'blocked'" class="empty-chat-state">
        <i class="fas fa-comments"></i>
        <p v-if="scope === 'blocked'">屏蔽管理模式<br />在左侧管理你已屏蔽的用户</p>
        <p v-else>
          选择一个对话开始聊天
          <br />
          <span class="hint">或点击 <i class="fas fa-pen-to-square"></i> 发起新对话</span>
        </p>
      </div>

      <div v-else class="chat-container">
        <!-- 头部 -->
        <header class="chat-header">
          <button class="mobile-back-btn" @click="closeMobileChat" title="返回">
            <i class="fas fa-arrow-left"></i>
          </button>
          <div class="chat-user-info" @click="viewPeerProfile">
            <img :src="selectedConversation?.avatar" :alt="selectedConversation?.username" class="chat-avatar" />
            <div class="chat-user-meta">
              <h2>{{ selectedConversation?.username }}</h2>
              <span class="chat-subtitle secure-subtitle">
                <span class="presence-dot" :class="{ offline: !peerOnline }"></span>
                <span>{{ peerOnline ? '在线' : '离线' }}</span>
                <span class="secure-chip">
                  <i class="fas fa-lock"></i>
                  安全连接
                </span>
              </span>
            </div>
          </div>
          <div class="chat-actions">
            <button class="action-btn" @click="showChatSearch = true" title="在对话中搜索">
              <i class="fas fa-search"></i>
            </button>
            <div class="menu-wrap" @click.stop>
              <button class="action-btn" @click="showChatMenu = !showChatMenu" title="更多">
                <i class="fas fa-ellipsis-vertical"></i>
              </button>
              <div v-if="showChatMenu" class="dropdown-menu">
                <button class="dm-item" @click="viewPeerProfile">
                  <i class="fas fa-user-circle"></i> 查看资料
                </button>
                <button class="dm-item" @click="toggleMarkRead">
                  <i class="fas" :class="currentSettings.force_unread || hasUnread ? 'fa-check-double' : 'fa-envelope'"></i>
                  <span v-if="currentSettings.force_unread || hasUnread">标记为已读</span><span v-else>标记为未读</span>
                </button>
                <button class="dm-item" @click="togglePin">
                  <i class="fas fa-thumbtack" :class="{ active: currentSettings.is_pinned }"></i>
                  {{ currentSettings.is_pinned ? '取消置顶' : '置顶会话' }}
                </button>
                <button class="dm-item" @click="toggleMute">
                  <i class="fas" :class="currentSettings.is_muted ? 'fa-bell' : 'fa-bell-slash'"></i>
                  {{ currentSettings.is_muted ? '取消免打扰' : '消息免打扰' }}
                </button>
                <button class="dm-item" @click="openDisappearing">
                  <i class="fas fa-fire-alt"></i> 阅后即焚
                </button>
                <button class="dm-item" @click="toggleArchive">
                  <i class="fas" :class="currentSettings.is_archived ? 'fa-inbox' : 'fa-box-archive'"></i>
                  {{ currentSettings.is_archived ? '取消归档' : '归档会话' }}
                </button>
                <button class="dm-item" @click="exportChat">
                  <i class="fas fa-download"></i> 导出聊天记录
                </button>
                <div class="dm-sep"></div>
                <button class="dm-item danger" @click="clearConversation">
                  <i class="fas fa-eraser"></i> 清空聊天记录
                </button>
                <button class="dm-item danger" @click="blockPeer">
                  <i class="fas fa-ban"></i> 拉黑用户
                </button>
                <button class="dm-item danger" @click="reportPeer">
                  <i class="fas fa-flag"></i> 举报
                </button>
              </div>
            </div>
          </div>
        </header>

        <!-- 阅后即焚提示条 -->
        <div v-if="currentSettings.disappearing_enabled" class="disappearing-banner">
          <i class="fas fa-fire-alt"></i>
          已开启阅后即焚 · {{ formatTtl(currentSettings.disappearing_ttl_seconds) }}内消息将自动销毁        </div>

        <!-- 消息列表 -->
        <div class="messages-list" ref="messagesListRef">
          <div v-if="loadingMessages" class="messages-state">
            <i class="fas fa-spinner fa-spin"></i>
          </div>
          <div v-else-if="messages.length === 0" class="messages-state">
            <i class="fas fa-comment-dots"></i>
            <p>暂无对话历史</p>
            <p class="hint">发一条消息开始聊天吧</p>
          </div>

          <template v-else>
            <div class="message-stream">
              <div v-for="(group, i) in groupedMessages" :key="i" class="message-group">
                <div class="date-sep-wrap">
                  <div class="date-sep">{{ group.date }}</div>
                </div>
                <MessageBubble
                  v-for="m in group.messages"
                  :key="m.id"
                  :data-msg-id="m.id"
                  :msg="m"
                  :highlight="highlightMessageId === m.id ? globalSearch : ''"
                  @context-menu="onMessageContextMenu"
                />
              </div>
            </div>
          </template>
        </div>

        <!-- 输入区 -->
        <div v-if="peerBlockedByMe" class="blocked-tip">
          <i class="fas fa-ban"></i>
          你已屏蔽此用户。          <button class="link-btn" @click="unblockPeer">解除屏蔽</button>
        </div>
        <div v-else class="message-input-area">
          <div v-if="replyDraft" class="reply-draft-bar">
            <span class="reply-label">
              <i class="fas fa-reply"></i>
              {{ replyModeLabel }} {{ replyDraft.sender }}
            </span>
            <span class="reply-preview">{{ replyDraft.preview }}</span>
            <button class="reply-cancel-btn" @click="clearReplyDraft" title="取消引用">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="composer-row">
            <textarea
              v-model="newMessage"
              class="message-input"
              placeholder="输入消息... Enter 发送，Shift+Enter 换行"
              @keydown.enter="handleComposerEnter"
              @input="autoGrowComposer"
              maxlength="5000"
              ref="inputRef"
            ></textarea>
            <div class="composer-side">
              <span class="char-count" :class="{ warn: newMessage.length > 4500 }">
                {{ newMessage.length }}/5000
              </span>
              <button
                class="send-btn"
                @click="sendMessage()"
                :disabled="isSending || !newMessage.trim()"
              >
                <i v-if="!isSending" class="fas fa-paper-plane"></i>
                <i v-else class="fas fa-spinner fa-spin"></i>
                <span class="send-text">发送</span>
              </button>
            </div>
          </div>
          <span class="shortcut-hint">Enter 发送 / Shift+Enter 换行</span>
        </div>
      </div>
    </main>

    <!-- 对话项右键菜单 -->
    <div
      v-if="ctxMenu.visible"
      class="context-menu"
      :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
    >
      <button class="dm-item" @click="ctxAction('mark_read_toggle')">
        <i class="fas" :class="ctxMenu.conv?.unread_count > 0 || ctxMenu.conv?.force_unread ? 'fa-check-double' : 'fa-envelope'"></i>
        {{ ctxMenu.conv?.unread_count > 0 || ctxMenu.conv?.force_unread ? '标记为已读' : '标记为未读' }}
      </button>
      <button class="dm-item" @click="ctxAction('pin')">
        <i class="fas fa-thumbtack"></i>
        {{ ctxMenu.conv?.is_pinned ? '取消置顶' : '置顶会话' }}
      </button>
      <button class="dm-item" @click="ctxAction('mute')">
        <i class="fas" :class="ctxMenu.conv?.is_muted ? 'fa-bell' : 'fa-bell-slash'"></i>
        {{ ctxMenu.conv?.is_muted ? '取消免打扰' : '消息免打扰' }}
      </button>
      <button class="dm-item" @click="ctxAction('archive')">
        <i class="fas" :class="ctxMenu.conv?.is_archived ? 'fa-inbox' : 'fa-box-archive'"></i>
        {{ ctxMenu.conv?.is_archived ? '取消归档' : '归档会话' }}
      </button>
      <div class="dm-sep"></div>
      <button class="dm-item danger" @click="ctxAction('clear')">
        <i class="fas fa-eraser"></i> 清空记录
      </button>
      <button class="dm-item danger" @click="ctxAction('block')">
        <i class="fas fa-ban"></i> 拉黑用户
      </button>
    </div>

    <div
      v-if="messageCtxMenu.visible"
      class="context-menu"
      :style="{ left: messageCtxMenu.x + 'px', top: messageCtxMenu.y + 'px' }"
    >
      <button class="dm-item" @click="messageCtxAction('quote')">
        <i class="fas fa-quote-left"></i> 引用
      </button>
      <button class="dm-item" @click="messageCtxAction('forward')">
        <i class="fas fa-share"></i> 转发
      </button>
      <button class="dm-item" @click="messageCtxAction('copy')">
        <i class="fas fa-copy"></i> 复制
      </button>
      <button
        v-if="messageCtxMenu.msg?.is_own && canRecallMessage(messageCtxMenu.msg)"
        class="dm-item danger"
        @click="messageCtxAction('recall')"
      >
        <i class="fas fa-rotate-left"></i> 撤回
      </button>
    </div>

    <!-- 寮圭獥 -->
    <NewMessageDialog
      v-if="showNewMessageDialog"
      @close="closeNewMessageDialog"
      @select="startNewConversation"
    />

    <ChatSearchDrawer
      v-if="showChatSearch && selectedUserId"
      :peer-id="selectedUserId"
      @close="showChatSearch = false"
      @jump="jumpToMessage"
    />

    <ReportUserDialog
      v-if="reportTarget"
      :target-user-id="reportTarget.userId"
      :target-username="reportTarget.username"
      :message-id="reportTarget.messageId"
      :message-snippet="reportTarget.snippet"
      :csrf-token="csrfToken"
      @close="reportTarget = null"
      @submitted="reportTarget = null"
    />

    <DisappearingSettingDialog
      v-if="showDisappearingDialog && selectedUserId"
      :peer-id="selectedUserId"
      :initial-enabled="currentSettings.disappearing_enabled"
      :initial-ttl="currentSettings.disappearing_ttl_seconds"
      :csrf-token="csrfToken"
      @close="showDisappearingDialog = false"
      @saved="onDisappearingSaved"
    />

    <!-- Turnstile 兜底：当日新对话超额时要求人机验证 -->
    <div v-if="turnstileGate.visible" class="turnstile-gate-overlay" @click.self="cancelTurnstileGate">
      <div class="turnstile-gate-card">
        <h3><i class="fas fa-shield-alt"></i> 请完成人机验证</h3>
        <p class="turnstile-gate-desc">
          你今天主动发起的新对话数量已达上限（{{ turnstileGate.quotaLimit || 5 }} 个）。
          请完成下方验证后继续发送。
        </p>
        <div class="turnstile-gate-body">
          <Turnstile
            v-if="turnstileGate.siteKey"
            :site-key="turnstileGate.siteKey"
            @verified="onTurnstileVerified"
            @error="onTurnstileError"
            @expired="onTurnstileExpired"
          />
          <div v-else class="turnstile-gate-loading">
            <i class="fas fa-spinner fa-spin"></i>
            加载验证组件中...
          </div>
        </div>
        <div class="turnstile-gate-actions">
          <button class="btn-ghost" @click="cancelTurnstileGate">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import NewMessageDialog from '@components/messages/NewMessageDialog/index.vue'
import ConversationItem from '@components/messages/ConversationItem/index.vue'
import MessageBubble from '@components/messages/MessageBubble/index.vue'
import BlockedUsersPanel from '@components/messages/BlockedUsersPanel/index.vue'
import ChatSearchDrawer from '@components/messages/ChatSearchDrawer/index.vue'
import ReportUserDialog from '@components/messages/ReportUserDialog/index.vue'
import DisappearingSettingDialog from '@components/messages/DisappearingSettingDialog/index.vue'
import Turnstile from '@components/common/Turnstile/index.vue'

// ==== 甯搁噺 ====
const recallWindowSeconds = 120

// ==== 鐘舵€?====
const currentUserId = ref(0)
const csrfToken = ref('')
const scope = ref('all')
const conversations = ref([])
const loadingConversations = ref(false)
const selectedUserId = ref(null)
const messages = ref([])
const loadingMessages = ref(false)
const currentSettings = ref({
  is_pinned: false,
  is_muted: false,
  is_archived: false,
  disappearing_enabled: false,
  disappearing_ttl_seconds: 86400,
  force_unread: false,
})
const newMessage = ref('')
const isSending = ref(false)
const messagesListRef = ref(null)
const inputRef = ref(null)
const showNewMessageDialog = ref(false)
const showChatMenu = ref(false)
const showChatSearch = ref(false)
const showDisappearingDialog = ref(false)
const reportTarget = ref(null)
const ctxMenu = ref({ visible: false, x: 0, y: 0, conv: null })
const messageCtxMenu = ref({ visible: false, x: 0, y: 0, msg: null })
const globalSearch = ref('')
const globalSearchResults = ref(null)
const highlightMessageId = ref(null)
const mobileChatOpen = ref(false)
const blockedPanelRef = ref(null)
const replyDraft = ref(null)
const forwardDraft = ref(null)

// Turnstile 兜底：当日新对话超额
const turnstileGate = ref({
  visible: false,
  siteKey: '',
  pendingContent: '',
  pendingRecipientId: null,
  quotaLimit: 5,
})

const tabs = [
  { value: 'all', label: '全部', icon: 'fas fa-comments' },
  { value: 'unread', label: '未读', icon: 'fas fa-envelope' },
  { value: 'archived', label: '归档', icon: 'fas fa-box-archive' },
  { value: 'blocked', label: '屏蔽', icon: 'fas fa-ban' },
]

// ==== 璁＄畻灞炴€?====
const selectedConversation = computed(() =>
  conversations.value.find((c) => c.user_id === selectedUserId.value)
)
// 后端可选增强字段：
// 1) selectedConversation.peer_online: Boolean 对方在线状态（无该字段时前端默认展示在线）
// 2) message.reply_to_id / reply_preview: 若要持久化引用关系，后端需返回并保存这些字段
// 3) message.is_read / message.read_at: 渲染消息底部已读状态（双勾）与已读时间
const peerOnline = computed(() => selectedConversation.value?.peer_online ?? true)

const peerBlockedByMe = computed(() => !!selectedConversation.value?.is_blocked)

const totalUnread = computed(() =>
  conversations.value.reduce((s, c) => s + (c.unread_count || 0), 0)
)

const filteredConversations = computed(() => conversations.value)

const hasUnread = computed(
  () => (selectedConversation.value?.unread_count || 0) > 0
)

const replyModeLabel = computed(() => '引用')

const emptyStateIcon = computed(() => {
  if (scope.value === 'unread') return 'fas fa-envelope-open'
  if (scope.value === 'archived') return 'fas fa-box-archive'
  return 'fas fa-inbox'
})

const emptyStateText = computed(() => {
  if (scope.value === 'unread') return '没有未读消息'
  if (scope.value === 'archived') return '暂无归档会话'
  return '还没有私信'
})

const groupedMessages = computed(() => {
  const groups = []
  let lastDate = null
  for (const m of messages.value) {
    const d = new Date(m.created_at)
    const today = new Date()
    const dateKey = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
    let label
    const diff = Math.floor(
      (new Date(today.getFullYear(), today.getMonth(), today.getDate()) -
        new Date(d.getFullYear(), d.getMonth(), d.getDate())) /
        86400000
    )
    const timeText = `${String(d.getHours()).padStart(2, '0')}:${String(
      d.getMinutes()
    ).padStart(2, '0')}`
    if (diff === 0) label = `今天 ${timeText}`
    else if (diff === 1) label = `昨天 ${timeText}`
    else if (diff < 7) {
      const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
      label = `${weekdays[d.getDay()]} ${timeText}`
    } else label = `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()} ${timeText}`

    if (dateKey !== lastDate) {
      groups.push({ date: label, messages: [] })
      lastDate = dateKey
    }
    groups[groups.length - 1].messages.push(m)
  }
  return groups
})

// ==== 工具 ====
function getCsrfToken() {
  return (
    document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
    document.querySelector('[name=csrf]')?.value ||
    ''
  )
}

function getUserId() {
  return (
    window.currentUserId ||
    parseInt(document.querySelector('meta[name="user-id"]')?.content || '0')
  )
}

async function apiPost(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken.value,
    },
    body: JSON.stringify(body || {}),
  })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) {
    const err = new Error(d.error || '请求失败')
    err.status = r.status
    err.data = d
    throw err
  }
  return d
}

function syncConversations(nextConversations) {
  const existingByUserId = new Map(
    conversations.value.map((conversation) => [conversation.user_id, conversation])
  )
  const merged = nextConversations.map((nextConversation) => {
    const existing = existingByUserId.get(nextConversation.user_id)
    if (!existing) return nextConversation
    for (const key of Object.keys(existing)) {
      if (!(key in nextConversation)) delete existing[key]
    }
    Object.assign(existing, nextConversation)
    return existing
  })
  conversations.value = merged
}

// ==== 加载 ====
async function loadConversations() {
  if (scope.value === 'blocked') {
    blockedPanelRef.value?.reload?.()
    conversations.value = []
    return
  }
  loadingConversations.value = true
  try {
    const r = await fetch(`/api/messages/conversations/?scope=${scope.value}`)
    if (r.ok) {
      const d = await r.json()
      syncConversations(d.conversations || [])
    }
  } catch (e) {
    console.error(e)
  } finally {
    loadingConversations.value = false
  }
}

async function loadMessages() {
  if (!selectedUserId.value) return
  loadingMessages.value = true
  try {
    const r = await fetch(`/api/messages/get/?user_id=${selectedUserId.value}`)
    if (r.ok) {
      const d = await r.json()
      messages.value = d.messages || []
      if (d.settings) {
        currentSettings.value = { ...currentSettings.value, ...d.settings }
      }
      await nextTick()
      scrollToBottom()
    }
  } catch (e) {
    console.error(e)
  } finally {
    loadingMessages.value = false
  }
}

// ==== 选择与发送 ====
function selectConversation(conv) {
  if (conv.is_blocked) {
    // 在“屏蔽”Tab下点击仅展示提示
    ElMessage.info('此用户已被你屏蔽')
    return
  }
  selectedUserId.value = conv.user_id
  newMessage.value = ''
  replyDraft.value = null
  highlightMessageId.value = null
  showChatMenu.value = false
  closeMessageCtxMenu()
  mobileChatOpen.value = true
  loadMessages()
}

async function sendMessage(turnstileToken = '') {
  if (!newMessage.value.trim() || !selectedUserId.value) return
  isSending.value = true
  const normalizedTurnstileToken = typeof turnstileToken === 'string' ? turnstileToken : ''
  const finalContent = replyDraft.value
    ? buildQuotedMessage(replyDraft.value, newMessage.value.trim())
    : newMessage.value.trim()
  try {
    const payload = {
      recipient_id: selectedUserId.value,
      content: finalContent,
    }
    if (normalizedTurnstileToken) payload.turnstile_token = normalizedTurnstileToken
    const d = await apiPost('/api/messages/send/', payload)
    messages.value.push(d.message)
    newMessage.value = ''
    replyDraft.value = null
    resetComposerHeight()
    await nextTick()
    scrollToBottom()
    loadConversations()
  } catch (e) {
    if (e?.data?.need_turnstile) {
      await openTurnstileGate(finalContent, selectedUserId.value, e.data.quota_limit)
      return
    }
    ElMessage.error(e.message)
  } finally {
    isSending.value = false
  }
}

async function openTurnstileGate(pendingContent, recipientId, quotaLimit) {
  turnstileGate.value = {
    visible: true,
    siteKey: turnstileGate.value.siteKey || '',
    pendingContent,
    pendingRecipientId: recipientId,
    quotaLimit: quotaLimit || 5,
  }
  if (!turnstileGate.value.siteKey) {
    try {
      const r = await fetch('/api/turnstile/config/')
      if (r.ok) {
        const d = await r.json()
        turnstileGate.value.siteKey = d.site_key || d.siteKey || ''
      }
    } catch (err) {
      console.error('加载 Turnstile 配置失败:', err)
    }
  }
}

function cancelTurnstileGate() {
  turnstileGate.value.visible = false
  turnstileGate.value.pendingContent = ''
  turnstileGate.value.pendingRecipientId = null
  ElMessage.info('已取消人机验证，消息未发送')
}

async function onTurnstileVerified(token) {
  const pending = turnstileGate.value.pendingContent
  const pendingRecipient = turnstileGate.value.pendingRecipientId
  const normalizedTurnstileToken = typeof token === 'string' ? token : ''
  turnstileGate.value.visible = false
  if (!normalizedTurnstileToken || !pending || !pendingRecipient) return
  // 保持现有输入不动，直接用暂存内容 + token 重新投递
  isSending.value = true
  try {
    const d = await apiPost('/api/messages/send/', {
      recipient_id: pendingRecipient,
      content: pending,
      turnstile_token: normalizedTurnstileToken,
    })
    messages.value.push(d.message)
    newMessage.value = ''
    replyDraft.value = null
    resetComposerHeight()
    await nextTick()
    scrollToBottom()
    loadConversations()
  } catch (e) {
    ElMessage.error(e.message || '验证通过但发送失败，请稍后重试')
  } finally {
    isSending.value = false
    turnstileGate.value.pendingContent = ''
    turnstileGate.value.pendingRecipientId = null
  }
}

function onTurnstileError() {
  ElMessage.error('人机验证出错，请重试')
}

function onTurnstileExpired() {
  ElMessage.warning('验证已过期，请重新验证')
}

function createReplyDraft(m, mode = 'quote') {
  return {
    id: m.id,
    mode,
    sender: m.sender || '对方',
    preview: String(m.content || '').replace(/\s+/g, ' ').slice(0, 60),
  }
}

function buildQuotedMessage(draft, messageText) {
  return `> 引用 @${draft.sender}: ${draft.preview}\n\n${messageText}`
}

function buildForwardMessage(m) {
  const senderLabel = m?.is_own ? '我' : m?.sender || '对方'
  const timeLabel = formatForwardTime(m?.created_at)
  return `【转发自 ${senderLabel}${timeLabel ? ` ${timeLabel}` : ''}】\n${String(m?.content || '').trim()}`
}

function formatForwardTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function canRecallMessage(m) {
  if (!m?.is_own || !m?.created_at) return false
  const ts = new Date(m.created_at).getTime()
  return Number.isFinite(ts) && (Date.now() - ts) / 1000 < recallWindowSeconds
}

function clearReplyDraft() {
  replyDraft.value = null
}

function openNewMessageDialog() {
  forwardDraft.value = null
  showNewMessageDialog.value = true
}

function closeNewMessageDialog() {
  showNewMessageDialog.value = false
  forwardDraft.value = null
}

function onQuoteMessage(m) {
  replyDraft.value = createReplyDraft(m, 'quote')
  nextTick(() => inputRef.value?.focus())
}

async function copyMessageContent(m) {
  try {
    await navigator.clipboard.writeText(String(m?.content || ''))
    ElMessage.success('已复制消息内容')
  } catch (e) {
    ElMessage.error('复制失败，请检查浏览器权限')
  }
}

function onForwardMessage(m) {
  forwardDraft.value = {
    sourceMessageId: m.id,
    content: buildForwardMessage(m),
  }
  showNewMessageDialog.value = true
}

function handleComposerEnter(e) {
  if (e.shiftKey) return
  e.preventDefault()
  sendMessage()
}

function autoGrowComposer() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 180)}px`
}

function resetComposerHeight() {
  const el = inputRef.value
  if (!el) return
  el.style.height = ''
}

function startNewConversation(userId) {
  showNewMessageDialog.value = false
  scope.value = 'all'
  selectedUserId.value = userId
  newMessage.value = forwardDraft.value?.content || ''
  replyDraft.value = null
  forwardDraft.value = null
  mobileChatOpen.value = true
  loadMessages()
  loadConversations()
  nextTick(() => {
    inputRef.value?.focus()
    autoGrowComposer()
  })
}

// ==== 滚动 / 时间 ====
function scrollToBottom() {
  if (messagesListRef.value) {
    messagesListRef.value.scrollTop = messagesListRef.value.scrollHeight
  }
}

function formatShortTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function formatTtl(sec) {
  if (!sec || sec === 0) return '立即'
  if (sec < 3600) return `${sec / 60} 分钟`
  if (sec < 86400) return `${sec / 3600} 小时`
  if (sec < 604800) return `${sec / 86400} 天`
  return `${sec / 604800} 周`
}

function highlightText(text, q) {
  if (!text) return ''
  const safe = (text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  if (!q) return safe
  const safeQ = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return safe.replace(new RegExp(`(${safeQ})`, 'gi'), '<mark>$1</mark>')
}

// ==== Tab / 搜索 ====
function switchScope(s) {
  scope.value = s
  selectedUserId.value = null
  closeMessageCtxMenu()
  mobileChatOpen.value = false
  loadConversations()
}

let globalSearchTimer = null
function onGlobalSearchInput() {
  clearTimeout(globalSearchTimer)
  globalSearchTimer = setTimeout(runGlobalSearch, 260)
}

async function runGlobalSearch() {
  const q = globalSearch.value.trim()
  if (!q || q.length < 2) {
    globalSearchResults.value = null
    return
  }
  try {
    const r = await fetch(`/api/messages/search/?q=${encodeURIComponent(q)}`)
    if (r.ok) {
      const d = await r.json()
      globalSearchResults.value = d.results || []
    }
  } catch (e) {
    console.error(e)
  }
}

function clearGlobalSearch() {
  globalSearch.value = ''
  globalSearchResults.value = null
}

async function jumpToResult(r) {
  clearGlobalSearch()
  selectedUserId.value = r.peer_id
  highlightMessageId.value = r.id
  mobileChatOpen.value = true
  await loadMessages()
  scrollToMessage(r.id)
}

async function jumpToMessage(m) {
  showChatSearch.value = false
  highlightMessageId.value = m.id
  scrollToMessage(m.id)
  setTimeout(() => (highlightMessageId.value = null), 2500)
}

function scrollToMessage(messageId) {
  nextTick(() => {
    const el = document.querySelector(`.messages-list [data-msg-id="${messageId}"]`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    else scrollToBottom()
  })
}

// ==== 消息操作 ====
async function recallMessage(m) {
  try {
    await ElMessageBox.confirm('撤回后双方都将看不到此消息，确认撤回吗？', '撤回消息', {
      confirmButtonText: '撤回',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await apiPost(`/api/messages/${m.id}/delete/`, { scope: 'both' })
    messages.value = messages.value.filter((x) => x.id !== m.id)
    loadConversations()
    ElMessage.success('已撤回')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

// ==== 对话顶部菜单动作 ====
function viewPeerProfile() {
  if (!selectedUserId.value) return
  showChatMenu.value = false
  const url = `/api/users/${selectedUserId.value}/profile/`
  fetch(url)
    .then((r) => r.json())
    .then((d) => {
      if (d.status === 'success') {
        ElMessageBox.alert(
          `<div style="text-align:center;">
            <img src="${d.avatar}" style="width:64px;height:64px;border-radius:50%;margin-bottom:10px;"/>
            <h3 style="margin:0 0 6px;">${d.username}</h3>
            <p style="color:#888;margin:0 0 10px;">${d.bio || '暂无简介'}</p>
            <div style="display:flex;justify-content:space-around;gap:10px;">
              <span>📓 笔记 ${d.notes_count}</span>
              <span>👀 浏览 ${d.views_count}</span>
              <span>❤️ 点赞 ${d.likes_count}</span>
            </div>
          </div>`,
          '用户资料',
          { dangerouslyUseHTMLString: true, confirmButtonText: '关闭' }
        )
      } else {
        ElMessage.error(d.error || '加载失败')
      }
    })
    .catch(() => ElMessage.error('网络错误'))
}

async function toggleMarkRead() {
  showChatMenu.value = false
  const shouldMarkRead = hasUnread.value || currentSettings.value.force_unread
  try {
    const url = shouldMarkRead
      ? '/api/messages/conversation/mark-read/'
      : '/api/messages/conversation/mark-unread/'
    await apiPost(url, { user_id: selectedUserId.value })
    currentSettings.value.force_unread = !shouldMarkRead
    loadConversations()
    ElMessage.success(shouldMarkRead ? '已标记为已读' : '已标记为未读')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function togglePin() {
  showChatMenu.value = false
  const v = !currentSettings.value.is_pinned
  try {
    await apiPost('/api/messages/conversation/pin/', {
      user_id: selectedUserId.value,
      value: v,
    })
    currentSettings.value.is_pinned = v
    loadConversations()
    ElMessage.success(v ? '已置顶' : '已取消置顶')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function toggleMute() {
  showChatMenu.value = false
  const v = !currentSettings.value.is_muted
  try {
    await apiPost('/api/messages/conversation/mute/', {
      user_id: selectedUserId.value,
      value: v,
    })
    currentSettings.value.is_muted = v
    loadConversations()
    ElMessage.success(v ? '已开启免打扰' : '已关闭免打扰')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function toggleArchive() {
  showChatMenu.value = false
  const v = !currentSettings.value.is_archived
  try {
    await apiPost('/api/messages/conversation/archive/', {
      user_id: selectedUserId.value,
      value: v,
    })
    currentSettings.value.is_archived = v
    loadConversations()
    ElMessage.success(v ? '已归档' : '已取消归档')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function openDisappearing() {
  showChatMenu.value = false
  showDisappearingDialog.value = true
}

function onDisappearingSaved(d) {
  currentSettings.value.disappearing_enabled = d.enabled
  currentSettings.value.disappearing_ttl_seconds = d.ttl
}

function exportChat() {
  showChatMenu.value = false
  window.open(
    `/api/messages/conversation/export/?user_id=${selectedUserId.value}`,
    '_blank'
  )
}

async function clearConversation() {
  showChatMenu.value = false
  try {
    await ElMessageBox.confirm(
      '清空后你将看不到此对话的历史消息（对方仍可见），确认清空？',
      '清空聊天记录',
      { confirmButtonText: '清空', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await apiPost('/api/messages/conversation/clear/', {
      user_id: selectedUserId.value,
    })
    messages.value = []
    loadConversations()
    ElMessage.success('已清空')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function blockPeer() {
  showChatMenu.value = false
  try {
    await ElMessageBox.confirm(
      `拉黑后 ${selectedConversation.value?.username} 将无法向你发送私信，是否继续？`,
      '拉黑用户',
      { confirmButtonText: '拉黑', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await apiPost('/api/users/block/', { user_id: selectedUserId.value })
    ElMessage.success('已拉黑')
    selectedUserId.value = null
    mobileChatOpen.value = false
    loadConversations()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function unblockPeer() {
  try {
    await apiPost('/api/users/unblock/', { user_id: selectedUserId.value })
    ElMessage.success('已解除屏蔽')
    loadConversations()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function reportPeer() {
  showChatMenu.value = false
  reportTarget.value = {
    userId: selectedUserId.value,
    username: selectedConversation.value?.username || '',
    messageId: null,
    snippet: '',
  }
}

// ==== 对话项右键菜单 ====
function onConversationContextMenu({ conv, x, y }) {
  closeMessageCtxMenu()
  lastContextMenuOpenedAt = Date.now()
  const maxX = window.innerWidth - 220
  const maxY = window.innerHeight - 320
  ctxMenu.value = {
    visible: true,
    x: Math.min(x, maxX),
    y: Math.min(y, maxY),
    conv,
  }
}

function closeCtxMenu() {
  ctxMenu.value.visible = false
}

function onMessageContextMenu({ msg, x, y }) {
  closeCtxMenu()
  showChatMenu.value = false
  lastContextMenuOpenedAt = Date.now()
  const maxX = window.innerWidth - 220
  const maxY = window.innerHeight - 260
  messageCtxMenu.value = {
    visible: true,
    x: Math.min(x, maxX),
    y: Math.min(y, maxY),
    msg,
  }
}

function closeMessageCtxMenu() {
  messageCtxMenu.value.visible = false
}

async function messageCtxAction(action) {
  const msg = messageCtxMenu.value.msg
  closeMessageCtxMenu()
  if (!msg) return
  if (action === 'quote') {
    onQuoteMessage(msg)
    return
  }
  if (action === 'forward') {
    onForwardMessage(msg)
    return
  }
  if (action === 'copy') {
    await copyMessageContent(msg)
    return
  }
  if (action === 'recall') {
    await recallMessage(msg)
  }
}

async function ctxAction(action) {
  const conv = ctxMenu.value.conv
  closeCtxMenu()
  if (!conv) return
  try {
    if (action === 'pin') {
      await apiPost('/api/messages/conversation/pin/', {
        user_id: conv.user_id,
        value: !conv.is_pinned,
      })
    } else if (action === 'mute') {
      await apiPost('/api/messages/conversation/mute/', {
        user_id: conv.user_id,
        value: !conv.is_muted,
      })
    } else if (action === 'archive') {
      await apiPost('/api/messages/conversation/archive/', {
        user_id: conv.user_id,
        value: !conv.is_archived,
      })
    } else if (action === 'mark_read_toggle') {
      const url =
        conv.unread_count > 0 || conv.force_unread
          ? '/api/messages/conversation/mark-read/'
          : '/api/messages/conversation/mark-unread/'
      await apiPost(url, { user_id: conv.user_id })
    } else if (action === 'clear') {
      await ElMessageBox.confirm('清空与该用户的聊天记录？', '确认', {
        type: 'warning',
      })
      await apiPost('/api/messages/conversation/clear/', { user_id: conv.user_id })
      if (selectedUserId.value === conv.user_id) messages.value = []
    } else if (action === 'block') {
      await ElMessageBox.confirm(`拉黑 ${conv.username}？`, '确认', { type: 'warning' })
      await apiPost('/api/users/block/', { user_id: conv.user_id })
      if (selectedUserId.value === conv.user_id) selectedUserId.value = null
    }
    ElMessage.success('操作成功')
    loadConversations()
  } catch (e) {
    if (e && e.message) ElMessage.error(e.message)
  }
}

// ==== 全局点击关闭菜单 / 移动端 ====
function onGlobalClick() {
  if (Date.now() - lastContextMenuOpenedAt < 250) return
  closeCtxMenu()
  closeMessageCtxMenu()
  showChatMenu.value = false
}

function closeMobileChat() {
  mobileChatOpen.value = false
}

// ==== 轮询 ====
let pollTimer = null
let lastContextMenuOpenedAt = 0
function startPolling() {
  pollTimer = setInterval(() => {
    if (scope.value !== 'blocked') loadConversations()
  }, 15000)
}

// ==== 生命周期 ====
onMounted(() => {
  currentUserId.value = getUserId()
  csrfToken.value = getCsrfToken()
  loadConversations()
  startPolling()
  document.addEventListener('click', onGlobalClick)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
  document.removeEventListener('click', onGlobalClick)
})

watch(selectedUserId, (v) => {
  if (v) {
    nextTick(() => {
      inputRef.value?.focus()
      resetComposerHeight()
    })
  }
})

watch(
  () => messages.value.length,
  (len, prev) => {
    if (len > prev) nextTick(scrollToBottom)
  }
)
</script>

<style scoped>
.messages-container {
  display: grid;
  grid-template-columns: 340px 1fr;
  height: calc(100vh - 64px);
  background: var(--bg-primary);
  color: var(--text-primary);
  gap: 0;
  position: relative;
}

/* ========== 左侧对话列表 ========== */
.conversations-sidebar {
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-header h2 {
  font-size: 20px;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary);
}

.new-message-btn {
  background: var(--primary-color);
  color: #fff;
  border: none;
  font-size: 14px;
  cursor: pointer;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s;
}

.new-message-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--primary-color, #2563eb) 35%, transparent);
}

.search-box {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  margin: 12px 14px 0;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  gap: 8px;
}

.search-box:focus-within {
  border-color: var(--primary-color);
}

.search-box i {
  color: var(--text-tertiary);
}

.search-box input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 14px;
  background: none;
  color: var(--text-primary);
}

.search-box input::placeholder {
  color: var(--text-tertiary);
}

.clear-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-tertiary);
  font-size: 14px;
  padding: 0;
  display: flex;
}

.tabs {
  display: flex;
  padding: 10px 12px 0;
  gap: 4px;
  border-bottom: 1px solid var(--border-color);
}

.tab {
  flex: 1;
  padding: 8px 6px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 6px 6px 0 0;
  font-size: 12.5px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
  position: relative;
}

.tab i {
  font-size: 13px;
}

.tab:hover {
  color: var(--text-primary);
}

.tab.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  font-weight: 600;
}

.tab-badge {
  position: absolute;
  top: 4px;
  right: 8px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  background: var(--danger-color, #ef4444);
  color: #fff;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.conversations-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 8px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60%;
  color: var(--text-tertiary);
  gap: 10px;
}

.empty-state i {
  font-size: 44px;
  opacity: 0.3;
}

.empty-state p {
  margin: 0;
  font-size: 13px;
}

/* 搜索结果 */
.search-results {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px 8px;
}

.search-results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 10px 8px;
  font-size: 12.5px;
  color: var(--text-tertiary);
}

.small-link {
  background: none;
  border: none;
  color: var(--primary-color);
  cursor: pointer;
  font-size: 12.5px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.result-row {
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: 10px;
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.result-row:hover {
  background: var(--bg-tertiary);
}

.result-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
}

.result-info {
  min-width: 0;
}

.result-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
}

.result-top h4 {
  margin: 0;
  font-size: 13.5px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-top .time {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.result-snippet {
  margin: 2px 0 0;
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-snippet :deep(mark) {
  background: rgba(250, 204, 21, 0.6);
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
}

/* ========== 右侧聊天区域 ========== */
.chat-area {
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  overflow: hidden;
}

.empty-chat-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
  gap: 10px;
}

.empty-chat-state i {
  font-size: 70px;
  opacity: 0.25;
}

.empty-chat-state p {
  margin: 0;
  text-align: center;
  font-size: 14px;
  line-height: 1.8;
}

.empty-chat-state .hint {
  font-size: 12.5px;
  color: var(--text-tertiary);
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);
  min-height: 64px;
}

.mobile-back-btn {
  display: none;
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}

.chat-user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.chat-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.chat-user-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-user-meta h2 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-subtitle {
  font-size: 12px;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.chat-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.action-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.15s;
}

.action-btn:hover {
  background: var(--bg-secondary);
  color: var(--primary-color);
}

.menu-wrap {
  position: relative;
}

.dropdown-menu {
  position: absolute;
  right: 0;
  top: 100%;
  margin-top: 8px;
  width: 200px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.12);
  padding: 6px;
  z-index: 100;
}

.dm-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-primary);
  font-size: 13px;
  border-radius: 6px;
  text-align: left;
}

.dm-item i {
  width: 16px;
  color: var(--text-secondary);
}

.dm-item:hover {
  background: var(--bg-secondary);
}

.dm-item.danger {
  color: var(--danger-color, #ef4444);
}

.dm-item.danger i {
  color: var(--danger-color, #ef4444);
}

.dm-item i.active {
  color: var(--primary-color);
}

.dm-sep {
  height: 1px;
  background: var(--border-color);
  margin: 4px 0;
}

.disappearing-banner {
  padding: 8px 20px;
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
  font-size: 12.5px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--border-color);
}

.messages-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: var(--bg-secondary);
}

.messages-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
  gap: 8px;
}

.messages-state i {
  font-size: 40px;
  opacity: 0.3;
}

.messages-state p {
  margin: 0;
  font-size: 13.5px;
}

.messages-state .hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.date-sep {
  text-align: center;
  padding: 10px 0 14px;
  color: var(--text-tertiary);
  font-size: 11.5px;
  position: relative;
}

.date-sep::before,
.date-sep::after {
  content: '';
  display: inline-block;
  width: 60px;
  height: 1px;
  background: var(--border-color);
  vertical-align: middle;
  margin: 0 10px;
}

.date-sep-wrap {
  display: flex;
  justify-content: center;
}

.blocked-tip {
  padding: 20px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 13.5px;
}

.link-btn {
  background: none;
  border: none;
  color: var(--primary-color);
  cursor: pointer;
  font-size: 13.5px;
  padding: 0;
  text-decoration: underline;
}

.message-input-area {
  padding: 14px 20px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-primary);
}

.message-input {
  width: 100%;
  min-height: 72px;
  max-height: 180px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  background: var(--bg-secondary);
  color: var(--text-primary);
  transition: all 0.2s;
}

.message-input:focus {
  outline: none;
  border-color: var(--primary-color);
  background: var(--bg-primary);
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}

.char-count {
  font-size: 11.5px;
  color: var(--text-tertiary);
}

.char-count.warn {
  color: #f59e0b;
}

.shortcut-hint {
  font-size: 11.5px;
  color: var(--text-tertiary);
  align-self: flex-start;
  padding-left: 2px;
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: var(--primary-color);
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 14px color-mix(in srgb, var(--primary-color, #2563eb) 35%, transparent);
}

.send-btn:disabled {
  background: var(--border-color);
  color: var(--text-tertiary);
  cursor: not-allowed;
}

/* ========== 右键菜单 ========== */
.context-menu {
  position: fixed;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  padding: 6px;
  z-index: 1000;
  min-width: 200px;
}

/* ========== 右侧重构样式覆盖（毛玻璃 + 新交互） ========== */
.chat-container {
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--bg-primary) 92%, transparent),
    color-mix(in srgb, var(--bg-secondary) 88%, transparent)
  );
}

.chat-header {
  position: sticky;
  top: 0;
  z-index: 8;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  background: color-mix(in srgb, var(--bg-primary) 76%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--border-color) 70%, transparent);
}

.secure-subtitle {
  gap: 8px;
}

.presence-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 3px color-mix(in srgb, #22c55e 18%, transparent);
}

.presence-dot.offline {
  background: #94a3b8;
  box-shadow: none;
}

.secure-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--bg-secondary) 75%, transparent);
  border: 1px solid color-mix(in srgb, var(--border-color) 75%, transparent);
}

.messages-list {
  display: flex;
  flex-direction: column;
  padding: 14px 22px 10px;
}

.message-stream {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.date-sep {
  position: sticky;
  top: 6px;
  z-index: 2;
  font-size: 11px;
  color: var(--text-tertiary);
}

.date-sep::before,
.date-sep::after {
  width: 74px;
}

.message-input-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  background: color-mix(in srgb, var(--bg-primary) 78%, transparent);
}

.composer-row {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: flex-end;
  gap: 10px;
}

.composer-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: flex-end;
  gap: 8px;
}

.reply-draft-bar {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  padding: 8px 10px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--bg-secondary) 72%, transparent);
  border: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
}

.reply-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--primary-color);
  font-weight: 600;
}

.reply-preview {
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-secondary);
}

.reply-cancel-btn {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  width: 24px;
  height: 24px;
  border-radius: 50%;
}

.reply-cancel-btn:hover {
  background: color-mix(in srgb, var(--bg-tertiary) 85%, transparent);
  color: var(--text-primary);
}

.message-input {
  min-height: 52px;
  max-height: 180px;
  border-radius: 14px;
  padding: 12px 14px;
  height: 52px;
}

.send-btn {
  width: 88px;
  height: 44px;
  border-radius: 999px;
  gap: 6px;
}

.send-text {
  font-size: 13px;
  font-weight: 600;
}

/* ========== 鍝嶅簲寮?========== */
@media (max-width: 768px) {
  .messages-container {
    grid-template-columns: 1fr;
  }

  .chat-area {
    display: none;
  }

  .messages-container.mobile-chat-open .conversations-sidebar {
    display: none;
  }

  .messages-container.mobile-chat-open .chat-area {
    display: flex;
  }

  .mobile-back-btn {
    display: flex;
  }
}

/* ==== Turnstile 兜底弹窗 ==== */
.turnstile-gate-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.turnstile-gate-card {
  background: var(--bg-primary, #fff);
  color: var(--text-primary, #333);
  border-radius: 12px;
  padding: 24px;
  max-width: 400px;
  width: 92%;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25);
}

.turnstile-gate-card h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.turnstile-gate-desc {
  font-size: 13px;
  color: var(--text-secondary, #666);
  line-height: 1.6;
  margin: 0 0 16px 0;
}

.turnstile-gate-body {
  min-height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.turnstile-gate-loading {
  color: var(--text-tertiary, #999);
  font-size: 13px;
  display: inline-flex;
  gap: 8px;
  align-items: center;
}

.turnstile-gate-actions {
  display: flex;
  justify-content: flex-end;
}

.turnstile-gate-actions .btn-ghost {
  padding: 8px 16px;
  background: transparent;
  border: 1px solid var(--border-color, #d0d0d0);
  color: var(--text-primary, #333);
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.turnstile-gate-actions .btn-ghost:hover {
  background: var(--bg-tertiary, #f2f2f2);
}
</style>









