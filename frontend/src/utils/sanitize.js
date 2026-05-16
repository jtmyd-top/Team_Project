import DOMPurify from 'dompurify'

export const DEFAULT_HTML_SANITIZE_CONFIG = {
  USE_PROFILES: { html: true },
}

export function sanitizeHtml(html, config = DEFAULT_HTML_SANITIZE_CONFIG) {
  return DOMPurify.sanitize(String(html || ''), config)
}

export function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
