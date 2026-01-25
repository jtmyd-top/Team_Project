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
  }
})

const hostRef = ref(null)
const shadowRoot = ref(null)

// 使用代码块增强功能
const { enhance: enhanceCodeBlocks } = useCodeEnhancer()

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

  const rawHtml = props.content || ''

  if (rawHtml !== cachedRawHtml) {
    cachedRawHtml = rawHtml

    // 使用后端生成的目录数据
    cachedCleanHtml = DOMPurify.sanitize(rawHtml, purifyConfig)

    // 使用后端提供的 TOC 数据
    tocItems.value = props.toc || []

    // 阈值判断：至少3个标题才显示目录
    showToc.value = tocItems.value.length >= TOC_THRESHOLD
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
    // 确保内容元素存在后再增强
    const contentEl = shadowRoot.value?.querySelector('.note-content')
    if (contentEl) {
      setupScrollSpy()
      // 使用 composable 增强代码块（支持 Shadow DOM）
      enhanceCodeBlocks(shadowRoot.value.querySelector('.note-content'))
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
})

// 监听内容变化
watch(() => props.content, () => {
  if (!shadowRoot.value && hostRef.value) {
    initShadowRoot()
  } else {
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
