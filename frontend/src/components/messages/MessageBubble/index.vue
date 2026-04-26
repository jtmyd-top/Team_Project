<template>
  <div class="bubble-row" :class="{ own: msg.is_own }" :data-msg-id="msg.id">
    <div class="bubble-wrap">
      <div
        class="bubble"
        :class="{ own: msg.is_own, highlighted: highlighted }"
        v-html="renderedContent"
        @contextmenu.prevent="emitContextMenu($event.clientX, $event.clientY)"
        @touchstart.passive="onTouchStart"
        @touchend="clearTouchHold"
        @touchcancel="clearTouchHold"
        @touchmove="onTouchMove"
      ></div>

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
import { computed, onBeforeUnmount } from 'vue'

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

const highlighted = computed(
  () => !!props.highlight && !!props.msg.content && String(props.msg.content).includes(props.highlight)
)

const renderedContent = computed(() => {
  let html = markdownToHtml(props.msg.content || '')
  if (props.highlight) {
    const safeQ = escapeHtml(props.highlight).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    html = html.replace(new RegExp(`(${safeQ})`, 'gi'), '<mark>$1</mark>')
  }
  return html
})

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

@media (max-width: 768px) {
  .bubble-wrap {
    max-width: 82%;
  }
}
</style>

