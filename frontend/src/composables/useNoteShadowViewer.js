/**
 * NoteShadowViewer 逻辑层
 * 处理 Shadow DOM 渲染、内容解密、目录滚动等功能
 */

import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import DOMPurify from 'dompurify'
import { useCodeEnhancer } from '@composables/useCodeEnhancer'
import { useClientCrypto } from '@composables/useClientCrypto'
import { useVaultStore } from '@/stores/vault'
import { getShadowStyles, purifyConfig, TOC_THRESHOLD } from '@/components/knowledge/NoteShadowViewer/config.js'
import { convertUbbMarkupInHtml, hydrateUbbDom } from '@/utils/ubb'

export function useNoteShadowViewer(props) {
  // ==================== Refs ====================
  const hostRef = ref(null)
  const shadowRoot = ref(null)

  // ==================== Composables ====================
  const { enhance: enhanceCodeBlocks } = useCodeEnhancer()
  const { decryptContent, looksLikeEncrypted } = useClientCrypto()
  const vaultStore = useVaultStore()

  // ==================== 状态 ====================
  const hasRequestedVaultUnlock = ref(false)
  const isDecrypting = ref(false)
  const decryptError = ref('')
  const decryptedContent = ref('')
  const tocItems = ref([])
  const showToc = ref(false)
  const activeTocId = ref('')
  const scrollProgress = ref(0)

  // 缓存
  let cachedRawHtml = ''
  let cachedCleanHtml = ''
  let scrollParent = null

  // ==================== 计算属性 ====================
  // 是否有有效的密钥（统一走 vaultStore.isUnlocked）
  const hasValidKey = computed(() => vaultStore.isUnlocked)

  const displayContent = computed(() => {
    if (!props.isSecret) {
      return props.content
    }

    if (!hasValidKey.value) {
      return ''
    }

    if (decryptedContent.value) {
      return decryptedContent.value
    }

    if (isDecrypting.value) {
      return ''
    }

    if (decryptError.value) {
      return ''
    }

    return props.content
  })

  // ==================== 解密逻辑 ====================
  let latestDecryptRequestId = 0
  async function decryptNoteContent() {
    if (!props.isSecret || !props.content) {
      return
    }

    console.log('[Vault] Starting decryption process...', {
      isSecret: props.isSecret,
      isTrashed: props.isTrashed,
      contentLength: props.content?.length || 0,
      isUnlocked: vaultStore.isUnlocked
    })

    if (!looksLikeEncrypted(props.content)) {
      console.warn('[Vault] Content does not look like encrypted data, treating as plaintext')
      decryptedContent.value = props.content
      return
    }

    if (!vaultStore.isUnlocked) {
      const recovered = await vaultStore.recoverKey()
      if (!recovered || !vaultStore.isUnlocked) {
        console.error('[Vault] Vault is locked, cannot decrypt')
        decryptError.value = '缺少加密密钥，请重新验证'
        return
      }
    }

    const requestId = ++latestDecryptRequestId
    const capturedNoteId = props.noteId
    const capturedContent = props.content

    isDecrypting.value = true
    decryptError.value = ''

    try {
      const plaintext = await decryptContent(capturedContent)
      // 竞态保护：如果期间切换了笔记或内容，丢弃本次结果
      if (requestId !== latestDecryptRequestId || capturedNoteId !== props.noteId) return
      decryptedContent.value = plaintext
      console.log('[Vault] Content decrypted successfully')
    } catch (e) {
      if (requestId !== latestDecryptRequestId || capturedNoteId !== props.noteId) return
      console.error('[Vault] 前端解密失败:', e)
      decryptError.value = '解密失败：' + e.message
    } finally {
      if (requestId === latestDecryptRequestId) {
        isDecrypting.value = false
      }
    }
  }

  // ==================== Shadow DOM 渲染 ====================
  function renderContent(forceStyleUpdate = false) {
    if (!shadowRoot.value) return

    const rawHtml = displayContent.value || ''
    const hasValidDek = vaultStore.isUnlocked
    const needsVerification = props.isSecret && !hasValidDek
    const shouldUpdate = rawHtml !== cachedRawHtml || needsVerification || forceStyleUpdate

    console.log('[ShadowViewer] renderContent called', {
      rawHtmlLength: rawHtml.length,
      shouldUpdate,
      forceStyleUpdate,
      hasPreTags: rawHtml.includes('<pre')
    })

    if (shouldUpdate) {
      cachedRawHtml = rawHtml

      if (needsVerification) {
        cachedCleanHtml = `
          <div class="vault-trash-locked-notice">
            <div class="notice-icon">🔒</div>
            <div class="notice-title">内容已锁定</div>
            <div class="notice-message">这是一条保密笔记，需要恢复笔记后才能查看内容</div>
            <div class="notice-hint">请在弹出的对话框中输入验证码</div>
          </div>
        `
        tocItems.value = []
        showToc.value = false

        if (!hasRequestedVaultUnlock.value) {
          hasRequestedVaultUnlock.value = true
          window.dispatchEvent(new CustomEvent('open-vault-unlock-dialog', {
            detail: { fromTrash: props.isTrashed, noteId: props.noteId }
          }))
        }
      } else if (props.isSecret && isDecrypting.value) {
        cachedCleanHtml = '<div style="padding: 20px; text-align: center; color: #999;">解密中，请稍候...</div>'
        tocItems.value = []
        showToc.value = false
      } else if (decryptError.value) {
        cachedCleanHtml = `<div style="padding: 20px; color: #ff0000;">${decryptError.value}</div>`
        tocItems.value = []
        showToc.value = false
      } else {
        const normalizedHtml = convertUbbMarkupInHtml(rawHtml)
        cachedCleanHtml = DOMPurify.sanitize(normalizedHtml, purifyConfig)
        console.log('[ShadowViewer] Sanitized HTML has pre tags:', cachedCleanHtml.includes('<pre'))
        tocItems.value = props.toc || []
        showToc.value = tocItems.value.length >= TOC_THRESHOLD
      }
    }

    const styleEl = shadowRoot.value.querySelector('style')
    const contentEl = shadowRoot.value.querySelector('.note-content')

    if (styleEl && contentEl && !forceStyleUpdate) {
      contentEl.innerHTML = cachedCleanHtml
    } else {
      shadowRoot.value.innerHTML = `
        <style>${getShadowStyles(props.isDark)}</style>
        <div class="note-content">${cachedCleanHtml}</div>
      `
    }

    // 增强代码块 - 使用 requestAnimationFrame 确保 DOM 已渲染
    requestAnimationFrame(() => {
      if (!shadowRoot.value) return

      const content = shadowRoot.value.querySelector('.note-content')
      if (!content) {
        console.log('[CodeEnhancer] No .note-content found')
        return
      }

      setupScrollSpy()

      const preBlocks = content.querySelectorAll('pre')
      console.log('[CodeEnhancer] Found pre blocks:', preBlocks.length)

      hydrateUbbDom(content)

      if (preBlocks.length > 0) {
        preBlocks.forEach((pre, index) => {
          console.log(`[CodeEnhancer] Pre block ${index}:`, {
            className: pre.className,
            hasCode: !!pre.querySelector('code'),
            textLength: pre.textContent?.length || 0
          })
        })
        enhanceCodeBlocks(content)
        console.log('[CodeEnhancer] Enhancement completed')
      }
    })
  }

  function initShadowRoot() {
    if (hostRef.value && !shadowRoot.value) {
      shadowRoot.value = hostRef.value.attachShadow({ mode: 'open' })
      renderContent()
    }
  }

  // ==================== 滚动监听 ====================
  function getScrollParent(node) {
    if (node == null) return null
    if (node.scrollHeight > node.clientHeight &&
        (getComputedStyle(node).overflowY === 'auto' || getComputedStyle(node).overflowY === 'scroll')) {
      return node
    }
    return getScrollParent(node.parentNode) || window
  }

  function setupScrollSpy() {
    if (!shadowRoot.value) return

    const contentEl = shadowRoot.value.querySelector('.note-content')
    if (!contentEl) return

    scrollParent = getScrollParent(hostRef.value)
    scrollParent.addEventListener('scroll', handleScroll, { passive: true })

    updateScrollProgress()
    updateActiveToc()
  }

  function handleScroll() {
    updateScrollProgress()
    updateActiveToc()
  }

  function updateScrollProgress() {
    if (!shadowRoot.value || !scrollParent) return

    let scrollTop, scrollHeight, clientHeight

    if (scrollParent === window) {
      scrollTop = window.scrollY || document.documentElement.scrollTop
      scrollHeight = document.documentElement.scrollHeight
      clientHeight = window.innerHeight
    } else {
      scrollTop = scrollParent.scrollTop
      scrollHeight = scrollParent.scrollHeight
      clientHeight = scrollParent.clientHeight
    }

    const scrollableHeight = scrollHeight - clientHeight
    const progress = scrollableHeight > 0 ? (scrollTop / scrollableHeight) * 100 : 0
    scrollProgress.value = Math.min(100, Math.max(0, progress))
  }

  function updateActiveToc() {
    if (!shadowRoot.value || tocItems.value.length === 0 || !scrollParent) return

    let containerTop = 0
    if (scrollParent !== window) {
      containerTop = scrollParent.getBoundingClientRect().top
    }

    let currentId = ''
    let minDistance = Infinity

    for (const item of tocItems.value) {
      const el = shadowRoot.value.getElementById(item.id)
      if (!el) continue

      const rect = el.getBoundingClientRect()
      const distanceToTop = Math.abs(rect.top - containerTop)

      if (rect.top <= containerTop + 100 && distanceToTop < minDistance) {
        minDistance = distanceToTop
        currentId = item.id
      }
    }

    if (!currentId) {
      for (const item of tocItems.value) {
        const el = shadowRoot.value.getElementById(item.id)
        if (!el) continue

        const rect = el.getBoundingClientRect()
        let isVisible = false
        if (scrollParent === window) {
          isVisible = rect.top >= 0 && rect.top < window.innerHeight
        } else {
          const containerRect = scrollParent.getBoundingClientRect()
          isVisible = rect.top >= containerRect.top && rect.top < containerRect.bottom
        }

        if (isVisible) {
          currentId = item.id
          break
        }
      }
    }

    if (!currentId && tocItems.value.length > 0) {
      currentId = tocItems.value[tocItems.value.length - 1].id
    }

    activeTocId.value = currentId
  }

  function scrollToHeading(id) {
    if (!shadowRoot.value) return

    const el = shadowRoot.value.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  // ==================== 生命周期 ====================
  onMounted(() => {
    initShadowRoot()
    if (props.isSecret && hasValidKey.value && props.content && props.noteId) {
      decryptNoteContent()
    }
  })

  onUnmounted(() => {
    if (scrollParent) {
      scrollParent.removeEventListener('scroll', handleScroll)
    } else {
      window.removeEventListener('scroll', handleScroll)
    }
    shadowRoot.value = null
  })

  // ==================== 监听器 ====================
  watch(() => props.content, () => {
    if (!shadowRoot.value && hostRef.value) {
      initShadowRoot()
    }

    if (props.isSecret && hasValidKey.value && props.content && props.noteId) {
      decryptNoteContent()
    } else {
      renderContent(false)
    }
  })

  watch(() => props.noteId, () => {
    decryptedContent.value = ''
    decryptError.value = ''
    hasRequestedVaultUnlock.value = false

    if (props.isSecret && hasValidKey.value && props.content && props.noteId) {
      decryptNoteContent()
    } else {
      renderContent(false)
    }
  })

  watch(() => hasValidKey.value, (valid) => {
    if (valid && props.isSecret && props.content && props.noteId && !decryptedContent.value) {
      decryptNoteContent()
    } else if (!valid && props.isSecret) {
      decryptedContent.value = ''
      renderContent(false)
    }
  })

  watch(() => props.isTrashed, () => {
    decryptedContent.value = ''
    decryptError.value = ''
    renderContent(false)
  })

  watch(() => decryptedContent.value, () => {
    if (props.isSecret && !isDecrypting.value) {
      renderContent(false)
    }
  })

  watch(() => props.toc, (newToc) => {
    tocItems.value = newToc || []
    showToc.value = tocItems.value.length >= TOC_THRESHOLD
  }, { deep: true })

  watch(() => props.isDark, () => {
    if (shadowRoot.value) {
      renderContent(true)
    }
  })

  // ==================== 返回 ====================
  return {
    hostRef,
    showToc,
    tocItems,
    activeTocId,
    scrollProgress,
    scrollToHeading
  }
}
