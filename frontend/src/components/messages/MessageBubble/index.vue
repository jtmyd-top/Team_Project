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
    <div class="bubble-wrap">
      <div
        class="bubble"
        :class="{ own: msg.is_own, highlighted: highlighted, 'merged-container': mergedForward }"
        @contextmenu.prevent="emitContextMenu($event.clientX, $event.clientY)"
        @touchstart.passive="onTouchStart"
        @touchend="clearTouchHold"
        @touchcancel="clearTouchHold"
        @touchmove="onTouchMove"
      >
        <button
          v-if="mergedForward"
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
        <div v-else-if="renderedContent" ref="messageTextRef" class="message-text" v-html="renderedContent"></div>
        <div v-if="attachments.length" class="message-attachments">
          <div
            v-for="attachment in attachments"
            :key="attachment.id"
            class="message-attachment"
            :class="`type-${attachment.type}`"
          >
            <a v-if="attachment.type === 'image'" :href="attachment.url" target="_blank">
              <img
                :src="attachment.url"
                :alt="attachment.name"
                class="message-image"
                loading="lazy"
              />
            </a>
            <audio
              v-else-if="attachment.type === 'audio'"
              :src="attachment.url"
              class="message-audio"
              controls
              preload="metadata"
            ></audio>
            <video
              v-else-if="attachment.type === 'video'"
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
import { computed, nextTick, onBeforeUnmount, onMounted, onUpdated, ref } from 'vue'
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
})

const emit = defineEmits(['context-menu', 'toggle-selected', 'open-merged-forward', 'reaction-toggle'])

// Backend fields (recommended):
// msg.is_read: boolean read receipt flag; msg.read_at: optional ISO timestamp.
const LONG_PRESS_DELAY_MS = 450
const LONG_PRESS_MOVE_THRESHOLD_PX = 12
let touchHoldTimer = null
let touchStartPoint = null
const messageTextRef = ref(null)

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

const highlighted = computed(
  () => !!props.highlight && !!props.msg.content && String(props.msg.content).includes(props.highlight)
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

function hydrateMessageContent() {
  const container = messageTextRef.value
  if (!container) return
  hydrateUbbDom(container)
  enhanceCodeBlocks(container)
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

function attachmentSummary(item) {
  const itemAttachments = Array.isArray(item?.attachments) ? item.attachments : []
  if (!itemAttachments.length) return ''
  const first = itemAttachments[0]
  if (first?.type === 'image') return '[图片]'
  if (first?.type === 'audio') return '[语音]'
  if (first?.type === 'video') return '[视频]'
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

.bubble-wrap {
  position: relative;
  max-width: min(72%, 720px);
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

.message-attachment.type-image a {
  display: block;
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
  .bubble-wrap {
    max-width: 82%;
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

