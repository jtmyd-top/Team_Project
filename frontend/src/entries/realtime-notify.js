/**
 * 全局实时通知（base.html 登录后加载）
 *
 * 通过 /ws/messages/ 通道接收 `notification` 事件：
 * - 右上角弹出可点击的轻量 toast（原生 DOM，无框架依赖）
 * - 同时派发 `app:notification` window 事件，供页面内组件（如通知中心）实时更新
 *
 * 私信页面自身已有完整的实时处理，new_message 类通知在 /messages/ 下不再弹 toast。
 */
import { ChatWebSocket } from '@services/chatWebSocket'

const config = window.APP_REALTIME || {}

const TOAST_DURATION = 6000
const MAX_TOASTS = 4

const KIND_ICONS = {
  new_message: 'fas fa-message',
  new_comment: 'fas fa-comment-dots',
  comment_reply: 'fas fa-reply',
  new_follower: 'fas fa-user-plus',
  profile_liked: 'fas fa-heart',
  note_copied: 'fas fa-copy',
  note_revision_restored: 'fas fa-clock-rotate-left',
  report_received: 'fas fa-shield-halved',
  report_resolved: 'fas fa-shield-halved',
  sanction_applied: 'fas fa-ban',
  sanction_revoked: 'fas fa-circle-check',
  appeal_submitted: 'fas fa-scale-balanced',
  appeal_resolved: 'fas fa-scale-balanced',
}

function injectStyles() {
  if (document.getElementById('rt-notify-styles')) return
  const style = document.createElement('style')
  style.id = 'rt-notify-styles'
  style.textContent = `
#rt-notify-container {
  position: fixed;
  top: 72px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(340px, calc(100vw - 32px));
  pointer-events: none;
}
.rt-notify-toast {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgba(64, 158, 255, 0.35);
  background: rgba(255, 255, 255, 0.97);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.16);
  cursor: pointer;
  pointer-events: auto;
  animation: rt-notify-in 0.25s ease-out;
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.rt-notify-toast.leaving {
  opacity: 0;
  transform: translateX(24px);
}
[data-theme="dark"] .rt-notify-toast {
  background: rgba(30, 41, 59, 0.97);
  border-color: rgba(64, 158, 255, 0.45);
}
.rt-notify-icon {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.12);
  font-size: 14px;
}
.rt-notify-copy {
  min-width: 0;
  flex: 1;
}
.rt-notify-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
[data-theme="dark"] .rt-notify-title { color: #e2e8f0; }
.rt-notify-body {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
[data-theme="dark"] .rt-notify-body { color: #94a3b8; }
.rt-notify-close {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 4px;
}
@keyframes rt-notify-in {
  from { opacity: 0; transform: translateX(24px); }
  to { opacity: 1; transform: translateX(0); }
}
`
  document.head.appendChild(style)
}

function getContainer() {
  let container = document.getElementById('rt-notify-container')
  if (!container) {
    container = document.createElement('div')
    container.id = 'rt-notify-container'
    document.body.appendChild(container)
  }
  return container
}

function notificationUrl(notification) {
  const data = notification.data || {}
  if (typeof data.url === 'string' && data.url.startsWith('/')) return data.url
  if (data.note_id) return `/knowledge/?note=${data.note_id}`
  if (data.group_id || data.message_id || notification.kind === 'new_message') return '/messages/'
  return ''
}

function dismissToast(toast) {
  if (toast.dataset.leaving) return
  toast.dataset.leaving = '1'
  toast.classList.add('leaving')
  setTimeout(() => toast.remove(), 320)
}

function showToast(notification) {
  injectStyles()
  const container = getContainer()

  while (container.children.length >= MAX_TOASTS) {
    container.firstElementChild.remove()
  }

  const toast = document.createElement('div')
  toast.className = 'rt-notify-toast'

  const icon = document.createElement('span')
  icon.className = 'rt-notify-icon'
  icon.innerHTML = `<i class="${KIND_ICONS[notification.kind] || 'fas fa-bell'}"></i>`

  const copy = document.createElement('div')
  copy.className = 'rt-notify-copy'
  const title = document.createElement('p')
  title.className = 'rt-notify-title'
  title.textContent = notification.title || '系统通知'
  copy.appendChild(title)
  if (notification.body) {
    const body = document.createElement('p')
    body.className = 'rt-notify-body'
    body.textContent = notification.body
    copy.appendChild(body)
  }

  const close = document.createElement('button')
  close.className = 'rt-notify-close'
  close.type = 'button'
  close.setAttribute('aria-label', '关闭通知')
  close.innerHTML = '<i class="fas fa-xmark"></i>'
  close.addEventListener('click', (event) => {
    event.stopPropagation()
    dismissToast(toast)
  })

  toast.appendChild(icon)
  toast.appendChild(copy)
  toast.appendChild(close)

  const url = notificationUrl(notification)
  if (url) {
    toast.addEventListener('click', () => {
      window.location.href = url
    })
  }

  container.appendChild(toast)
  setTimeout(() => dismissToast(toast), TOAST_DURATION)
}

function shouldToast(notification) {
  // 私信页面自身有完整的实时消息 UI，不重复弹私信 toast
  if (notification.kind === 'new_message' && window.location.pathname.startsWith('/messages')) {
    return false
  }
  return true
}

function handleEvent(data) {
  if (!data || data.type !== 'notification' || !data.notification) return
  window.dispatchEvent(new CustomEvent('app:notification', { detail: data }))
  if (shouldToast(data.notification)) {
    showToast(data.notification)
  }
}

if (config.enabled && 'WebSocket' in window) {
  const socket = new ChatWebSocket({
    path: config.wsPath || '/ws/messages/',
    onEvent: handleEvent,
  })
  socket.connect()
  window.addEventListener('beforeunload', () => socket.close())
}
