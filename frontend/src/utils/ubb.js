import DOMPurify from 'dompurify'

const EXCLUDED_PARENT_TAGS = new Set(['A', 'AUDIO', 'VIDEO', 'CODE', 'PRE', 'SCRIPT', 'STYLE', 'TEXTAREA'])
const UBB_PATTERN = /\[(?:b|i|u|img|audio|movie|url|forecolor|qqmusic|wymusic|code|text|now|codo)(?:=[^\]]+)?\]/i
const SAFE_COLOR_PATTERN = /^(?:#[0-9a-f]{3,8}|[a-z]{3,20}|rgba?\(\s*[\d.\s%,]+\)|hsla?\(\s*[\d.\s%,]+\))$/i
const COMMENT_PURITY_CONFIG = {
  USE_PROFILES: { html: true },
  ADD_TAGS: ['audio', 'video'],
  ADD_ATTR: ['controls', 'preload', 'style', 'target', 'rel', 'class', 'src', 'playsinline', 'data-song-id', 'data-date', 'data-ubb-now'],
  ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function escapeAttribute(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
}

function normalizeLineEndings(value) {
  return String(value ?? '').replace(/\r\n?/g, '\n')
}

function sanitizeUrl(rawUrl, { allowContact = false } = {}) {
  const trimmed = String(rawUrl ?? '').trim()
  const compact = trimmed.replace(/[\u0000-\u0020\u007f\s]+/g, '')

  if (!trimmed || /^(?:javascript|vbscript|data):/i.test(compact)) {
    return ''
  }

  if (/^(?:https?:|\/\/|\/|\.{1,2}\/|#|\?)/i.test(trimmed)) {
    return trimmed
  }

  if (allowContact && /^(?:mailto:|tel:)/i.test(trimmed)) {
    return trimmed
  }

  return ''
}

function sanitizeColor(rawColor) {
  const color = String(rawColor ?? '').trim()
  return SAFE_COLOR_PATTERN.test(color) ? color : ''
}

function normalizeMusicId(rawValue) {
  const input = String(rawValue ?? '').trim()
  if (!input) return ''

  const directId = input.match(/^[A-Za-z0-9]+$/)
  if (directId) return directId[0]

  const idFromQuery = input.match(/[?&]id=(\d+)/i)
  if (idFromQuery) return idFromQuery[1]

  const songIdFromQuery = input.match(/[?&]songid=(\d+)/i)
  if (songIdFromQuery) return songIdFromQuery[1]

  const songMidFromQuery = input.match(/[?&](?:songmid|mid)=([A-Za-z0-9]+)/i)
  if (songMidFromQuery) return songMidFromQuery[1]

  const trailingId = input.match(/\/song\/([A-Za-z0-9]+)/i)
  if (trailingId) return trailingId[1]

  const songDetailId = input.match(/\/songDetail\/([A-Za-z0-9]+)/i)
  if (songDetailId) return songDetailId[1]

  return ''
}

function resolveMusicId(rawValue) {
  const raw = String(rawValue ?? '').trim()
  if (!raw) return null

  // UBB 内容经过 escapeHtml 处理，& 会变成 &amp;，需先还原再解析
  const input = raw.replace(/&amp;/gi, '&')

  // 格式1：纯数字 songid（老版）
  const directNumericId = input.match(/^\d+$/)
  if (directNumericId) return { playerId: directNumericId[0], idType: 'songid' }

  // 格式2：纯字母数字混合 songmid（直接传入）
  const directSongMid = input.match(/^[A-Za-z0-9]+$/)
  if (directSongMid) return { playerId: directSongMid[0], idType: 'songmid' }

  // 格式3：老版带参 URL，匹配 ?songid=123 或 ?id=123
  const songIdFromQuery = input.match(/[?&]songid=(\d+)/i) || input.match(/[?&]id=(\d+)/i)
  if (songIdFromQuery) return { playerId: songIdFromQuery[1], idType: 'songid' }

  // 格式4：新版带参 URL，匹配 ?songmid=abc 或 ?mid=abc
  const songMidFromQuery = input.match(/[?&](?:songmid|mid)=([A-Za-z0-9]+)/i)
  if (songMidFromQuery) return { playerId: songMidFromQuery[1], idType: 'songmid' }

  // 格式5：路径包含 mid 的 URL，匹配 /song/abc 或 /songDetail/abc
  const songMidFromPath = input.match(/\/(?:song|songDetail)\/([A-Za-z0-9]+)/i)
  if (songMidFromPath) return { playerId: songMidFromPath[1], idType: 'songmid' }

  return null
}

function extractFirstUrl(rawValue) {
  const match = String(rawValue ?? '').match(/https?:\/\/[^\s<>"']+/i)
  return match ? match[0] : ''
}

function isQqMusicShareUrl(rawUrl) {
  try {
    const url = new URL(rawUrl)
    return ['c6.y.qq.com', 'i.y.qq.com', 'y.qq.com'].includes(url.hostname)
  } catch (e) {
    return false
  }
}

function toHalfWidth(value) {
  return String(value ?? '').replace(/[\uFF01-\uFF5E]/g, char => String.fromCharCode(char.charCodeAt(0) - 0xFEE0)).replace(/\u3000/g, ' ')
}

function formatNow() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

function formatCountdown(dateText) {
  const target = new Date(`${dateText}T00:00:00`)
  if (Number.isNaN(target.getTime())) {
    return '日期格式错误'
  }

  const today = new Date()
  const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const diffDays = Math.ceil((target.getTime() - todayStart.getTime()) / 86400000)

  if (diffDays > 0) {
    return `还有 ${diffDays} 天`
  }
  if (diffDays === 0) {
    return '就是今天'
  }
  return `已过 ${Math.abs(diffDays)} 天`
}

function applySimpleTag(tagName, htmlTag, input) {
  const pattern = new RegExp(`\\[${tagName}\\]([\\s\\S]*?)\\[\\/${tagName}\\]`, 'gi')
  return input.replace(pattern, `<${htmlTag}>$1</${htmlTag}>`)
}

function applyUbbReplacements(input) {
  let output = input

  for (let pass = 0; pass < 6; pass += 1) {
    const before = output

    output = output.replace(/\[img\]([\s\S]*?)\[\/img\]/gi, (_, url) => {
      const safeUrl = sanitizeUrl(url)
      return safeUrl
        ? `<img class="ubb-image" src="${escapeAttribute(safeUrl)}" alt="ubb-image">`
        : _
    })

    output = output.replace(/\[audio\]([\s\S]*?)\[\/audio\]/gi, (_, url) => {
      const safeUrl = sanitizeUrl(url)
      return safeUrl
        ? `<audio class="ubb-audio" controls preload="none" src="${escapeAttribute(safeUrl)}"></audio>`
        : _
    })

    output = output.replace(/\[movie\]([\s\S]*?)\[\/movie\]/gi, (_, url) => {
      const safeUrl = sanitizeUrl(url)
      return safeUrl
        ? `<video class="ubb-video" controls playsinline preload="metadata" src="${escapeAttribute(safeUrl)}"></video>`
        : _
    })

    output = output.replace(/\[qqmusic\]([\s\S]*?)\[\/qqmusic\]/gi, (_, songId) => {
      const resolvedMusic = resolveMusicId(songId)
      return resolvedMusic
        ? `<div class="ubb-music-card ubb-qqmusic" data-song-id="${escapeAttribute(resolvedMusic.playerId)}" data-id-type="${escapeAttribute(resolvedMusic.idType)}">QQ音乐载入中...</div>`
        : `<div class="ubb-music-card ubb-qqmusic" data-share-url="${escapeAttribute(songId.trim())}">QQ音乐载入中...</div>`
    })

    output = output.replace(/\[wymusic\]([\s\S]*?)\[\/wymusic\]/gi, (_, songId) => {
      const safeSongId = normalizeMusicId(songId)
      return safeSongId
        ? `<div class="ubb-music-card ubb-wymusic" data-song-id="${escapeAttribute(safeSongId)}">网易云音乐载入中...</div>`
        : _
    })

    output = output.replace(/\[url=([^\]]+)\]([\s\S]*?)\[\/url\]/gi, (_, url, text) => {
      const safeUrl = sanitizeUrl(url, { allowContact: true })
      return safeUrl
        ? `<a href="${escapeAttribute(safeUrl)}" target="_blank" rel="noopener noreferrer">${text}</a>`
        : text
    })

    output = output.replace(/\[url\]([\s\S]*?)\[\/url\]/gi, (_, url) => {
      const safeUrl = sanitizeUrl(url, { allowContact: true })
      if (!safeUrl) {
        return _
      }
      const safeText = escapeHtml(url.trim())
      return `<a href="${escapeAttribute(safeUrl)}" target="_blank" rel="noopener noreferrer">${safeText}</a>`
    })

    output = output.replace(/\[forecolor=([^\]]+)\]([\s\S]*?)\[\/forecolor\]/gi, (_, color, text) => {
      const safeColor = sanitizeColor(color)
      return safeColor ? `<span style="color:${escapeAttribute(safeColor)}">${text}</span>` : text
    })

    output = output.replace(/\[code\]([\s\S]*?)\[\/code\]/gi, (_, code) => {
      return `<pre class="line"><code><span class="line-content">${code}</span></code></pre>`
    })

    output = output.replace(/\[text\]([\s\S]*?)\[\/text\]/gi, (_, text) => {
      return `<span class="ubb-text">${escapeHtml(toHalfWidth(text))}</span>`
    })

    output = output.replace(/\[now\]/gi, () => {
      const initialText = formatNow()
      return `<time class="ubb-now" data-ubb-now="1">${initialText}</time>`
    })

    output = output.replace(/\[codo\]([\s\S]*?)\[\/codo\]/gi, (_, dateText) => {
      const targetDate = String(dateText ?? '').trim()
      if (!targetDate) return _
      return `<span class="ubb-countdown" data-date="${escapeAttribute(targetDate)}">${formatCountdown(targetDate)}</span>`
    })

    output = applySimpleTag('b', 'strong', output)
    output = applySimpleTag('i', 'em', output)
    output = applySimpleTag('u', 'u', output)

    if (output === before) {
      break
    }
  }

  return output
}

function buildFragment(doc, html) {
  const template = doc.createElement('template')
  template.innerHTML = html
  return template.content
}

function looksLikeHtml(input) {
  return /<\/?[a-z][\w-]*[\s>]/i.test(input)
}

function htmlToUbbBlockText(input) {
  const withLineBreaks = String(input || '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>\s*<p[^>]*>/gi, '\n')
    .replace(/<\/div>\s*<div[^>]*>/gi, '\n')
    .replace(/<\/li>\s*<li[^>]*>/gi, '\n')
    .replace(/<\/blockquote>\s*<blockquote[^>]*>/gi, '\n')
    .replace(/<\/h[1-6]>\s*<h[1-6][^>]*>/gi, '\n')
    .replace(/<\/?(?:p|div|li|blockquote|h[1-6])[^>]*>/gi, '')

  const parser = new DOMParser()
  const doc = parser.parseFromString(`<body>${withLineBreaks}</body>`, 'text/html')
  return (doc.body.textContent || '').replace(/\n{3,}/g, '\n\n').trim()
}

function replaceBlockUbbInHtml(rawInput) {
  return String(rawInput || '').replace(/\[code\]([\s\S]*?)\[\/code\]/gi, (_, innerHtml) => {
    const codeText = htmlToUbbBlockText(innerHtml)
    return `<pre class="line"><code><span class="line-content">${escapeHtml(codeText)}</span></code></pre>`
  })
}

export function hasUbbMarkup(input) {
  return UBB_PATTERN.test(String(input ?? ''))
}

export function convertUbbTextToHtml(input, { escapeText = true, preserveLineBreaks = false } = {}) {
  const normalized = normalizeLineEndings(input)
  let output = escapeText ? escapeHtml(normalized) : normalized
  output = applyUbbReplacements(output)

  if (preserveLineBreaks) {
    output = output.replace(/\n/g, '<br>')
  }

  return output
}

export function convertUbbMarkupInHtml(input) {
  const rawInput = String(input ?? '')

  if (!hasUbbMarkup(rawInput)) {
    return rawInput
  }

  if (!looksLikeHtml(rawInput)) {
    return convertUbbTextToHtml(rawInput, { escapeText: true, preserveLineBreaks: true })
  }

  const normalizedInput = replaceBlockUbbInHtml(rawInput)

  const parser = new DOMParser()
  const doc = parser.parseFromString(normalizedInput, 'text/html')
  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT)
  const textNodes = []
  let currentNode = walker.nextNode()

  while (currentNode) {
    const parentTag = currentNode.parentElement?.tagName
    if (parentTag && !EXCLUDED_PARENT_TAGS.has(parentTag) && hasUbbMarkup(currentNode.nodeValue)) {
      textNodes.push(currentNode)
    }
    currentNode = walker.nextNode()
  }

  textNodes.forEach((node) => {
    const html = convertUbbTextToHtml(node.nodeValue, { escapeText: true, preserveLineBreaks: false })
    node.replaceWith(buildFragment(doc, html))
  })

  return doc.body.innerHTML
}

export function renderCommentUbb(input) {
  const html = convertUbbTextToHtml(input, { escapeText: true, preserveLineBreaks: true })
  return DOMPurify.sanitize(html, COMMENT_PURITY_CONFIG)
}

function buildMusicIframe(doc, provider, songId, idType = 'songid') {
  const iframe = doc.createElement('iframe')
  iframe.loading = 'lazy'
  iframe.referrerPolicy = 'no-referrer-when-downgrade'
  iframe.setAttribute('frameborder', 'no')
  iframe.setAttribute('border', '0')
  iframe.setAttribute('marginwidth', '0')
  iframe.setAttribute('marginheight', '0')
  iframe.className = `ubb-music-frame ${provider}`

  if (provider === 'qqmusic') {
    const queryKey = idType === 'songmid' ? 'songmid' : 'songid'
    iframe.src = `https://i.y.qq.com/n2/m/outchain/player/index.html?${queryKey}=${encodeURIComponent(songId)}&songtype=0`
    iframe.width = '100%'
    iframe.height = '110'
  } else {
    iframe.src = `https://music.163.com/outchain/player?type=2&id=${encodeURIComponent(songId)}&auto=0&height=66`
    iframe.width = '100%'
    iframe.height = '86'
  }

  return iframe
}

async function resolveQqMusicShareUrl(shareText) {
  const response = await fetch(`/api/ubb/resolve-qqmusic/?text=${encodeURIComponent(shareText)}`, {
    method: 'GET',
    credentials: 'same-origin',
    headers: {
      'Accept': 'application/json'
    }
  })

  if (!response.ok) {
    throw new Error('resolve_failed')
  }

  const data = await response.json()
  if (!data || !data.ok || !data.player_id) {
    throw new Error('resolve_failed')
  }

  return {
    playerId: data.player_id,
    idType: data.id_type || 'songid'
  }
}

function installCommentCopyButtons(root) {
  root.querySelectorAll('pre').forEach((block) => {
    if (block.dataset.copyReady === '1') return
    block.dataset.copyReady = '1'

    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'ubb-copy-btn'
    button.textContent = '复制'
    button.addEventListener('click', async () => {
      const text = block.textContent || ''
      try {
        await navigator.clipboard.writeText(text)
        button.textContent = '已复制'
        setTimeout(() => {
          button.textContent = '复制'
        }, 1500)
      } catch (e) {
        button.textContent = '复制失败'
        setTimeout(() => {
          button.textContent = '复制'
        }, 1500)
      }
    })

    block.appendChild(button)
  })
}

export function hydrateUbbDom(root, { addCodeCopyButtons = false } = {}) {
  if (!root) return

  root.querySelectorAll('.ubb-now[data-ubb-now]').forEach((element) => {
    element.textContent = formatNow()
  })

  root.querySelectorAll('.ubb-countdown[data-date]').forEach((element) => {
    element.textContent = formatCountdown(element.dataset.date || '')
  })

  root.querySelectorAll('.ubb-qqmusic[data-song-id], .ubb-wymusic[data-song-id]').forEach((element) => {
    if (element.dataset.hydrated === '1') return
    const provider = element.classList.contains('ubb-qqmusic') ? 'qqmusic' : 'wymusic'
    const songId = element.dataset.songId || ''
    if (!songId) return

    const iframe = buildMusicIframe(document, provider, songId, element.dataset.idType || 'songid')
    element.innerHTML = ''
    element.appendChild(iframe)
    element.dataset.hydrated = '1'
  })

  root.querySelectorAll('.ubb-qqmusic[data-share-url]').forEach((element) => {
    if (element.dataset.hydrated === '1' || element.dataset.resolving === '1') return
    const sharePayload = element.dataset.shareUrl || ''
    if (!sharePayload) return

    element.dataset.resolving = '1'
    resolveQqMusicShareUrl(sharePayload)
      .then(({ playerId, idType }) => {
        if (!playerId) {
          element.textContent = 'QQ音乐链接解析失败'
          return
        }

        const iframe = buildMusicIframe(document, 'qqmusic', playerId, idType)
        element.innerHTML = ''
        element.appendChild(iframe)
        element.dataset.songId = playerId
        element.dataset.idType = idType
        element.dataset.hydrated = '1'
      })
      .catch(() => {
        const link = document.createElement('a')
        const fallbackUrl = extractFirstUrl(sharePayload)
        if (!fallbackUrl) {
          element.textContent = 'QQ音乐链接解析失败'
          return
        }
        link.href = fallbackUrl
        link.target = '_blank'
        link.rel = 'noopener noreferrer'
        link.textContent = '打开 QQ 音乐分享链接'
        element.innerHTML = ''
        element.appendChild(link)
      })
      .finally(() => {
        delete element.dataset.resolving
      })
  })

  if (addCodeCopyButtons) {
    installCommentCopyButtons(root)
  }
}
