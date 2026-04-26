<template>
  <div
    class="conversation-item"
    :class="{
      active: active,
      pinned: conv.is_pinned,
      muted: conv.is_muted,
      'has-unread': displayUnread > 0,
    }"
    @click="$emit('select', conv)"
    @contextmenu.prevent="$emit('context-menu', { conv, x: $event.clientX, y: $event.clientY })"
  >
    <div class="avatar-wrap">
      <img :src="conv.avatar" :alt="conv.username" class="avatar" width="48" height="48" decoding="async" />
      <span v-if="conv.is_pinned" class="icon-badge pin-badge" title="已置顶">
        <i class="fas fa-thumbtack"></i>
      </span>
    </div>

    <div class="info">
      <div class="top-row">
        <h3 class="name">{{ conv.username }}</h3>
        <span class="time">{{ formatTime(conv.last_message_time) }}</span>
      </div>
      <div class="bottom-row">
        <p class="preview" :class="{ italic: isOwnLast }">
          <span v-if="isOwnLast" class="own-prefix">我：</span>{{ previewText }}
        </p>
        <div class="indicators">
          <i v-if="conv.is_muted" class="fas fa-bell-slash muted-icon" title="消息免打扰"></i>
          <i
            v-if="conv.disappearing_enabled"
            class="fas fa-fire-alt disappearing-icon"
            title="阅后即焚已开启"
          ></i>
          <span v-if="displayUnread > 0" class="unread-badge" :class="{ dot: conv.is_muted }">
            <template v-if="!conv.is_muted">{{ displayUnread > 99 ? '99+' : displayUnread }}</template>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  conv: { type: Object, required: true },
  active: { type: Boolean, default: false },
  currentUserId: { type: Number, default: 0 },
})

defineEmits(['select', 'context-menu'])

const isOwnLast = computed(
  () => props.conv.last_sender_id && props.conv.last_sender_id === props.currentUserId
)

const displayUnread = computed(() => {
  if (props.conv.unread_count > 0) return props.conv.unread_count
  if (props.conv.force_unread) return 1
  return 0
})

const previewText = computed(() => {
  const txt = props.conv.last_message || ''
  return txt.length > 40 ? txt.slice(0, 40) + '...' : txt
})

function formatTime(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  const now = new Date()
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  if (sameDay) {
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
  }
  const diffDays = Math.floor((now - date) / 86400000)
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) {
    return ['日', '一', '二', '三', '四', '五', '六'][date.getDay()] && `周${['日', '一', '二', '三', '四', '五', '六'][date.getDay()]}`
  }
  return `${date.getMonth() + 1}/${date.getDate()}`
}
</script>

<style scoped>
.conversation-item {
  display: grid;
  grid-template-columns: 48px 1fr;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.18s ease;
  position: relative;
}

.conversation-item:hover {
  background: var(--bg-tertiary, rgba(0, 0, 0, 0.04));
}

.conversation-item.active {
  background: color-mix(in srgb, var(--primary-color, #2563eb) 14%, transparent);
}

.conversation-item.pinned {
  background: color-mix(in srgb, var(--primary-color, #2563eb) 6%, transparent);
}

.conversation-item.pinned:hover,
.conversation-item.pinned.active {
  background: color-mix(in srgb, var(--primary-color, #2563eb) 18%, transparent);
}

.avatar-wrap {
  position: relative;
  width: 48px;
  height: 48px;
  overflow: hidden;
  border-radius: 50%;
  align-self: center;
}

.avatar {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
  background: var(--bg-tertiary);
  vertical-align: top;
}

.icon-badge {
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  color: #fff;
  background: var(--primary-color, #2563eb);
  border: 2px solid var(--bg-primary, #fff);
}

.info {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  justify-content: center;
}

.top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.name {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.time {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
  flex-shrink: 0;
}

.conversation-item.active .time {
  color: var(--primary-color);
}

.bottom-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.preview {
  font-size: 12.5px;
  color: var(--text-secondary);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  line-height: 1.4;
}

.preview.italic {
  color: var(--text-tertiary);
}

.own-prefix {
  color: var(--text-tertiary);
}

.conversation-item.has-unread .preview {
  color: var(--text-primary);
  font-weight: 500;
}

.indicators {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.muted-icon,
.disappearing-icon {
  font-size: 11px;
  color: var(--text-tertiary);
}

.disappearing-icon {
  color: #f59e0b;
}

.unread-badge {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: var(--danger-color, #ef4444);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.unread-badge.dot {
  min-width: 8px;
  width: 8px;
  height: 8px;
  padding: 0;
  border-radius: 50%;
  background: var(--text-tertiary);
}
</style>
