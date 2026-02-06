/**
 * NoteShadowViewer 逻辑层
 * 处理 Shadow DOM 渲染、内容解密、目录滚动等功能
 */

import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import DOMPurify from 'dompurify'
import { useCodeEnhancer } from '@composables/useCodeEnhancer'
import { useVaultEncryption } from '@composables/useVaultEncryption'
import { useClientCrypto } from '@composables/useClientCrypto'
import { useVaultStore } from '@/stores/vault'
import { getShadowStyles, purifyConfig, TOC_THRESHOLD } from '@/components/knowledge/NoteShadowViewer/config.js'

export function useNoteShadowViewer(props) {
  // ==================== Refs ====================
  const hostRef = ref(null)
  const shadowRoot = ref(null)

  // ==================== Composables ====================
  const { enhance: enhanceCodeBlocks } = useCodeEnhancer()
  const { isKeyValid, dek } = useVaultEncryption()
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
  const hasAnyValidDek = computed(() => !!(dek.value || vaultStore.dek))

  const displayContent = computed(() => {
    if (!props.isSecret) {
      return props.content
    }

    if (!hasAnyValidDek.value) {
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
  async function decryptNoteContent() {
    if (!props.isSecret || !props.content) {
      return
    }

    console.log('[Vault] Starting decryption process...', {
      isSecret: props.isSecret,
      isTrashed: props.isTrashed,
      contentLength: props.content?.length || 0,
      hasKeyValid: !!isKeyValid.value,
      hasDek: !!dek.value,
      hasVaultDek: !!vaultStore.dek
    })

    if (!looksLikeEncrypted(props.content)) {
      console.warn('[Vault] Content does not look like encrypted data, treating as plaintext')
      decryptedContent.value = props.content
      return
    }

    isDecrypting.value = true
    decryptError.value = ''

    try {
      const dekToUse = dek.value || vaultStore.dek

      if (!dekToUse) {
        console.error('[Vault] No DEK available for decryption')
        decryptError.value = '缺少加密密钥，请重新验证'
        return
      }

      const plaintext = decryptContent(props.content, dekToUse)
      decryptedContent.value = plaintext

      console.log('[Vault] Content decrypted successfully')
    } catch (e) {
      console.error('[Vault] 前端解密失败:', e)
      decryptError.value = '解密失败：' + e.message
    } finally {
      isDecrypting.value = false
    }
  }

  // ==================== Shadow DOM 渲染 ====================
  function renderContent(forceStyleUpdate = false) {
    if (!shadowRoot.value) return

    const rawHtml = displayContent.value || ''
    const hasValidDek = !!(dek.value || vaultStore.dek)
    const needsVerification = props.isSecret && !hasValidDek
    const shouldUpdate = rawHtml !== cachedRawHtml || needsVerification || forceStyleUpdate

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
        cachedCleanHtml = DOMPurify.sanitize(rawHtml, purifyConfig)
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

    nextTick(() => {
      if (!shadowRoot.value) return

      const contentEl = shadowRoot.value.querySelector('.note-content')
      if (!contentEl) return

      try {
        setupScrollSpy()
        enhanceCodeBlocks(contentEl)
      } catch (e) {
        console.warn('Error enhancing code blocks:', e)
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
    if (props.isSecret && isKeyValid.value && props.content && props.noteId) {
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

    if (props.isSecret && isKeyValid.value && props.content && props.noteId) {
      decryptNoteContent()
    } else {
      renderContent(false)
    }
  })

  watch(() => props.noteId, () => {
    decryptedContent.value = ''
    decryptError.value = ''
    hasRequestedVaultUnlock.value = false

    if (props.isSecret && isKeyValid.value && props.content && props.noteId) {
      decryptNoteContent()
    } else {
      renderContent(false)
    }
  })

  watch(() => isKeyValid.value, (valid) => {
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
