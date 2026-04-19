import { ref, watch, onMounted, nextTick, computed } from 'vue'
import DOMPurify from 'dompurify'
import { useCodeEnhancer } from './useCodeEnhancer'
import { useClientCrypto } from './useClientCrypto'
import { useVaultStore } from '@/stores/vault'

/**
 * NoteViewer 组件的业务逻辑
 * @param {Object} props - 组件 props
 * @returns {Object} 组件所需的状态和方法
 */
export function useNoteViewer(props) {
  const contentRef = ref(null)
  const isDecrypting = ref(false)
  const decryptError = ref('')
  const decryptedContent = ref('')

  // 使用加密组合式
  const vaultStore = useVaultStore()
  const isKeyValid = computed(() => vaultStore.isUnlocked)
  const { decryptContent: decryptClientContent } = useClientCrypto()

  // 使用代码块增强功能
  const { enhance: enhanceCodeBlocks } = useCodeEnhancer()

  // 配置 DOMPurify
  const purifyConfig = {
    FORBID_TAGS: ['script', 'style', 'link', 'meta', 'iframe', 'object', 'embed', 'frame', 'frameset'],
    FORBID_ATTR: ['onerror', 'onclick', 'onmouseover', 'onload', 'onmouseenter', 'onfocus', 'onblur'],
    ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|data):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
  }

  /**
   * 计算属性：响应式解密内容
   */
  const displayContent = computed(() => {
    if (!props.isSecret) {
      return props.content
    }
    if (isKeyValid.value) {
      return decryptedContent.value
    }
    return ''
  })

  /**
   * 移除所有 class 和 id 属性，防止外部样式影响布局
   */
  const stripClassAndId = (html) => {
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    const baseUrl = window.location.origin + '/'

    doc.querySelectorAll('*').forEach(el => {
      el.removeAttribute('class')
      el.removeAttribute('id')

      if (el.tagName === 'IMG') {
        const src = el.getAttribute('src')
        if (src && !src.match(/^https?:\/\//) && !src.match(/^\/\//)) {
          if (src.startsWith('./') || src.startsWith('../')) {
            el.setAttribute('src', new URL(src, baseUrl).href)
          } else if (!src.match(/^[a-zA-Z][a-zA-Z0-9+.-]*:/)) {
            el.setAttribute('src', baseUrl + src.replace(/^\//, ''))
          }
        }
      }

      const style = el.getAttribute('style')
      if (style) {
        const dangerousPatterns = [
          /position\s*:/gi,
          /display\s*:\s*(flex|grid|none)/gi,
          /float\s*:/gi,
          /z-index\s*:/gi,
          /fixed/gi,
          /absolute/gi,
          /transform\s*:/gi,
          /left\s*:/gi,
          /right\s*:/gi,
          /top\s*:/gi,
          /bottom\s*:/gi,
          /width\s*:\s*\d+vw/gi,
          /height\s*:\s*\d+vh/gi,
        ]
        let cleanStyle = style
        dangerousPatterns.forEach(pattern => {
          cleanStyle = cleanStyle.replace(pattern, '')
        })
        cleanStyle = cleanStyle.replace(/;\s*;/g, ';').replace(/^\s*;|;\s*$/g, '').trim()
        if (cleanStyle) {
          el.setAttribute('style', cleanStyle)
        } else {
          el.removeAttribute('style')
        }
      }
    })

    return doc.body.innerHTML
  }

  const getSanitizedContent = (content) => {
    if (!content) return ''
    const cleanHTML = DOMPurify.sanitize(content, purifyConfig)
    const strippedHTML = stripClassAndId(cleanHTML)
    return strippedHTML
  }

  const renderContent = (content) => {
    if (!contentRef.value) {
      return
    }

    try {
      contentRef.value.innerHTML = getSanitizedContent(content)
    } catch (e) {
      return
    }

    nextTick(() => {
      if (!contentRef.value) {
        return
      }

      try {
        enhanceCodeBlocks(contentRef.value)
      } catch (e) {
        // enhancement error
      }
    })
  }

  /**
   * 解密加密笔记的内容
   */
  let latestDecryptRequestId = 0
  async function decryptContent() {
    if (!props.isSecret || !props.content || !props.noteId) {
      return
    }

    if (!vaultStore.isUnlocked) {
      decryptError.value = '未能获取解密密钥，请进行 2FA 验证'
      return
    }

    const requestId = ++latestDecryptRequestId
    const capturedNoteId = props.noteId
    const capturedContent = props.content

    isDecrypting.value = true
    decryptError.value = ''

    try {
      const plaintext = await decryptClientContent(capturedContent)
      if (requestId !== latestDecryptRequestId || capturedNoteId !== props.noteId) return
      decryptedContent.value = plaintext
      renderContent(plaintext)
    } catch (e) {
      if (requestId !== latestDecryptRequestId || capturedNoteId !== props.noteId) return
      decryptError.value = '解密失败: ' + e.message
      decryptedContent.value = ''
    } finally {
      if (requestId === latestDecryptRequestId) {
        isDecrypting.value = false
      }
    }
  }

  // 生命周期
  onMounted(() => {
    if (!props.isSecret) {
      renderContent(props.content)
    } else if (isKeyValid.value) {
      decryptContent()
    }
  })

  // 监听 displayContent 变化
  watch(() => displayContent.value, (newContent) => {
    if (newContent) {
      renderContent(newContent)
    }
  })

  // 监听 isKeyValid 变化
  watch(() => isKeyValid.value, (valid) => {
    if (valid && props.isSecret && props.content && !decryptedContent.value) {
      decryptContent()
    } else if (!valid && props.isSecret) {
      // 锁定时立即清明文
      decryptedContent.value = ''
    }
  })

  // 监听 content 变化
  watch(() => props.content, (newContent) => {
    if (newContent && props.isSecret && isKeyValid.value) {
      decryptContent()
    }
  })

  return {
    contentRef,
    isDecrypting,
    decryptError,
    decryptedContent,
    isKeyValid,
    displayContent,
    renderContent,
    decryptContent
  }
}
