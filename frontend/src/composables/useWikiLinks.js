import { ref } from 'vue'

/**
 * Wiki 双向链接：把正文里的 [[标题]] 语法渲染成可点击链接，并拉取反链。
 *
 * 服务端 /api/notes/<id>/links/ 返回：
 *   { outgoing: { resolved: [{title, id, note_title, is_public}], unresolved: [] },
 *     backlinks: [{id, title, is_public}] }
 *
 * resolved 里的 title 是正文中书写的原始标题（用于文本匹配），id 是解析到的笔记。
 */

// 与后端 WIKI_LINK_PATTERN 对齐：[[ 非中括号/换行 ]]
const WIKI_LINK_RE = /\[\[([^[\]\n]{1,255}?)\]\]/g

export function useWikiLinks() {
  const backlinks = ref([])
  const isLoadingLinks = ref(false)
  // casefold(title) -> noteId，用于把 [[标题]] 文本替换成链接
  let resolvedMap = new Map()

  async function fetchLinks(noteId) {
    if (!noteId) {
      backlinks.value = []
      resolvedMap = new Map()
      return
    }
    isLoadingLinks.value = true
    try {
      const res = await fetch(`/api/notes/${noteId}/links/`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      })
      if (!res.ok) {
        backlinks.value = []
        resolvedMap = new Map()
        return
      }
      const data = await res.json()
      backlinks.value = Array.isArray(data?.backlinks) ? data.backlinks : []
      const map = new Map()
      for (const link of data?.outgoing?.resolved || []) {
        if (link?.title != null && link?.id != null) {
          map.set(String(link.title).toLowerCase(), link.id)
        }
      }
      resolvedMap = map
    } catch (e) {
      backlinks.value = []
      resolvedMap = new Map()
    } finally {
      isLoadingLinks.value = false
    }
  }

  function buildLinkEl(title, noteId, onNavigate) {
    const a = document.createElement('a')
    a.className = 'wiki-link'
    a.textContent = title
    a.href = `/knowledge/?note=${noteId}`
    a.dataset.wikiNoteId = String(noteId)
    a.addEventListener('click', (ev) => {
      if (typeof onNavigate === 'function') {
        ev.preventDefault()
        onNavigate(noteId)
      }
    })
    return a
  }

  /**
   * 遍历容器内的文本节点，把 [[标题]] 替换为 <a class="wiki-link"> 或
   * <span class="wiki-link is-unresolved">。跳过 code/pre/a 内部，避免破坏代码块和已有链接。
   *
   * 可重入：链接数据晚于正文渲染到达时，第一遍会先生成 unresolved 占位 span，
   * 第二遍将其中命中 resolvedMap 的升级为可点击链接。
   */
  function decorateWikiLinks(container, onNavigate) {
    if (!container) return

    // 升级上一轮生成的 unresolved 占位
    container.querySelectorAll('span.wiki-link.is-unresolved').forEach((span) => {
      const title = span.dataset.wikiTitle || span.textContent || ''
      const noteId = resolvedMap.get(title.trim().toLowerCase())
      if (noteId) {
        span.replaceWith(buildLinkEl(title.trim(), noteId, onNavigate))
      }
    })

    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (!node.nodeValue || node.nodeValue.indexOf('[[') === -1) {
          return NodeFilter.FILTER_REJECT
        }
        let el = node.parentElement
        while (el && el !== container) {
          const tag = el.tagName
          if (tag === 'CODE' || tag === 'PRE' || tag === 'A') {
            return NodeFilter.FILTER_REJECT
          }
          el = el.parentElement
        }
        return NodeFilter.FILTER_ACCEPT
      },
    })

    const targets = []
    let current = walker.nextNode()
    while (current) {
      targets.push(current)
      current = walker.nextNode()
    }

    for (const textNode of targets) {
      const text = textNode.nodeValue
      WIKI_LINK_RE.lastIndex = 0
      if (!WIKI_LINK_RE.test(text)) continue

      WIKI_LINK_RE.lastIndex = 0
      const frag = document.createDocumentFragment()
      let lastIndex = 0
      let match
      while ((match = WIKI_LINK_RE.exec(text)) !== null) {
        const [full, rawTitle] = match
        const title = rawTitle.trim()
        if (match.index > lastIndex) {
          frag.appendChild(document.createTextNode(text.slice(lastIndex, match.index)))
        }
        if (!title) {
          frag.appendChild(document.createTextNode(full))
        } else {
          const noteId = resolvedMap.get(title.toLowerCase())
          if (noteId) {
            frag.appendChild(buildLinkEl(title, noteId, onNavigate))
          } else {
            const span = document.createElement('span')
            span.className = 'wiki-link is-unresolved'
            span.textContent = title
            span.title = '未找到匹配的笔记'
            span.dataset.wikiTitle = title
            frag.appendChild(span)
          }
        }
        lastIndex = match.index + full.length
      }
      if (lastIndex < text.length) {
        frag.appendChild(document.createTextNode(text.slice(lastIndex)))
      }
      textNode.parentNode.replaceChild(frag, textNode)
    }
  }

  return {
    backlinks,
    isLoadingLinks,
    fetchLinks,
    decorateWikiLinks,
  }
}
