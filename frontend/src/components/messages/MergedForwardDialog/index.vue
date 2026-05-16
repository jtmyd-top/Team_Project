<template>
  <div class="merged-dialog-overlay" @click.self="$emit('close')">
    <div class="merged-dialog">
      <div class="merged-dialog-header">
        <button class="merged-dialog-close left" type="button" @click="$emit('close')">
          <i class="fas fa-chevron-left"></i>
        </button>
        <div class="merged-dialog-title-wrap">
          <h3 class="merged-dialog-title">聊天记录</h3>
          <p class="merged-dialog-subtitle">{{ payloadTitle }}</p>
        </div>
        <button class="merged-dialog-close" type="button" @click="$emit('close')">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="merged-dialog-body">
        <div class="merged-dialog-summary">
          {{ payload?.source || `共 ${messageCount} 条聊天记录` }}
        </div>

        <div
          v-for="(item, index) in payload?.items || []"
          :key="item.id || index"
          class="merged-message"
          :class="{ own: isOwnItem(item) }"
        >
          <img :src="item.avatar || '/static/img/default-avatar.png'" :alt="item.sender" class="merged-avatar" />
          <div class="merged-content">
            <div class="merged-meta">
              <span class="merged-sender">{{ item.sender }}</span>
              <span class="merged-time">{{ formatTime(item.time) }}</span>
            </div>

            <div v-if="item.content" class="merged-text">{{ item.content }}</div>

            <div v-if="item.attachments?.length" class="merged-attachments">
              <div
                v-for="attachment in item.attachments"
                :key="attachment.id || attachment.url || attachment.name"
                class="merged-attachment"
                :class="`type-${attachment.type}`"
              >
                <a v-if="attachment.type === 'image'" :href="attachment.url" target="_blank" rel="noopener noreferrer">
                  <img :src="attachment.url" :alt="attachment.name || '图片'" class="merged-image" />
                </a>
                <audio
                  v-else-if="attachment.type === 'audio'"
                  class="merged-audio"
                  :src="attachment.url"
                  controls
                  preload="metadata"
                ></audio>
                <video
                  v-else-if="attachment.type === 'video'"
                  class="merged-video"
                  :src="attachment.url"
                  controls
                  preload="metadata"
                ></video>
                <a
                  v-else
                  :href="attachment.url"
                  :download="attachment.name"
                  class="merged-file"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <i class="fas fa-file"></i>
                  <span>{{ attachment.name || '附件' }}</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatMonthDayHm } from '@utils/datetime'

const props = defineProps({
  payload: { type: Object, default: null },
  currentUserName: { type: String, default: '我' },
})

defineEmits(['close'])

const payloadTitle = computed(() => props.payload?.title || '聊天记录')
const messageCount = computed(() => Number(props.payload?.count || props.payload?.items?.length || 0))

function formatTime(iso) {
  return formatMonthDayHm(iso) || iso || ''
}

function isOwnItem(item) {
  if (item?.is_own === true) return true
  const sender = String(item?.sender || '').trim()
  const currentName = String(props.currentUserName || '').trim()
  return !!sender && (sender === '我' || (!!currentName && sender === currentName))
}
</script>

<style scoped>
.merged-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(0, 0, 0, 0.42);
}

.merged-dialog {
  width: min(100%, 520px);
  max-height: min(84vh, 760px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 10px;
  background: #ededed;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.2);
}

.merged-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px 10px;
  background: #f7f7f7;
  border-bottom: 1px solid #e6e6e6;
}

.merged-dialog-title-wrap {
  min-width: 0;
  flex: 1;
  text-align: center;
}

.merged-dialog-title {
  margin: 0;
  font-size: 16px;
  line-height: 1.35;
  color: #111111;
}

.merged-dialog-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: #888888;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.merged-dialog-close {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #555555;
  cursor: pointer;
  flex: 0 0 32px;
}

.merged-dialog-close.left {
  font-size: 15px;
}

.merged-dialog-body {
  overflow-y: auto;
  padding: 14px 14px 18px;
}

.merged-dialog-summary {
  display: flex;
  justify-content: center;
  margin-bottom: 14px;
  font-size: 12px;
  color: #8b8b8b;
}

.merged-message {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 10px;
  align-items: flex-start;
}

.merged-message.own {
  grid-template-columns: minmax(0, 1fr) 36px;
}

.merged-message + .merged-message {
  margin-top: 16px;
}

.merged-avatar {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  object-fit: cover;
  background: #e5e7eb;
}

.merged-message.own .merged-avatar {
  grid-column: 2;
  grid-row: 1;
}

.merged-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
}

.merged-message.own .merged-content {
  grid-column: 1;
  grid-row: 1;
  align-items: flex-end;
}

.merged-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.merged-message.own .merged-meta {
  flex-direction: row-reverse;
}

.merged-sender {
  font-size: 12px;
  color: #7d7d7d;
  line-height: 1;
}

.merged-time {
  font-size: 11px;
  color: #a0a0a0;
  line-height: 1;
}

.merged-text {
  width: fit-content;
  max-width: min(100%, 320px);
  padding: 10px 12px;
  border-radius: 8px;
  background: #ffffff;
  color: #111111;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: 0 1px 1px rgba(0, 0, 0, 0.04);
}

.merged-message.own .merged-text {
  background: var(--primary-color, #2563eb);
  color: #ffffff;
  text-align: left;
}

.merged-attachments {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}

.merged-message.own .merged-attachments {
  align-items: flex-end;
}

.merged-attachment.type-image,
.merged-attachment.type-video {
  width: min(100%, 240px);
  overflow: hidden;
  border-radius: 8px;
  background: #ffffff;
}

.merged-image,
.merged-video {
  display: block;
  width: 100%;
  max-height: 220px;
  object-fit: contain;
}

.merged-audio {
  width: min(100%, 260px);
}

.merged-file {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  max-width: 100%;
  padding: 10px 12px;
  border-radius: 8px;
  background: #ffffff;
  color: #111111;
  font-size: 12.5px;
  text-decoration: none;
}

.merged-message.own .merged-file {
  background: var(--primary-color, #2563eb);
  color: #ffffff;
}

@media (max-width: 768px) {
  .merged-dialog-overlay {
    padding: 0;
  }

  .merged-dialog {
    width: 100%;
    max-height: 100vh;
    height: 100vh;
    border-radius: 0;
  }

  .merged-text {
    max-width: min(100%, 280px);
  }
}
</style>
