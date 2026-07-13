<template>
  <div
    class="bubble-row"
    :class="{ own: msg.is_own, selectable: selectable, selected: selected }"
    :data-msg-id="msg.id"
    @click="toggleSelected"
  >
    <button
      v-if="selectable"
      class="message-select"
      type="button"
      :class="{ active: selected }"
      @click.stop="emitToggleSelected"
      :title="selected ? '取消选择' : '选择消息'"
    >
      <i class="fas" :class="selected ? 'fa-check-circle' : 'fa-circle'"></i>
    </button>
    <button
      class="message-sender-avatar"
      :class="{ own: msg.is_own }"
      type="button"
      :title="`${msg.is_own ? '我' : msg.sender || '成员'}的头像`"
      @click.stop="emitSenderAvatarClick"
    >
      <img
        v-if="msg.sender_avatar"
        :src="msg.sender_avatar"
        :alt="msg.sender || '成员头像'"
      />
      <span v-else>{{ senderInitial }}</span>
    </button>
    <div class="bubble-wrap">
      <div
        class="bubble"
        :class="{ own: msg.is_own, highlighted: highlighted, editing: isEditing, 'merged-container': mergedForward && !isEditing }"
        @contextmenu.prevent="emitContextMenu($event.clientX, $event.clientY)"
        @touchstart.passive="onTouchStart"
        @touchend="clearTouchHold"
        @touchcancel="clearTouchHold"
        @touchmove="onTouchMove"
      >
        <div v-if="isEditing" class="inline-edit-box" @click.stop>
          <textarea
            ref="editTextareaRef"
            v-model="localEditContent"
            class="inline-edit-textarea"
            :disabled="editSaving"
            rows="3"
            @keydown.esc.prevent="cancelInlineEdit"
            @keydown.ctrl.enter.prevent="confirmInlineEdit"
            @keydown.meta.enter.prevent="confirmInlineEdit"
            @input="autoResizeEditTextarea"
          ></textarea>
          <div class="inline-edit-footer">
            <span v-if="editError" class="inline-edit-error">{{ editError }}</span>
            <span v-else class="inline-edit-hint">Ctrl + Enter 保存</span>
            <span class="inline-edit-actions">
              <button
                type="button"
                class="inline-edit-action confirm"
                :disabled="editSaving"
                title="确认修改"
                @click.stop="confirmInlineEdit"
              >
                <i class="fas" :class="editSaving ? 'fa-spinner fa-spin' : 'fa-check'"></i>
              </button>
              <button
                type="button"
                class="inline-edit-action cancel"
                :disabled="editSaving"
                title="取消修改"
                @click.stop="cancelInlineEdit"
              >
                <i class="fas fa-xmark"></i>
              </button>
            </span>
          </div>
        </div>
        <button
          v-else-if="mergedForward"
          class="merged-forward-card"
          type="button"
          @click.stop="openMergedForward"
        >
          <span class="merged-forward-title">{{ mergedForward.title }}</span>
          <span class="merged-forward-lines">
            <span
              v-for="(line, index) in mergedForwardPreviewLines"
              :key="index"
              class="merged-forward-line"
            >
              {{ line }}
            </span>
          </span>
          <span class="merged-forward-footer">
            <i class="fas fa-list-ul"></i>
            聊天记录
          </span>
        </button>
        <button
          v-if="noteShare"
          class="note-share-card"
          type="button"
          :class="{ unavailable: !noteShare.is_available }"
          :disabled="!noteShare.is_available"
          @click.stop="openNoteShare"
        >
          <span class="note-share-icon"><i class="fas fa-sticky-note"></i></span>
          <span class="note-share-main">
            <span class="note-share-title">{{ noteShare.title || '未命名笔记' }}</span>
            <span class="note-share-meta">
              {{ noteShareVisibilityLabel(noteShare) }}
              <span v-if="noteShare.shared_by?.username"> · {{ noteShare.shared_by.username }}</span>
            </span>
          </span>
          <span class="note-share-action">
            <i class="fas" :class="noteShare.is_available ? 'fa-chevron-right' : 'fa-lock'"></i>
          </span>
        </button>
        <div v-else-if="renderedContent" ref="messageTextRef" class="message-text" v-html="renderedContent"></div>
        <div v-if="attachments.length" class="message-attachments">
          <div
            v-for="attachment in attachments"
            :key="attachment.id"
            class="message-attachment"
            :class="`type-${attachmentKind(attachment)}`"
          >
            <button
              v-if="isImageAttachment(attachment)"
              class="message-media-trigger"
              type="button"
              :title="attachment.name || '预览图片'"
              @click.prevent.stop="openMediaPreview(attachment)"
              @mousedown.stop
              @touchstart.stop
            >
              <img
                :src="attachment.url"
                :alt="attachment.name"
                class="message-image"
                loading="lazy"
              />
            </button>
            <audio
              v-else-if="attachmentKind(attachment) === 'audio'"
              :src="attachment.url"
              class="message-audio"
              controls
              preload="metadata"
            ></audio>
            <video
              v-else-if="attachmentKind(attachment) === 'video'"
              :src="attachment.url"
              class="message-video"
              controls
              preload="metadata"
            ></video>
            <template v-else>
              <a :href="attachment.url" :download="attachment.name" class="file-link">
                <i class="fas fa-file"></i>
                <span class="file-info">
                  <span class="file-name">{{ attachment.name }}</span>
                  <span class="file-size">{{ formatFileSize(attachment.size) }}</span>
                </span>
                <i class="fas fa-download"></i>
              </a>
            </template>
          </div>
        </div>
      </div>

      <!-- Phase 2: 表情回应区域 -->
      <div v-if="hasReactions" class="message-reactions">
        <button
          v-for="(reaction, emoji) in reactions"
          :key="emoji"
          class="reaction-item"
          :class="{ 'reacted-by-me': reaction.reacted_by_me }"
          type="button"
          @click.stop="toggleReaction(emoji)"
          :title="getReactionTooltip(reaction)"
        >
          <span class="reaction-emoji">{{ emoji }}</span>
          <span class="reaction-count">{{ reaction.count }}</span>
        </button>
        <button
          v-if="!selectable"
          class="reaction-add"
          type="button"
          @click.stop="showReactionPicker"
          title="添加表情"
        >
          <i class="fas fa-plus"></i>
        </button>
      </div>
      <div v-else-if="!selectable && showAddReactionButton" class="message-reactions-empty">
        <button
          class="reaction-add"
          type="button"
          @click.stop="showReactionPicker"
          title="添加表情"
        >
          <i class="far fa-smile"></i>
        </button>
      </div>

      <div class="bubble-meta">
        <span class="time">{{ formatTime(msg.created_at) }}</span>
        <span v-if="msg.is_edited" class="edited-state">已编辑</span>
        <span v-if="msg.is_own" class="read-state" :class="{ unread: !msg.is_read }">
          <i class="fas" :class="msg.is_read ? 'fa-check-double' : 'fa-check'"></i>
          <span>{{ msg.is_read ? '已读' : '未读' }}</span>
        </span>
      </div>
    </div>

    <div v-if="notePreview.visible" class="note-preview-overlay" @click.stop="closeNotePreview">
      <section class="note-preview-dialog" @click.stop>
        <header class="note-preview-header">
          <div class="note-preview-title-block">
            <span class="note-preview-icon">
              <i class="fas fa-file-lines"></i>
            </span>
            <div class="note-preview-title-text">
              <span class="note-preview-kicker">文章预览</span>
              <h3>{{ notePreview.title || '笔记' }}</h3>
              <p>{{ notePreview.meta }}</p>
            </div>
          </div>
          <button type="button" class="note-preview-close" title="关闭" @click="closeNotePreview">
            <i class="fas fa-times"></i>
          </button>
        </header>
        <div class="note-preview-body">
          <div v-if="notePreview.loading" class="note-preview-state">
            <i class="fas fa-spinner fa-spin"></i>
            <span>读取中...</span>
          </div>
          <div v-else-if="notePreview.error" class="note-preview-state error">
            <i class="fas fa-exclamation-circle"></i>
            <span>{{ notePreview.error }}</span>
          </div>
          <article v-else class="note-preview-content" v-html="notePreviewContent"></article>
        </div>
      </section>
    </div>

    <!-- Phase 2: 表情选择器弹窗 -->
    <div
      v-if="showEmojiPicker"
      class="emoji-picker-overlay"
      @click.stop="closeReactionPicker"
    >
      <div class="emoji-picker" @click.stop>
        <div class="emoji-picker-title">选择表情</div>
        <div class="emoji-picker-grid">
          <button
            v-for="emoji in commonEmojis"
            :key="emoji"
            class="emoji-picker-item"
            type="button"
            @click.stop="selectEmoji(emoji)"
          >
            {{ emoji }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, onUpdated, ref, watch } from 'vue'
import { enhanceCodeBlocks } from '@/composables/useCodeEnhancer'
import { formatHm } from '@utils/datetime'
import { hasUbbMarkup, hydrateUbbDom, renderCommentUbb } from '@/utils/ubb'
import { parseMergedForward } from '@/utils/mergedForward'
import { escapeHtml, sanitizeHtml } from '@utils/sanitize'

const props = defineProps({
  msg: { type: Object, required: true },
  highlight: { type: String, default: '' },
  selectable: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
  isEditing: { type: Boolean, default: false },
  editSaving: { type: Boolean, default: false },
})

const emit = defineEmits([
  'context-menu',
  'toggle-selected',
  'open-merged-forward',
  'reaction-toggle',
  'open-media-preview',
  'save-edit',
  'cancel-edit',
  'sender-avatar-click',
])

// Backend fields (recommended):
// msg.is_read: boolean read receipt flag; msg.read_at: optional ISO timestamp.
const LONG_PRESS_DELAY_MS = 450
const LONG_PRESS_MOVE_THRESHOLD_PX = 12
let touchHoldTimer = null
let touchStartPoint = null
const messageTextRef = ref(null)
const editTextareaRef = ref(null)
const localEditContent = ref(props.msg.content || '')
const editError = ref('')

// Phase 2: 表情回应相关状态
const showEmojiPicker = ref(false)
const showAddReactionButton = ref(false)

// 常用表情列表
const commonEmojis = [
  '👍', '👎', '❤️', '😂', '😮', '😢', '😡', '🎉',
  '🔥', '👏', '✅', '❌', '💯', '🙏', '💪', '👀',
]

const reactions = computed(() => props.msg.reactions || {})
const hasReactions = computed(() => Object.keys(reactions.value).length > 0)
const noteShare = computed(() => props.msg.note_share || null)
const senderInitial = computed(() => String(props.msg.sender || '?').trim().slice(0, 1).toUpperCase() || '?')

function noteShareVisibilityLabel(share, { currentGroup = false } = {}) {
  if (share?.requires_group_membership) {
    return currentGroup ? '仅当前群成员可见' : '仅群成员可见'
  }
  return share?.is_public ? '公开笔记' : '私有笔记'
}

function emitSenderAvatarClick() {
  emit('sender-avatar-click', props.msg)
}

const notePreview = ref({
  visible: false,
  loading: false,
  error: '',
  title: '',
  meta: '',
  content: '',
})
const notePreviewRequestId = ref(0)
const notePreviewContent = computed(() => sanitizeHtml(notePreview.value.content || '<p>暂无内容</p>'))

const highlighted = computed(
  () => {
    const query = String(props.highlight || '').trim().toLowerCase()
    return !!query && String(props.msg.content || '').toLowerCase().includes(query)
  }
)

const attachments = computed(() => Array.isArray(props.msg.attachments) ? props.msg.attachments : [])
const mergedForward = computed(() => parseMergedForward(props.msg.content))
const mergedForwardPreviewLines = computed(() => {
  if (!mergedForward.value) return []
  return mergedForward.value.items.slice(0, 3).map((item) => {
    const text = item.preview || item.content || attachmentSummary(item)
    return `${item.sender}: ${text || '[附件]'}`
  })
})

const renderedContent = computed(() => {
  if (mergedForward.value) return ''
  const rawContent = props.msg.content || ''
  let html = hasUbbMarkup(rawContent) ? renderCommentUbb(rawContent) : markdownToHtml(rawContent)
  if (props.highlight) {
    const safeQ = escapeHtml(props.highlight).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    html = html.replace(new RegExp(`(${safeQ})`, 'gi'), '<mark>$1</mark>')
  }
  return sanitizeHtml(html)
})

watch(
  () => props.isEditing,
  (isEditing) => {
    if (!isEditing) return
    localEditContent.value = props.msg.content || ''
    editError.value = ''
    nextTick(() => {
      autoResizeEditTextarea()
      editTextareaRef.value?.focus()
      editTextareaRef.value?.select()
    })
  },
  { immediate: true }
)

function hydrateMessageContent() {
  const container = messageTextRef.value
  if (!container) return
  hydrateUbbDom(container)
  enhanceCodeBlocks(container)
}

function autoResizeEditTextarea() {
  const textarea = editTextareaRef.value
  if (!textarea) return
  textarea.style.height = 'auto'
  textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 84), 260)}px`
}

function confirmInlineEdit() {
  if (props.editSaving) return
  const content = String(localEditContent.value || '').trim()
  if (!content) {
    editError.value = '消息内容不能为空'
    nextTick(autoResizeEditTextarea)
    return
  }
  if (content.length > 5000) {
    editError.value = '消息内容不能超过 5000 字'
    nextTick(autoResizeEditTextarea)
    return
  }
  editError.value = ''
  emit('save-edit', { msg: props.msg, content })
}

function cancelInlineEdit() {
  if (props.editSaving) return
  editError.value = ''
  localEditContent.value = props.msg.content || ''
  emit('cancel-edit', props.msg)
}

function markdownToHtml(rawText) {
  const text = String(rawText || '').replace(/\r\n/g, '\n')

  const codeBlocks = []
  const withPlaceholders = text.replace(/```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/g, (_, lang = '', code = '') => {
    const id = codeBlocks.length
    codeBlocks.push(
      `<pre class="msg-code-block"><code class="lang-${escapeAttr(lang)}">${escapeHtml(code)}</code></pre>`
    )
    return `@@CODE_BLOCK_${id}@@`
  })

  let html = escapeHtml(withPlaceholders)
    .replace(/`([^`\n]+)`/g, '<code class="msg-code-inline">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\n/g, '<br>')

  html = html.replace(/@@CODE_BLOCK_(\d+)@@/g, (_, idx) => codeBlocks[Number(idx)] || '')
  return html
}

function escapeAttr(s) {
  return String(s || '')
    .replace(/[^a-zA-Z0-9_-]/g, '')
}

function formatTime(iso) {
  return formatHm(iso)
}

function formatFileSize(size) {
  const bytes = Number(size) || 0
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function attachmentKind(attachment) {
  const type = String(attachment?.type || '').toLowerCase()
  if (['image', 'audio', 'video'].includes(type)) return type

  const mime = String(attachment?.mime_type || attachment?.content_type || '').toLowerCase()
  if (mime.startsWith('image/')) return 'image'
  if (mime.startsWith('audio/')) return 'audio'
  if (mime.startsWith('video/')) return 'video'

  const name = String(attachment?.name || attachment?.url || '').toLowerCase()
  if (/\.(png|jpe?g|gif|webp|bmp|avif|svg)(\?|#|$)/.test(name)) return 'image'
  if (/\.(mp3|wav|ogg|m4a|aac|flac)(\?|#|$)/.test(name)) return 'audio'
  if (/\.(mp4|webm|mov|m4v|avi|mkv)(\?|#|$)/.test(name)) return 'video'
  return type || 'file'
}

function isImageAttachment(attachment) {
  return attachmentKind(attachment) === 'image'
}

function attachmentSummary(item) {
  const itemAttachments = Array.isArray(item?.attachments) ? item.attachments : []
  if (!itemAttachments.length) return ''
  const first = itemAttachments[0]
  const kind = attachmentKind(first)
  if (kind === 'image') return '[图片]'
  if (kind === 'audio') return '[语音]'
  if (kind === 'video') return '[视频]'
  return `[文件] ${first?.name || '附件'}`
}

function emitContextMenu(x, y) {
  emit('context-menu', { msg: props.msg, x, y })
}

function emitToggleSelected() {
  emit('toggle-selected', props.msg)
}

function openMergedForward() {
  if (props.selectable) {
    emitToggleSelected()
    return
  }
  if (!mergedForward.value) return
  emit('open-merged-forward', { message: props.msg, payload: mergedForward.value })
}

async function openNoteShare() {
  if (props.selectable) {
    emitToggleSelected()
    return
  }
  const share = noteShare.value
  if (!share?.is_available || !share.access_url) return
  const requestId = ++notePreviewRequestId.value
  notePreview.value = {
    visible: true,
    loading: true,
    error: '',
    title: share.title || '笔记',
    meta: noteShareVisibilityLabel(share, { currentGroup: true }),
    content: '',
  }
  try {
    const response = await fetch(share.access_url, { cache: 'no-store' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.error || '无法读取该笔记')
    if (requestId !== notePreviewRequestId.value || !notePreview.value.visible) return
    const note = data.note || {}
    notePreview.value = {
      visible: true,
      loading: false,
      error: '',
      title: note.title || share.title || '笔记',
      meta: noteShareVisibilityLabel(data.share, { currentGroup: true }),
      content: note.content || '<p>暂无内容</p>',
    }
  } catch (error) {
    if (requestId !== notePreviewRequestId.value || !notePreview.value.visible) return
    notePreview.value = {
      ...notePreview.value,
      loading: false,
      error: error?.message || '无法读取该笔记',
    }
  }
}

function closeNotePreview() {
  notePreviewRequestId.value += 1
  notePreview.value.visible = false
}

function openMediaPreview(attachment) {
  if (props.selectable) {
    emitToggleSelected()
    return
  }
  emit('open-media-preview', {
    attachment: { ...attachment, type: attachmentKind(attachment) },
    message: props.msg,
  })
}

function toggleSelected() {
  if (!props.selectable) return
  emitToggleSelected()
}

function clearTouchHold() {
  if (touchHoldTimer) {
    clearTimeout(touchHoldTimer)
    touchHoldTimer = null
  }
  touchStartPoint = null
}

function onTouchStart(event) {
  const touch = event.touches?.[0]
  if (!touch) return
  clearTouchHold()
  const touchPoint = { x: touch.clientX, y: touch.clientY }
  touchStartPoint = touchPoint
  touchHoldTimer = setTimeout(() => {
    emitContextMenu(touchPoint.x, touchPoint.y)
    clearTouchHold()
  }, LONG_PRESS_DELAY_MS)
}

function onTouchMove(event) {
  const touch = event.touches?.[0]
  if (!touch || !touchStartPoint) return
  const movedX = Math.abs(touch.clientX - touchStartPoint.x)
  const movedY = Math.abs(touch.clientY - touchStartPoint.y)
  if (movedX > LONG_PRESS_MOVE_THRESHOLD_PX || movedY > LONG_PRESS_MOVE_THRESHOLD_PX) {
    clearTouchHold()
  }
}

// Phase 2: 表情回应方法
function toggleReaction(emoji) {
  emit('reaction-toggle', { msg: props.msg, emoji })
}

function showReactionPicker() {
  showEmojiPicker.value = true
}

function closeReactionPicker() {
  showEmojiPicker.value = false
}

function selectEmoji(emoji) {
  toggleReaction(emoji)
  closeReactionPicker()
}

function getReactionTooltip(reaction) {
  if (!reaction.users || reaction.users.length === 0) {
    return `${reaction.count} 人`
  }
  const usernames = reaction.users.map(u => u.username).join(', ')
  if (reaction.count > reaction.users.length) {
    return `${usernames} 和其他 ${reaction.count - reaction.users.length} 人`
  }
  return usernames
}

onBeforeUnmount(() => {
  clearTouchHold()
})

onMounted(() => {
  nextTick(hydrateMessageContent)
})

onUpdated(() => {
  nextTick(hydrateMessageContent)
})
</script>

<style scoped>
.bubble-row {
  display: flex;
  align-items: flex-end;
  justify-content: flex-start;
  gap: 10px;
}

.bubble-row.own {
  justify-content: flex-end;
}

.bubble-row.own .message-sender-avatar {
  order: 3;
}

.bubble-row.selectable {
  cursor: pointer;
}

.bubble-row.selected .bubble {
  box-shadow: 0 0 0 2px color-mix(in srgb, #60a5fa 55%, transparent);
}

.message-select {
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  border: none;
  background: transparent;
  color: #94a3b8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  cursor: pointer;
}

.message-select.active {
  color: #3b82f6;
}

.message-sender-avatar {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--border-color, #cbd5e1) 72%, transparent);
  border-radius: 50%;
  background: color-mix(in srgb, var(--bg-tertiary, #e5e7eb) 82%, transparent);
  color: var(--text-secondary, #475569);
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}

.message-sender-avatar:hover {
  border-color: color-mix(in srgb, var(--primary-color, #2563eb) 64%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary-color, #2563eb) 14%, transparent);
  transform: translateY(-1px);
}

.message-sender-avatar:focus-visible {
  outline: none;
  border-color: var(--primary-color, #2563eb);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary-color, #2563eb) 20%, transparent);
}

.message-sender-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.bubble-wrap {
  position: relative;
  max-width: min(72%, 720px);
  width: fit-content;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bubble-row.own .bubble-wrap {
  align-items: flex-end;
}

.bubble {
  padding: 10px 13px;
  border-radius: 16px;
  border-top-left-radius: 6px;
  background: color-mix(in srgb, var(--bg-tertiary, #e5e7eb) 75%, transparent);
  color: var(--text-primary);
  word-break: break-word;
  line-height: 1.56;
  border: 1px solid color-mix(in srgb, var(--border-color, #cbd5e1) 58%, transparent);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  -webkit-touch-callout: none;
  touch-action: manipulation;
  transition: background 180ms ease, border-color 180ms ease, box-shadow 180ms ease, padding 180ms ease;
}

.bubble.own {
  border-top-left-radius: 16px;
  border-top-right-radius: 6px;
  color: #fff;
  background: color-mix(in srgb, var(--primary-color, #2563eb) 86%, #60a5fa 14%);
  border-color: color-mix(in srgb, var(--primary-color, #2563eb) 66%, transparent);
}

.bubble.highlighted {
  outline: 1px solid color-mix(in srgb, var(--primary-color, #2563eb) 55%, #facc15 45%);
  outline-offset: 1px;
}

.bubble.merged-container {
  padding: 0;
  background: transparent;
  border: none;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.bubble.editing {
  width: min(520px, 70vw);
  padding: 9px;
  color: var(--text-primary, #0f172a);
  background: color-mix(in srgb, var(--bg-primary, #ffffff) 94%, transparent);
  border-color: color-mix(in srgb, var(--primary-color, #2563eb) 42%, var(--border-color, #cbd5e1));
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.12);
  animation: inline-edit-morph 180ms ease-out;
}

@keyframes inline-edit-morph {
  from {
    transform: scale(0.985);
    opacity: 0.88;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

.inline-edit-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.inline-edit-textarea {
  width: 100%;
  min-height: 84px;
  max-height: 260px;
  resize: none;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text-primary, #0f172a);
  font: inherit;
  line-height: 1.56;
  padding: 2px 4px;
  overflow-y: auto;
}

.inline-edit-textarea:disabled {
  opacity: 0.72;
}

.inline-edit-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 2px 0 0 4px;
}

.inline-edit-hint,
.inline-edit-error {
  min-width: 0;
  font-size: 11px;
  line-height: 1.2;
}

.inline-edit-hint {
  color: var(--text-tertiary, #64748b);
}

.inline-edit-error {
  color: #dc2626;
}

.inline-edit-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}

.inline-edit-action {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 12px;
  transition: transform 140ms ease, background 140ms ease, color 140ms ease, border-color 140ms ease;
}

.inline-edit-action:hover:not(:disabled) {
  transform: translateY(-1px);
}

.inline-edit-action:disabled {
  cursor: wait;
  opacity: 0.7;
}

.inline-edit-action.confirm {
  color: #047857;
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.28);
}

.inline-edit-action.confirm:hover:not(:disabled) {
  color: #fff;
  background: #059669;
}

.inline-edit-action.cancel {
  color: #b91c1c;
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.24);
}

.inline-edit-action.cancel:hover:not(:disabled) {
  color: #fff;
  background: #dc2626;
}

.bubble-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 9px;
  color: var(--text-tertiary);
  padding: 0 4px;
  opacity: 0.74;
  letter-spacing: 0.02em;
}

.read-state {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.edited-state {
  opacity: 0.86;
}

.read-state.unread {
  opacity: 0.85;
}

.bubble :deep(a) {
  color: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.message-text + .message-attachments {
  margin-top: 8px;
}

.merged-forward-card {
  width: min(320px, 72vw);
  border: none;
  border-radius: 8px;
  background: #f1f1f1;
  color: var(--text-primary, #0f172a);
  padding: 12px 14px 10px;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 9px;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.bubble.own .merged-forward-card {
  color: var(--text-primary, #0f172a);
  background: #f1f1f1;
}

.merged-forward-title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.35;
}

.merged-forward-lines {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-bottom: 8px;
  border-bottom: 1px solid color-mix(in srgb, var(--border-color, #dbe3ee) 80%, transparent);
}

.merged-forward-line {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.45;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.merged-forward-footer {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #9ca3af;
  font-size: 11px;
  line-height: 1;
}

.note-share-card {
  width: min(340px, 74vw);
  border: 1px solid color-mix(in srgb, var(--border-color, #dbe3ee) 74%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--bg-primary, #ffffff) 90%, #f8fafc 10%);
  color: var(--text-primary, #0f172a);
  padding: 12px;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  text-align: left;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
}

.note-share-card:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--primary-color, #2563eb) 45%, var(--border-color, #dbe3ee));
  background: color-mix(in srgb, var(--bg-primary, #ffffff) 84%, #eef6ff 16%);
}

.note-share-card.unavailable {
  opacity: 0.62;
  cursor: not-allowed;
}

.note-share-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.1);
}

.note-share-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.note-share-title {
  font-size: 14px;
  font-weight: 650;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.note-share-meta {
  color: var(--text-tertiary, #64748b);
  font-size: 12px;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.note-share-action {
  color: var(--text-tertiary, #64748b);
  font-size: 12px;
}

.note-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 3100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: clamp(18px, 4vw, 44px);
  background:
    radial-gradient(circle at 50% 28%, rgba(99, 102, 241, 0.16), transparent 36%),
    rgba(15, 23, 42, 0.46);
  backdrop-filter: blur(12px) saturate(1.05);
  -webkit-backdrop-filter: blur(12px) saturate(1.05);
}

.note-preview-dialog {
  width: min(860px, 94vw);
  max-height: min(820px, 88vh);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.94)),
    var(--bg-primary, #ffffff);
  color: var(--text-primary, #0f172a);
  border: 1px solid rgba(255, 255, 255, 0.78);
  box-shadow:
    0 30px 90px rgba(15, 23, 42, 0.34),
    0 1px 0 rgba(255, 255, 255, 0.72) inset;
  animation: note-preview-in 0.2s ease-out;
}

.note-preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding: 22px 24px 18px;
  background:
    linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(236, 72, 153, 0.08)),
    rgba(255, 255, 255, 0.62);
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

.note-preview-title-block {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 14px;
}

.note-preview-icon {
  flex: 0 0 auto;
  width: 42px;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  color: #4f46e5;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.16), rgba(14, 165, 233, 0.12));
  box-shadow: 0 10px 22px rgba(79, 70, 229, 0.14);
}

.note-preview-title-text {
  min-width: 0;
}

.note-preview-kicker {
  display: inline-flex;
  margin-bottom: 5px;
  color: #6366f1;
  font-size: 12px;
  font-weight: 700;
}

.note-preview-header h3 {
  margin: 0;
  max-width: 680px;
  font-size: 20px;
  font-weight: 750;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.note-preview-header p {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  max-width: 100%;
  margin: 8px 0 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.05);
  color: var(--text-tertiary, #64748b);
  font-size: 12px;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.note-preview-close {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--text-secondary, #475569);
  cursor: pointer;
  transition: transform 0.16s ease, background 0.16s ease, color 0.16s ease, box-shadow 0.16s ease;
}

.note-preview-close:hover {
  color: #ef4444;
  background: #ffffff;
  transform: translateY(-1px);
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.12);
}

.note-preview-body {
  min-height: 0;
  padding: 18px;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(241, 245, 249, 0.72), rgba(255, 255, 255, 0.82));
}

.note-preview-state {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-secondary, #475569);
}

.note-preview-state.error {
  color: #dc2626;
}

.note-preview-content {
  max-height: calc(min(820px, 88vh) - 116px);
  padding: clamp(22px, 4vw, 44px);
  overflow: auto;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.08);
  line-height: 1.78;
  word-break: break-word;
  overscroll-behavior: contain;
}

.note-preview-content::-webkit-scrollbar {
  width: 10px;
}

.note-preview-content::-webkit-scrollbar-thumb {
  border: 3px solid rgba(255, 255, 255, 0.92);
  border-radius: 999px;
  background: rgba(100, 116, 139, 0.42);
}

.note-preview-content::-webkit-scrollbar-track {
  background: transparent;
}

.note-preview-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 12px;
}

.note-preview-content :deep(h1),
.note-preview-content :deep(h2),
.note-preview-content :deep(h3) {
  color: var(--text-primary, #0f172a);
  line-height: 1.35;
}

.note-preview-content :deep(pre) {
  max-width: 100%;
  overflow: auto;
  border-radius: 12px;
}

@keyframes note-preview-in {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

[data-theme="dark"] .note-preview-dialog {
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.94)),
    var(--bg-primary, #0f172a);
  border-color: rgba(148, 163, 184, 0.24);
  box-shadow: 0 32px 96px rgba(0, 0, 0, 0.46);
}

[data-theme="dark"] .note-preview-header {
  background:
    linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(236, 72, 153, 0.1)),
    rgba(15, 23, 42, 0.82);
  border-bottom-color: rgba(148, 163, 184, 0.18);
}

[data-theme="dark"] .note-preview-body {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.82), rgba(2, 6, 23, 0.74));
}

[data-theme="dark"] .note-preview-content {
  border-color: rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.88);
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.24);
}

[data-theme="dark"] .note-preview-header p {
  background: rgba(148, 163, 184, 0.12);
}

[data-theme="dark"] .note-preview-close {
  background: rgba(15, 23, 42, 0.7);
  border-color: rgba(148, 163, 184, 0.24);
}

.message-attachments {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-attachment {
  color: inherit;
  text-decoration: none;
}

.message-attachment.type-image,
.message-attachment.type-video {
  display: block;
  max-width: min(340px, 64vw);
  overflow: hidden;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.08);
}

.message-media-trigger {
  display: block;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: zoom-in;
  color: inherit;
}

.message-image {
  display: block;
  width: 100%;
  max-height: 360px;
  object-fit: contain;
}

.message-video {
  display: block;
  width: 100%;
  max-height: 360px;
  background: #0f172a;
}

.message-audio {
  width: min(320px, 64vw);
  display: block;
}

.file-link {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  min-width: min(280px, 62vw);
  padding: 10px 12px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--bg-primary) 18%, transparent);
  border: 1px solid color-mix(in srgb, var(--border-color) 48%, transparent);
  color: inherit;
  text-decoration: none;
}

.file-info {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.file-size {
  font-size: 11px;
  opacity: 0.72;
}

.bubble :deep(mark) {
  background: rgba(250, 204, 21, 0.55);
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
}

.bubble :deep(.msg-code-inline) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 12px;
  padding: 1px 6px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--bg-secondary) 82%, transparent);
}

.bubble :deep(.msg-code-block) {
  margin: 8px 0;
  border-radius: 10px;
  padding: 9px 10px;
  overflow-x: auto;
  background: color-mix(in srgb, #0f172a 86%, #1e293b 14%);
  color: #e2e8f0;
}

.bubble :deep(.msg-code-block code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre;
}

.bubble :deep(.ubb-music-frame) {
  display: block;
  width: min(100%, 320px);
  border: none;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.08);
  margin-top: 8px;
}

.bubble :deep(.ubb-audio),
.bubble :deep(.ubb-video) {
  display: block;
  width: min(100%, 320px);
  margin-top: 8px;
}

.bubble :deep(pre.code-block-enhanced) {
  position: relative;
  margin: 8px 0;
  border-radius: 10px;
  padding: 34px 10px 10px;
  overflow-x: auto;
  background: color-mix(in srgb, #0f172a 86%, #1e293b 14%);
  color: #e2e8f0;
}

.bubble :deep(pre.line code .line-content) {
  display: block;
  white-space: pre-wrap;
}

.bubble :deep(pre.code-block-enhanced .copy-btn) {
  position: absolute;
  top: 6px;
  right: 6px;
  height: 28px;
  padding: 0 10px;
  border: none;
  border-radius: 6px;
  background: rgba(255,255,255,0.15);
  color: #cbd5e1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s ease;
  z-index: 10;
  font-size: 12px;
  line-height: 1;
}

.bubble :deep(pre.code-block-enhanced:hover .copy-btn) {
  opacity: 1;
}

.bubble :deep(pre.code-block-enhanced .copy-btn:hover) {
  background: rgba(255,255,255,0.25);
  color: white;
}

.bubble :deep(pre.code-block-enhanced .copy-btn.copied) {
  background: #10b981;
  color: white;
  opacity: 1;
}

.bubble :deep(pre.code-block-enhanced .copy-btn svg) {
  width: 14px;
  height: 14px;
  flex: 0 0 auto;
}

.bubble :deep(pre.code-block-enhanced .copy-btn span) {
  display: inline-block;
}

.bubble :deep(.ubb-countdown) {
  display: inline-flex;
  align-items: center;
  padding: 0.08rem 0.5rem;
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.18);
  color: inherit;
  font-size: 0.82em;
}

.bubble :deep(.ubb-chatlog) {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 240px;
  max-width: min(100%, 420px);
  padding: 12px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--bg-primary, #fff) 82%, transparent);
  border: 1px solid color-mix(in srgb, var(--border-color, #dbe3ee) 82%, transparent);
}

.bubble :deep(.ubb-chatlog-title) {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary, #0f172a);
}

.bubble :deep(.ubb-chatlog-body) {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-secondary, #475569);
}

/* Phase 2: 表情回应样式 */
.message-reactions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
  padding: 0 4px;
}

.message-reactions-empty {
  display: flex;
  opacity: 0;
  transition: opacity 0.2s ease;
  margin-top: 4px;
  padding: 0 4px;
}

.bubble-row:hover .message-reactions-empty {
  opacity: 1;
}

.reaction-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid color-mix(in srgb, var(--border-color, #cbd5e1) 68%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--bg-secondary, #f1f5f9) 45%, transparent);
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 14px;
  line-height: 1;
}

.reaction-item:hover {
  background: color-mix(in srgb, var(--bg-secondary, #f1f5f9) 75%, transparent);
  border-color: color-mix(in srgb, var(--border-color, #cbd5e1) 88%, transparent);
  transform: scale(1.05);
}

.reaction-item.reacted-by-me {
  background: color-mix(in srgb, var(--primary-color, #3b82f6) 15%, transparent);
  border-color: color-mix(in srgb, var(--primary-color, #3b82f6) 45%, transparent);
}

.reaction-item.reacted-by-me:hover {
  background: color-mix(in srgb, var(--primary-color, #3b82f6) 22%, transparent);
}

.reaction-emoji {
  font-size: 16px;
  line-height: 1;
}

.reaction-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.reaction-add {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--border-color, #cbd5e1) 58%, transparent);
  border-radius: 12px;
  background: transparent;
  color: var(--text-tertiary, #94a3b8);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 12px;
}

.reaction-add:hover {
  background: color-mix(in srgb, var(--bg-secondary, #f1f5f9) 65%, transparent);
  border-color: color-mix(in srgb, var(--border-color, #cbd5e1) 85%, transparent);
  color: var(--text-secondary);
}

.emoji-picker-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.emoji-picker {
  background: var(--bg-primary, #fff);
  border-radius: 16px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
  padding: 16px;
  max-width: min(90vw, 360px);
  max-height: min(80vh, 480px);
  overflow: auto;
}

.emoji-picker-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
}

.emoji-picker-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 8px;
}

.emoji-picker-item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  font-size: 22px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.emoji-picker-item:hover {
  background: color-mix(in srgb, var(--bg-secondary, #f1f5f9) 75%, transparent);
  border-color: var(--border-color, #e5e7eb);
  transform: scale(1.1);
}

@media (max-width: 768px) {
  .message-sender-avatar {
    width: 30px;
    height: 30px;
    flex-basis: 30px;
    font-size: 12px;
  }

  .bubble-wrap {
    max-width: 82%;
  }

  .note-preview-overlay {
    align-items: stretch;
    padding: 12px;
  }

  .note-preview-dialog {
    width: 100%;
    max-height: calc(100vh - 24px);
    border-radius: 16px;
  }

  .note-preview-header {
    padding: 16px;
    gap: 12px;
  }

  .note-preview-icon {
    width: 36px;
    height: 36px;
    border-radius: 12px;
  }

  .note-preview-header h3 {
    max-width: none;
    font-size: 17px;
  }

  .note-preview-body {
    padding: 12px;
  }

  .note-preview-content {
    max-height: calc(100vh - 128px);
    padding: 20px;
    border-radius: 14px;
  }

  .emoji-picker-grid {
    grid-template-columns: repeat(6, 1fr);
  }

  .emoji-picker-item {
    width: 36px;
    height: 36px;
    font-size: 20px;
  }
}
</style>

