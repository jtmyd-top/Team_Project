<template>
  <div class="bubble-row" :class="{ own: msg.is_own }" :data-msg-id="msg.id">
    <div class="bubble-wrap">
      <div
        class="bubble"
        :class="{ own: msg.is_own, highlighted: highlighted }"
        @contextmenu.prevent="emitContextMenu($event.clientX, $event.clientY)"
        @touchstart.passive="onTouchStart"
        @touchend="clearTouchHold"
        @touchcancel="clearTouchHold"
        @touchmove="onTouchMove"
      >
        <div v-if="renderedContent" ref="messageTextRef" class="message-text" v-html="renderedContent"></div>
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

      <div class="bubble-meta">
        <span class="time">{{ formatTime(msg.created_at) }}</span>
        <span v-if="msg.is_own" class="read-state" :class="{ unread: !msg.is_read }">
          <i class="fas" :class="msg.is_read ? 'fa-check-double' : 'fa-check'"></i>
          <span>{{ msg.is_read ? '已读' : '未读' }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, onUpdated, ref } from 'vue'
import { enhanceCodeBlocks } from '@/composables/useCodeEnhancer'
import { hasUbbMarkup, hydrateUbbDom, renderCommentUbb } from '@/utils/ubb'

const props = defineProps({
  msg: { type: Object, required: true },
  highlight: { type: String, default: '' },
})

const emit = defineEmits(['context-menu'])

// Backend fields (recommended):
// msg.is_read: boolean read receipt flag; msg.read_at: optional ISO timestamp.
const LONG_PRESS_DELAY_MS = 450
const LONG_PRESS_MOVE_THRESHOLD_PX = 12
let touchHoldTimer = null
let touchStartPoint = null
const messageTextRef = ref(null)

const highlighted = computed(
  () => !!props.highlight && !!props.msg.content && String(props.msg.content).includes(props.highlight)
)

const attachments = computed(() => Array.isArray(props.msg.attachments) ? props.msg.attachments : [])

const renderedContent = computed(() => {
  const rawContent = props.msg.content || ''
  let html = hasUbbMarkup(rawContent) ? renderCommentUbb(rawContent) : markdownToHtml(rawContent)
  if (props.highlight) {
    const safeQ = escapeHtml(props.highlight).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    html = html.replace(new RegExp(`(${safeQ})`, 'gi'), '<mark>$1</mark>')
  }
  return html
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

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function escapeAttr(s) {
  return String(s || '')
    .replace(/[^a-zA-Z0-9_-]/g, '')
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function formatFileSize(size) {
  const bytes = Number(size) || 0
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function emitContextMenu(x, y) {
  emit('context-menu', { msg: props.msg, x, y })
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
}

.bubble-row.own {
  justify-content: flex-end;
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

@media (max-width: 768px) {
  .bubble-wrap {
    max-width: 82%;
  }
}
</style>

