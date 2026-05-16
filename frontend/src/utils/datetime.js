function isValidDate(date) {
  return date instanceof Date && !Number.isNaN(date.getTime())
}

export function parseDate(value) {
  const date = value instanceof Date ? value : new Date(value)
  return isValidDate(date) ? date : null
}

export function formatHm(value) {
  const date = parseDate(value)
  if (!date) return ''
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

export function formatMonthDayHm(value) {
  const date = parseDate(value)
  if (!date) return ''
  return `${date.getMonth() + 1}/${date.getDate()} ${formatHm(date)}`
}

export function formatRelativeListDate(value) {
  const date = parseDate(value)
  if (!date) return ''
  const now = new Date()
  if (date.toDateString() === now.toDateString()) {
    return formatHm(date)
  }
  return `${date.getMonth() + 1}/${date.getDate()}`
}

export function formatDateOnly(value, locale = 'zh-CN') {
  const date = parseDate(value)
  return date ? date.toLocaleDateString(locale) : ''
}

export function formatMonthDayShortTime(value, locale = 'zh-CN') {
  const date = parseDate(value)
  if (!date) return ''
  return date.toLocaleString(locale, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}
