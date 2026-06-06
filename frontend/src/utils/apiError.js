export function extractApiErrorMessage(data, fallback = '请求失败') {
  if (!data) return fallback
  if (typeof data === 'string') return data || fallback

  const directMessage = normalizeErrorValue(data.error || data.message || data.detail)
  if (directMessage) return directMessage

  if (data.status === 'error') {
    const statusMessage = normalizeErrorValue(data.message || data.error)
    if (statusMessage) return statusMessage
  }

  const nestedErrors = normalizeErrorValue(data.errors)
  if (nestedErrors) return nestedErrors

  if (typeof data === 'object') {
    const messages = []
    for (const [field, value] of Object.entries(data)) {
      if (['status', 'code'].includes(field)) continue
      const message = normalizeErrorValue(value)
      if (message) messages.push(message)
    }
    if (messages.length) return messages.join('; ')
  }

  return fallback
}

function normalizeErrorValue(value) {
  if (!value) return ''
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    return value
      .map(item => normalizeErrorValue(item))
      .filter(Boolean)
      .join('; ')
  }
  if (typeof value === 'object') {
    if (value.message) return normalizeErrorValue(value.message)
    if (value.error) return normalizeErrorValue(value.error)
    if (value.detail) return normalizeErrorValue(value.detail)
    return Object.values(value)
      .map(item => normalizeErrorValue(item))
      .filter(Boolean)
      .join('; ')
  }
  return String(value)
}
