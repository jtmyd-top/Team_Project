/**
 * useCodeEnhancer - 代码块增强功能
 *
 * 为代码块添加复制和折叠功能
 * 统一了 NoteViewer.vue 和 NoteShadowViewer.vue 中的重复逻辑
 */

// SVG 图标常量
const ICONS = {
  copy: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
  </svg>`,

  copied: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="20 6 9 17 4 12"></polyline>
  </svg>`,

  expand: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="6 9 12 15 18 9"></polyline>
  </svg>`
}

// 默认配置
const DEFAULT_OPTIONS = {
  // 超过多少行才显示折叠按钮
  collapseThreshold: 5,
  // 是否默认折叠长代码
  defaultCollapsed: true,
  // 复制成功后的提示持续时间(ms)
  copiedDuration: 2000,
  // 增强标记类名
  enhancedClass: 'code-block-enhanced',
  // 长代码类名
  longCodeClass: 'long-code',
  // 折叠状态类名
  collapsedClass: 'collapsed'
}

/**
 * 复制文本到剪贴板
 * @param {string} text - 要复制的文本
 * @returns {Promise<boolean>} - 是否成功
 */
async function copyToClipboard(text) {
  // 方法1: 使用 Clipboard API
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch (err) {
      console.warn('Clipboard API 失败，尝试备用方法:', err)
    }
  }

  // 方法2: 使用 execCommand (备用)
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.left = '-999999px'
    textarea.style.top = '-999999px'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()

    const successful = document.execCommand('copy')
    document.body.removeChild(textarea)
    return successful
  } catch (err) {
    console.error('复制失败:', err)
    return false
  }
}

/**
 * 计算代码块行数
 * @param {HTMLElement} codeEl - code 元素
 * @returns {number} - 行数
 */
function countLines(codeEl) {
  if (!codeEl) return 0

  try {
    const textContent = codeEl.textContent
    const actualNewLines = textContent.split('\n')

    if (actualNewLines.length > 1) {
      return actualNewLines.length
    }

    // TinyMCE 使用 <br> 标签的情况
    const brCount = (codeEl.innerHTML && codeEl.innerHTML.match(/<br\s*\/?>/gi) || []).length
    return brCount + 1
  } catch (e) {
    console.warn('Error counting lines:', e)
    return 0
  }
}

/**
 * 创建复制按钮
 * @param {HTMLElement} codeEl - code 元素
 * @param {Object} options - 配置选项
 * @returns {HTMLButtonElement}
 */
function createCopyButton(codeEl, options) {
  if (!codeEl) return null

  const copyBtn = document.createElement('button')
  copyBtn.className = 'copy-btn'

  try {
    copyBtn.innerHTML = ICONS.copy
  } catch (e) {
    console.warn('Error setting copy button innerHTML:', e)
    return null
  }

  copyBtn.setAttribute('aria-label', '复制代码')

  copyBtn.addEventListener('click', async (e) => {
    e.preventDefault()
    e.stopPropagation()

    const textToCopy = codeEl.textContent
    const success = await copyToClipboard(textToCopy)

    if (success) {
      copyBtn.classList.add('copied')
      try {
        copyBtn.innerHTML = ICONS.copied
      } catch (err) {
        console.warn('Error updating copy button:', err)
      }

      setTimeout(() => {
        try {
          if (copyBtn && copyBtn.classList) {
            copyBtn.classList.remove('copied')
            copyBtn.innerHTML = ICONS.copy
          }
        } catch (err) {
          console.warn('Error resetting copy button:', err)
        }
      }, options.copiedDuration)
    }
  })

  return copyBtn
}

/**
 * 创建折叠按钮
 * @param {HTMLElement} pre - pre 元素
 * @param {Object} options - 配置选项
 * @returns {HTMLButtonElement}
 */
function createCollapseButton(pre, options) {
  if (!pre) return null

  const collapseBtn = document.createElement('button')
  collapseBtn.className = 'collapse-btn'

  try {
    collapseBtn.innerHTML = ICONS.expand
  } catch (e) {
    console.warn('Error setting collapse button innerHTML:', e)
    return null
  }

  collapseBtn.setAttribute('aria-label', '展开代码')

  collapseBtn.addEventListener('click', (e) => {
    e.preventDefault()
    e.stopPropagation()

    // 确保 pre 仍在 DOM 中
    if (!pre || !pre.parentNode) {
      console.warn('pre element is no longer in DOM')
      return
    }

    const isCollapsed = pre.classList.contains(options.collapsedClass)
    if (isCollapsed) {
      pre.classList.remove(options.collapsedClass)
      collapseBtn.setAttribute('aria-label', '折叠代码')
    } else {
      pre.classList.add(options.collapsedClass)
      collapseBtn.setAttribute('aria-label', '展开代码')
    }
  })

  return collapseBtn
}

/**
 * 增强单个代码块
 * @param {HTMLElement} pre - pre 元素
 * @param {Object} options - 配置选项
 */
function enhanceCodeBlock(pre, options) {
  // 基础检查
  if (!pre) return
  if (!pre.parentNode) return  // 检查元素是否仍在 DOM 中

  // 跳过已经处理过的代码块
  if (pre.classList.contains(options.enhancedClass)) return

  try {
    // 获取代码元素或使用 pre 本身
    let codeEl = pre.querySelector('code')
    if (!codeEl) {
      // 如果没有 code 标签，创建一个包裹 pre 的内容
      const originalContent = pre.innerHTML
      pre.innerHTML = `<code>${originalContent}</code>`
      codeEl = pre.querySelector('code')
    }

    if (!codeEl) return

    // 添加增强标记类名
    pre.classList.add(options.enhancedClass)

    // 计算行数
    const lineCount = countLines(codeEl)

    // 超过阈值添加折叠功能
    if (lineCount > options.collapseThreshold) {
      pre.classList.add(options.longCodeClass)
      if (options.defaultCollapsed) {
        pre.classList.add(options.collapsedClass)
      }
    }

    // 添加复制按钮
    const copyBtn = createCopyButton(codeEl, options)
    if (copyBtn && pre.parentNode) {  // 确保按钮有效且 pre 仍在 DOM 中
      pre.appendChild(copyBtn)
    }

    // 添加折叠按钮（超过阈值的代码块）
    if (lineCount > options.collapseThreshold) {
      const collapseBtn = createCollapseButton(pre, options)
      if (collapseBtn && pre.parentNode) {  // 确保按钮有效且 pre 仍在 DOM 中
        pre.appendChild(collapseBtn)
      }
    }
  } catch (e) {
    console.warn('Error enhancing code block:', e)
  }
}

/**
 * 增强容器内的所有代码块
 * @param {HTMLElement|ShadowRoot} container - 容器元素
 * @param {Object} userOptions - 用户配置选项
 */
export function enhanceCodeBlocks(container, userOptions = {}) {
  if (!container) return

  const options = { ...DEFAULT_OPTIONS, ...userOptions }

  try {
    // 支持普通 DOM 和 Shadow DOM
    const codeBlocks = container.querySelectorAll('pre')
    if (!codeBlocks) return

    codeBlocks.forEach(pre => {
      try {
        enhanceCodeBlock(pre, options)
      } catch (e) {
        console.warn('Error processing individual code block:', e)
        // 继续处理其他代码块
      }
    })
  } catch (e) {
    console.warn('Error enhancing code blocks:', e)
  }
}

/**
 * Vue Composable: useCodeEnhancer
 *
 * 用法:
 * ```js
 * import { useCodeEnhancer } from '@/composables/useCodeEnhancer'
 *
 * const { enhance } = useCodeEnhancer()
 *
 * // 在内容渲染后调用
 * nextTick(() => {
 *   enhance(contentRef.value)
 * })
 * ```
 */
export function useCodeEnhancer(defaultOptions = {}) {
  const options = { ...DEFAULT_OPTIONS, ...defaultOptions }

  /**
   * 增强指定容器内的代码块
   * @param {HTMLElement|ShadowRoot} container
   * @param {Object} overrideOptions - 覆盖默认配置
   */
  const enhance = (container, overrideOptions = {}) => {
    enhanceCodeBlocks(container, { ...options, ...overrideOptions })
  }

  return {
    enhance,
    copyToClipboard
  }
}

/**
 * 获取代码块增强所需的 CSS 样式
 * 可用于 Shadow DOM 内部样式
 * @param {boolean} isDark - 是否暗色主题
 * @returns {string} CSS 样式字符串
 */
export function getCodeEnhancerStyles(isDark = false) {
  return `
  /* 代码块增强：复制和折叠 */
  pre.code-block-enhanced {
    position: relative;
    padding-right: 40px;
  }

  /* 复制按钮 */
  pre .copy-btn {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 32px;
    height: 32px;
    border: none;
    background: ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'};
    color: ${isDark ? '#aaa' : '#666'};
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
    z-index: 10;
    overflow: hidden;
    padding: 0;
  }

  pre .copy-btn:hover {
    background: ${isDark ? 'rgba(64, 158, 255, 0.3)' : 'rgba(64, 158, 255, 0.2)'};
    color: #409eff;
  }

  pre .copy-btn.copied {
    background: #67c23a;
    color: white;
  }

  pre .copy-btn svg {
    width: 16px;
    height: 16px;
    display: block;
    flex-shrink: 0;
  }

  /* 折叠按钮 */
  pre .collapse-btn {
    position: absolute;
    bottom: 8px;
    right: 8px;
    width: 32px;
    height: 32px;
    border: none;
    background: ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'};
    color: ${isDark ? '#aaa' : '#666'};
    border-radius: 4px;
    cursor: pointer;
    display: none;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
    z-index: 10;
    overflow: hidden;
    padding: 0;
  }

  pre .collapse-btn:hover {
    background: ${isDark ? 'rgba(64, 158, 255, 0.3)' : 'rgba(64, 158, 255, 0.2)'};
    color: #409eff;
  }

  pre .collapse-btn svg {
    width: 16px;
    height: 16px;
    display: block;
    flex-shrink: 0;
    transition: transform 0.2s ease;
  }

  /* 折叠状态 */
  pre.code-block-enhanced.collapsed .collapse-btn svg {
    transform: rotate(180deg);
  }

  pre.code-block-enhanced.collapsed code {
    display: block;
    max-height: 5.4em;
    overflow: hidden;
    -webkit-mask-image: linear-gradient(180deg, #000 60%, transparent);
    mask-image: linear-gradient(180deg, #000 60%, transparent);
  }

  /* 超过阈值的代码块显示折叠按钮 */
  pre.code-block-enhanced.long-code .collapse-btn {
    display: flex;
  }
`
}

export default useCodeEnhancer
