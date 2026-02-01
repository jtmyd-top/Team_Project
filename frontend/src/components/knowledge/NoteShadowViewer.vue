<template>
  <div class="note-viewer-container" :class="{ 'has-toc': showToc }">
    <!-- 阅读进度条 -->
    <div v-if="showToc" class="reading-progress-bar" :style="{ width: scrollProgress + '%' }"></div>

    <!-- 主内容区 -->
    <div ref="hostRef" class="shadow-host"></div>

    <!-- 目录侧边栏（阈值触发显示） -->
    <Transition name="slide-in">
      <aside v-if="showToc" class="note-toc">
        <div class="toc-sticky">
          <h3>目录</h3>
          <ul class="toc-list">
            <li
              v-for="item in tocItems"
              :key="item.id"
              :class="['toc-item', `toc-level-${item.level}`, { 'active': activeTocId === item.id }]"
              @click="scrollToHeading(item.id)"
            >
              {{ item.text }}
            </li>
          </ul>
        </div>
      </aside>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick, onUnmounted, computed } from 'vue'
import DOMPurify from 'dompurify'
import { useCodeEnhancer, getCodeEnhancerStyles } from '@composables/useCodeEnhancer'
import { useVaultEncryption } from '@composables/useVaultEncryption'
import { useClientCrypto } from '@composables/useClientCrypto'
import { useVaultStore } from '@/stores/vault'

const props = defineProps({
  content: {
    type: String,
    default: ''
  },
  toc: {
    type: Array,
    default: () => []
  },
  isDark: {
    type: Boolean,
    default: false
  },
  isSecret: {
    type: Boolean,
    default: false
  },
  isTrashed: {
    type: Boolean,
    default: false
  },
  noteId: {
    type: Number,
    default: null
  }
})

const hostRef = ref(null)
const shadowRoot = ref(null)

// 使用代码块增强功能
const { enhance: enhanceCodeBlocks } = useCodeEnhancer()

// 获取加密/解密相关
const { isKeyValid, dek } = useVaultEncryption()
const { decryptContent, looksLikeEncrypted } = useClientCrypto()

// 获取 vaultStore 用于访问全局 DEK
const vaultStore = useVaultStore()

// 【新增】标记是否已请求过 2FA 验证（防止重复请求）
const hasRequestedVaultUnlock = ref(false)

// 【新增】计算属性：检查是否有任何可用的 DEK
const hasAnyValidDek = computed(() => {
  return !!(dek.value || vaultStore.dek)
})

// 加密相关状态
const isDecrypting = ref(false)
const decryptError = ref('')
const decryptedContent = ref('')

// 计算属性：响应式解密内容
const displayContent = computed(() => {
  // 【修复】回收站中的保密笔记处理逻辑
  // 不再阻止解密，允许正常笔记直接显示，保密笔记在 2FA 验证后显示
  if (!props.isSecret) {
    // 普通笔记（包括回收站中的），直接返回原内容
    return props.content
  }

  // 保密笔记需要检查是否已解锁（检查所有 DEK 源）
  if (!hasAnyValidDek.value) {
    // 加密笔记未解锁 - 返回空字符串，让 renderContent 处理显示
    return ''
  }

  // 如果已解密，返回解密内容；否则返回密文（稍后会被解密）
  if (decryptedContent.value) {
    return decryptedContent.value
  }

  // 如果正在解密，显示占位符
  if (isDecrypting.value) {
    return ''
  }

  // 如果解密失败，返回错误提示
  if (decryptError.value) {
    return ''
  }

  // 返回原始内容（可能是密文，等待解密）
  return props.content
})

// 前端解密加密笔记
async function decryptNoteContent() {
  // 【修复】回收站中的保密笔记也可以解密（在完成 2FA 后）
  if (!props.isSecret || !props.content) {
    return
  }

  console.log('[Vault] Starting decryption process...', {
    isSecret: props.isSecret,
    isTrashed: props.isTrashed,
    contentLength: props.content?.length || 0,
    contentSample: props.content?.substring(0, 30),
    hasKeyValid: !!isKeyValid.value,
    hasDek: !!dek.value,
    hasVaultDek: !!vaultStore.dek
  })

  // 如果内容看起来不像密文，跳过解密
  if (!looksLikeEncrypted(props.content)) {
    console.warn('[Vault] Content does not look like encrypted data, treating as plaintext')
    decryptedContent.value = props.content
    return
  }

  isDecrypting.value = true
  decryptError.value = ''

  try {
    // 【修复】使用双重 DEK 源
    const dekToUse = dek.value || vaultStore.dek

    // 获取用户的 DEK（Data Encryption Key，来自 2FA 验证）
    if (!dekToUse) {
      console.error('[Vault] No DEK available for decryption, user needs to verify 2FA')
      decryptError.value = '缺少加密密钥，请重新验证'
      return
    }

    console.log('[Vault] DEK available, decrypting...', {
      dekLength: dekToUse?.length || 0,
      dekSample: dekToUse?.substring(0, 20)
    })

    // 前端解密：在浏览器中使用 DEK 解密
    // 新的 useClientCrypto 已经是 Python 兼容格式
    // 可以解密旧的迁移数据和新的加密数据
    const plaintext = decryptContent(props.content, dekToUse)
    decryptedContent.value = plaintext

    console.log('[Vault] Content decrypted successfully in browser', {
      decryptedLength: plaintext?.length || 0,
      decryptedSample: plaintext?.substring(0, 50)
    })
  } catch (e) {
    console.error('[Vault] 前端解密失败:', e, {
      message: e.message,
      contentLength: props.content?.length,
      dekLength: dekToUse?.length
    })
    decryptError.value = '解密失败：' + e.message
  } finally {
    isDecrypting.value = false
  }
}

// 目录相关状态
const tocItems = ref([])
const showToc = ref(false)
const activeTocId = ref('')
const scrollProgress = ref(0)

// 阈值：至少3个标题才显示目录
const TOC_THRESHOLD = 3

// Shadow DOM 内部的基础样式
const getShadowStyles = (isDark) => `
  :host {
    display: block;
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
    overflow: hidden;
  }

  .note-content {
    line-height: 1.8;
    color: ${isDark ? '#e0e0e0' : '#333'};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    word-wrap: break-word;
    overflow-wrap: anywhere;
    font-size: 16px;
    max-width: 100%;
    width: 100%;
    box-sizing: border-box;
    scroll-behavior: smooth;
    overflow-x: hidden; /* 防止内容溢出容器 */
  }

  /* 【新增】回收站中保密笔记的锁定提示样式 */
  .vault-trash-locked-notice {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 40px;
    text-align: center;
    background: ${isDark ? 'rgba(255,255,255,0.02)' : 'rgba(240, 112, 112, 0.05)'};
    border-radius: 8px;
    border: 1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(240, 112, 112, 0.2)'};
    min-height: 300px;
  }

  .vault-trash-locked-notice .notice-icon {
    font-size: 64px;
    margin-bottom: 20px;
    animation: bounce 2s infinite;
  }

  @keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
  }

  .vault-trash-locked-notice .notice-title {
    font-size: 24px;
    font-weight: 600;
    color: ${isDark ? '#e0e0e0' : '#333'};
    margin-bottom: 12px;
  }

  .vault-trash-locked-notice .notice-message {
    font-size: 16px;
    color: ${isDark ? '#999' : '#666'};
    margin-bottom: 8px;
    line-height: 1.6;
  }

  .vault-trash-locked-notice .notice-hint {
    font-size: 14px;
    color: ${isDark ? '#777' : '#999'};
    font-style: italic;
    margin-top: 16px;
  }

  /* 标题 - 添加 scroll-margin-top 使锚点跳转时不被顶部遮挡 */
  .note-content h1 {
    font-size: 1.8em;
    font-weight: 600;
    margin: 1em 0 0.5em;
    line-height: 1.3;
    color: ${isDark ? '#fff' : '#1a1a1a'};
    scroll-margin-top: 20px;
  }
  .note-content h2 {
    font-size: 1.5em;
    font-weight: 600;
    margin: 1em 0 0.5em;
    line-height: 1.35;
    color: ${isDark ? '#fff' : '#1a1a1a'};
    scroll-margin-top: 20px;
  }
  .note-content h3 {
    font-size: 1.25em;
    font-weight: 600;
    margin: 1em 0 0.5em;
    line-height: 1.4;
    color: ${isDark ? '#fff' : '#1a1a1a'};
    scroll-margin-top: 20px;
  }
  .note-content h4, .note-content h5, .note-content h6 {
    font-size: 1.1em;
    font-weight: 600;
    margin: 1em 0 0.5em;
    color: ${isDark ? '#fff' : '#1a1a1a'};
    scroll-margin-top: 20px;
  }

  /* 段落 */
  .note-content p { margin: 1em 0; line-height: 1.8; }

  /* 链接 */
  .note-content a { color: #409eff; text-decoration: none; }
  .note-content a:hover { text-decoration: underline; }

  /* 列表 */
  .note-content ul, .note-content ol { margin: 1em 0; padding-left: 2em; }
  .note-content li { margin: 0.5em 0; line-height: 1.6; }

  /* 图片 */
  .note-content img {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    display: block;
    margin: 1em 0;
  }

  /* 代码 */
  .note-content code {
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    background: ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)'};
    padding: 0.2em 0.4em;
    border-radius: 3px;
    font-size: 0.9em;
  }

  .note-content pre {
    background: ${isDark ? '#2d2d2d' : '#f5f5f5'};
    padding: 1em;
    border-radius: 8px;
    overflow-x: auto;
    margin: 1em 0;
    position: relative;
    max-width: 100%;
    box-sizing: border-box;
  }

  .note-content pre code {
    background: transparent;
    padding: 0;
  }

  /* 代码块增强样式（来自 composable） */
  ${getCodeEnhancerStyles(isDark)}

  /* 引用块 */
  .note-content blockquote {
    border-left: 4px solid #409eff;
    margin: 1em 0;
    padding: 0.5em 1em;
    background: ${isDark ? 'rgba(64, 158, 255, 0.1)' : 'rgba(64, 158, 255, 0.05)'};
    border-radius: 0 4px 4px 0;
  }

  .note-content blockquote p { margin: 0.5em 0; }

  /* 表格 */
  .note-content table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
  }

  .note-content th, .note-content td {
    border: 1px solid ${isDark ? '#444' : '#e0e0e0'};
    padding: 0.75em 1em;
    text-align: left;
  }

  .note-content th {
    background: ${isDark ? '#333' : '#f5f5f5'};
    font-weight: 600;
  }

  /* 分割线 */
  .note-content hr {
    margin: 2em 0;
    border: none;
    border-top: 1px solid ${isDark ? '#444' : '#e0e0e0'};
  }

  /* 强调 */
  .note-content strong, .note-content b { font-weight: 600; }
  .note-content em, .note-content i { font-style: italic; }

  /* 高亮 */
  .note-content mark {
    background: rgba(255, 230, 0, 0.4);
    padding: 0.1em 0.2em;
    border-radius: 2px;
  }

  /* 按钮样式重置 */
  .note-content button {
    display: inline-block;
    padding: 0.5em 1em;
    background: ${isDark ? '#444' : '#f0f0f0'};
    border: 1px solid ${isDark ? '#555' : '#d0d0d0'};
    border-radius: 4px;
    cursor: pointer;
    font-size: inherit;
    color: inherit;
  }

  /* 防止 fixed 定位溢出 */
  .note-content {
    contain: layout style;
  }

  /* 限制可能的绝对/固定定位元素 */
  .note-content [style*="position: fixed"],
  .note-content [style*="position:fixed"] {
    position: relative !important;
  }
`

// 清洗配置
const purifyConfig = {
  FORBID_TAGS: ['script', 'iframe', 'frame', 'object', 'embed', 'form', 'meta', 'link'],
  FORBID_ATTR: ['onerror', 'onclick', 'onmouseover', 'onload', 'onmouseenter', 'onfocus', 'onblur', 'onsubmit'],
  ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|data):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
}

// 处理内容：给标题添加 ID，并提取目录
const processContent = (html) => {
  if (!html) return { processedHtml: html, tocItems: [] }

  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')

  const headers = doc.querySelectorAll('h1, h2, h3')
  const tocItems = []

  headers.forEach((header, index) => {
    // 如果没有 ID，生成一个
    if (!header.id) {
      header.id = `heading-${Date.now()}-${index}`
    }

    tocItems.push({
      id: header.id,
      text: header.textContent.trim() || `标题 ${index + 1}`,
      level: parseInt(header.tagName.substring(1))
    })
  })

  return {
    processedHtml: doc.body.innerHTML,
    tocItems
  }
}

// 缓存
let cachedRawHtml = ''
let cachedCleanHtml = ''

const renderContent = (forceStyleUpdate = false) => {
  if (!shadowRoot.value) return

  // 使用 displayContent 而不是 props.content，这样可以自动处理解密
  const rawHtml = displayContent.value || ''

  // 【修复】检查 DEK 是否可用（包括 dek 和 vaultStore.dek）
  const hasValidDek = !!(dek.value || vaultStore.dek)
  const needsVerification = props.isSecret && !hasValidDek

  // 【修复】强制更新：当需要验证时，即使内容相同也要重新渲染
  const shouldUpdate = rawHtml !== cachedRawHtml || needsVerification || forceStyleUpdate

  if (shouldUpdate) {
    cachedRawHtml = rawHtml

    // 【修改】回收站中的笔记处理逻辑
    if (needsVerification) {
      // 保密笔记 + 未解锁：显示需要验证的提示
      cachedCleanHtml = '<div style="padding: 20px; text-align: center; color: #999;">🔒 保密笔记，请完成 2FA 验证后查看内容。</div>'
      tocItems.value = []
      showToc.value = false

      // 【新增】请求打开 2FA 验证弹窗（仅请求一次）
      if (!hasRequestedVaultUnlock.value) {
        console.log('[NoteShadowViewer] Requesting vault unlock for secret note:', props.noteId, 'hasValidDek:', hasValidDek)
        hasRequestedVaultUnlock.value = true
        window.dispatchEvent(new CustomEvent('open-vault-unlock-dialog', {
          detail: { fromTrash: props.isTrashed, noteId: props.noteId }
        }))
      }
    } else if (props.isSecret && isDecrypting.value) {
      // 解密中的状态
      cachedCleanHtml = '<div style="padding: 20px; text-align: center; color: #999;">解密中，请稍候...</div>'
      tocItems.value = []
      showToc.value = false
    } else if (decryptError.value) {
      // 解密错误
      cachedCleanHtml = `<div style="padding: 20px; color: #ff0000;">${decryptError.value}</div>`
      tocItems.value = []
      showToc.value = false
    } else {
      // 正常内容渲染（包括已解锁的保密笔记、回收站中的正常笔记）
      cachedCleanHtml = DOMPurify.sanitize(rawHtml, purifyConfig)

      // 使用后端提供的 TOC 数据
      tocItems.value = props.toc || []

      // 阈值判断：至少3个标题才显示目录
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

// 渲染后设置滚动监听和代码块增强功能
  nextTick(() => {
    // 双重检查：确保 shadowRoot 和 contentEl 都存在后再操作
    if (!shadowRoot.value) {
      console.warn('shadowRoot has been cleared')
      return
    }

    const contentEl = shadowRoot.value.querySelector('.note-content')
    if (!contentEl) {
      console.warn('content element not found in shadow DOM')
      return
    }

    try {
      setupScrollSpy()
      // 使用 composable 增强代码块（支持 Shadow DOM）
      enhanceCodeBlocks(contentEl)  // 直接传 contentEl，而不是重新查询
    } catch (e) {
      console.warn('Error enhancing code blocks:', e)
    }
  })
}

const initShadowRoot = () => {
  if (hostRef.value && !shadowRoot.value) {
    shadowRoot.value = hostRef.value.attachShadow({ mode: 'open' })
    renderContent()
  }
}

// 查找可滚动父元素
const getScrollParent = (node) => {
  if (node == null) return null
  if (node.scrollHeight > node.clientHeight && 
      (getComputedStyle(node).overflowY === 'auto' || getComputedStyle(node).overflowY === 'scroll')) {
    return node
  }
  return getScrollParent(node.parentNode) || window
}

let scrollParent = null

// 滚动高亮和进度条
const setupScrollSpy = () => {
  if (!shadowRoot.value) return

  const contentEl = shadowRoot.value.querySelector('.note-content')
  if (!contentEl) return

  // 查找滚动父元素
  scrollParent = getScrollParent(hostRef.value)
  
  // 监听滚动事件
  scrollParent.addEventListener('scroll', handleScroll, { passive: true })

  // 初始化进度条
  updateScrollProgress()
  updateActiveToc()
}

// 滚动事件处理器
const handleScroll = () => {
  updateScrollProgress()
  updateActiveToc()
}

const updateScrollProgress = () => {
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

const updateActiveToc = () => {
  if (!shadowRoot.value || tocItems.value.length === 0 || !scrollParent) return

  // 获取视口/容器的顶部位置
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
    // 计算相对于容器顶部的距离
    // 注意：getBoundingClientRect 返回的是相对于视口的坐标
    // 如果在容器内滚动，我们需要比较 rect.top 和 containerTop
    const distanceToTop = Math.abs(rect.top - containerTop)

    // 如果标题接近容器顶部
    if (rect.top <= containerTop + 100 && distanceToTop < minDistance) {
      minDistance = distanceToTop
      currentId = item.id
    }
  }
  
  // 如果上面的逻辑没找到（比如都在下面），尝试找第一个可见的
  if (!currentId) {
    for (const item of tocItems.value) {
      const el = shadowRoot.value.getElementById(item.id)
      if (!el) continue
      
      const rect = el.getBoundingClientRect()
      // 判断是否在可视区域内
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

  // 如果还是没有，使用最后一个
  if (!currentId && tocItems.value.length > 0) {
    currentId = tocItems.value[tocItems.value.length - 1].id
  }

  activeTocId.value = currentId
}

// 滚动到指定标题
const scrollToHeading = (id) => {
  if (!shadowRoot.value) return

  const el = shadowRoot.value.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

onMounted(() => {
  initShadowRoot()
  // 如果是加密笔记且已解锁，立即解密（包括回收站中的笔记）
  if (props.isSecret && isKeyValid.value && props.content && props.noteId) {
    decryptNoteContent()
  }
})

// 监听内容变化
watch(() => props.content, () => {
  if (!shadowRoot.value && hostRef.value) {
    initShadowRoot()
  }

  // 如果是加密笔记且已解锁，重新解密（包括回收站中的笔记）
  if (props.isSecret && isKeyValid.value && props.content && props.noteId) {
    decryptNoteContent()
  } else {
    renderContent(false)
  }
})

// 监听笔记 ID 变化（切换笔记时重置解密状态）
watch(() => props.noteId, () => {
  decryptedContent.value = ''
  decryptError.value = ''
  hasRequestedVaultUnlock.value = false // 重置标记，允许新笔记请求 2FA

  if (props.isSecret && isKeyValid.value && props.content && props.noteId) {
    decryptNoteContent()
  } else {
    renderContent(false)
  }
})

// 监听密钥状态：保险柜解锁时自动解密（包括回收站中的笔记）
watch(() => isKeyValid.value, (valid) => {
  if (valid && props.isSecret && props.content && props.noteId && !decryptedContent.value) {
    decryptNoteContent()
  } else if (!valid && props.isSecret) {
    // 密钥失效，清除解密内容
    decryptedContent.value = ''
    renderContent(false)
  }
})

// 【新增】监听回收站状态变化
watch(() => props.isTrashed, () => {
  // 如果笔记被移入/移出回收站，重新渲染
  decryptedContent.value = ''
  decryptError.value = ''
  renderContent(false)
})

// 监听解密结果：内容解密完成后重新渲染
watch(() => decryptedContent.value, () => {
  if (props.isSecret && !isDecrypting.value) {
    renderContent(false)
  }
})

// 监听后端 TOC 数据变化
watch(() => props.toc, (newToc) => {
  tocItems.value = newToc || []
  showToc.value = tocItems.value.length >= TOC_THRESHOLD
}, { deep: true })

// 监听主题变化
watch(() => props.isDark, () => {
  if (shadowRoot.value) {
    renderContent(true)
  }
})

// 组件卸载时清理
onUnmounted(() => {
  if (scrollParent) {
    scrollParent.removeEventListener('scroll', handleScroll)
  } else {
    window.removeEventListener('scroll', handleScroll)
  }
  shadowRoot.value = null
})
</script>

<style scoped>
/* 容器布局 */
.note-viewer-container {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  display: flex;
  justify-content: center;
  position: relative;
  overflow-x: hidden; /* 防止内容溢出 */
}

/* 简单笔记模式：内容居中，无侧边栏 */
.shadow-host {
  width: 100%;
  max-width: 800px;
  min-width: 0; /* 防止 flex 子元素溢出 */
  box-sizing: border-box;
  overflow-x: hidden; /* 防止内容溢出 */
  transition: max-width 0.3s ease;
}

/* 复杂文档模式：显示目录，内容左移 */
.note-viewer-container.has-toc {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px; /* minmax(0, 1fr) 防止内容溢出 */
  gap: 30px;
  max-width: 100%;
  padding: 0;
}

.note-viewer-container.has-toc .shadow-host {
  max-width: 100%;
  min-width: 0; /* 防止 grid 子元素溢出 */
}

/* 阅读进度条 */
.reading-progress-bar {
  position: fixed;
  top: 0;
  left: 0;
  height: 3px;
  background: linear-gradient(90deg, #409eff, #67c23a);
  z-index: 1000;
  transition: width 0.1s ease-out;
}

/* 目录侧边栏 */
.note-toc {
  position: relative;
}

.note-toc h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  color: v-bind(isDark ? '#e0e0e0' : '#333');
}

.toc-sticky {
  position: sticky;
  top: 20px;
  max-height: calc(100vh - 40px);
  overflow-y: auto;
}

.toc-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.toc-item {
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s ease;
  font-size: 14px;
  color: v-bind(isDark ? '#999' : '#666');
  line-height: 1.5;
}

.toc-item:hover {
  background-color: v-bind(isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)');
  color: v-bind(isDark ? '#409eff' : '#409eff');
}

.toc-item.active {
  background-color: v-bind(isDark ? 'rgba(64, 158, 255, 0.1)' : 'rgba(64, 158, 255, 0.1)');
  color: #409eff;
  font-weight: 500;
}

.toc-level-1 {
  font-weight: 600;
  margin-top: 4px;
}

.toc-level-2 {
  margin-left: 16px;
  font-size: 0.9em;
}

.toc-level-3 {
  margin-left: 32px;
  font-size: 0.85em;
}

/* 目录滑入动画 */
.slide-in-enter-active,
.slide-in-leave-active {
  transition: all 0.3s ease;
}

.slide-in-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.slide-in-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

/* 响应式：窄屏时隐藏目录 */
@media (max-width: 1100px) {
  .note-viewer-container.has-toc {
    grid-template-columns: 1fr;
  }

  .note-toc {
    display: none;
  }
}

/* 更窄的屏幕优化内容区 */
@media (max-width: 768px) {
  .shadow-host {
    max-width: 100%;
  }

  .note-viewer-container.has-toc {
    gap: 0;
    padding: 0;
  }
}
</style>
