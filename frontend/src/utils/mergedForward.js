export const MERGED_FORWARD_PREFIX = '__MERGED_FORWARD_V1__:'
export const MERGED_FORWARD_MAX_ITEMS = 99
export const MERGED_FORWARD_MAX_ENCODED_LENGTH = 100000

export function encodeMergedForward(payload) {
  const json = JSON.stringify(payload || {})
  const encoded = `${MERGED_FORWARD_PREFIX}${toBase64(json)}`
  if (encoded.length > MERGED_FORWARD_MAX_ENCODED_LENGTH) {
    throw new Error('合并转发内容过长，请减少消息数量后再试')
  }
  return encoded
}

export function parseMergedForward(content) {
  const raw = String(content || '').trim()
  if (!raw.startsWith(MERGED_FORWARD_PREFIX)) return null
  try {
    const decoded = fromBase64(raw.slice(MERGED_FORWARD_PREFIX.length))
    const data = JSON.parse(decoded)
    if (!data || data.type !== 'merged_forward' || !Array.isArray(data.items)) return null
    return {
      ...data,
      title: String(data.title || '聊天记录'),
      source: String(data.source || ''),
      count: Number(data.count || data.items.length) || data.items.length,
      items: data.items.slice(0, MERGED_FORWARD_MAX_ITEMS).map(normalizeForwardItem).filter(Boolean),
    }
  } catch {
    return null
  }
}

export function mergedForwardPreview(content, fallback = '') {
  const data = parseMergedForward(content)
  if (!data) return fallback
  const lines = data.items
    .slice(0, 3)
    .map((item) => `${item.sender}: ${item.preview || item.content || '[附件]'}`)
  return `[聊天记录] ${lines.join(' / ') || data.title}`
}

export function mergedForwardPlainText(content, fallback = '') {
  const data = parseMergedForward(content)
  if (!data) return fallback
  const lines = [`[聊天记录] ${data.title}`]
  if (data.source) lines.push(data.source)
  data.items.forEach((item) => {
    const attachmentText = (item.attachments || [])
      .map((attachment) => `[附件] ${attachment.name || '未命名文件'}`)
      .join(' ')
    const body = item.content || item.preview || attachmentText || '[附件]'
    lines.push(`${item.sender}: ${body}`)
  })
  return lines.join('\n')
}

function normalizeForwardItem(item) {
  if (!item || typeof item !== 'object') return null
  return {
    id: item.id,
    sender: String(item.sender || '未知用户'),
    avatar: String(item.avatar || '/static/img/default-avatar.png'),
    is_own: item.is_own === true,
    content: String(item.content || ''),
    preview: String(item.preview || item.content || ''),
    time: String(item.time || ''),
    attachments: Array.isArray(item.attachments) ? item.attachments : [],
  }
}

function toBase64(value) {
  const bytes = new TextEncoder().encode(value)
  let binary = ''
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte)
  })
  return btoa(binary)
}

function fromBase64(value) {
  const binary = atob(value)
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0))
  return new TextDecoder().decode(bytes)
}
