<template>
  <div ref="contentRef" class="note-viewer note-prose"></div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import DOMPurify from 'dompurify'
import { useCodeEnhancer } from '../composables/useCodeEnhancer'

const props = defineProps({
  content: {
    type: String,
    default: ''
  }
})

const contentRef = ref(null)

// 使用代码块增强功能
const { enhance: enhanceCodeBlocks } = useCodeEnhancer()

// 配置 DOMPurify
const purifyConfig = {
  // 禁止的标签
  FORBID_TAGS: ['script', 'style', 'link', 'meta', 'iframe', 'object', 'embed', 'frame', 'frameset'],
  // 禁止的属性（所有事件处理器会自动被移除）
  FORBID_ATTR: ['onerror', 'onclick', 'onmouseover', 'onload', 'onmouseenter', 'onfocus', 'onblur'],
  // 允许的 URI 协议
  ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|data):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
}

/**
 * 移除所有 class 和 id 属性，防止外部样式影响布局
 * 保留内容结构，只清理可能造成样式冲突的属性
 * 同时修复相对路径的图片 URL
 */
const stripClassAndId = (html) => {
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')

  // 获取网站根 URL
  const baseUrl = window.location.origin + '/'

  // 移除所有元素的 class 和 id 属性
  doc.querySelectorAll('*').forEach(el => {
    el.removeAttribute('class')
    el.removeAttribute('id')

    // 修复图片的 src 属性：将相对路径转换为绝对路径
    if (el.tagName === 'IMG') {
      const src = el.getAttribute('src')
      if (src && !src.match(/^https?:\/\//) && !src.match(/^\/\//)) {
        // 相对路径，转换为绝对路径
        if (src.startsWith('./') || src.startsWith('../')) {
          // 处理 ./ 或 ../ 开头的路径
          el.setAttribute('src', new URL(src, baseUrl).href)
        } else if (!src.match(/^[a-zA-Z][a-zA-Z0-9+.-]*:/)) {
          // 不是绝对路径也不是协议，视为根相对路径
          el.setAttribute('src', baseUrl + src.replace(/^\//, ''))
        }
      }
    }

    // 移除可能影响布局的 style 属性中的危险部分
    const style = el.getAttribute('style')
    if (style) {
      // 只保留安全的样式属性（颜色、字体等），移除布局相关的
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
      // 清理空的样式声明
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

// 获取清洗后的内容
const getSanitizedContent = () => {
  if (!props.content) return ''

  // 1. 使用 DOMPurify 进行安全清洗
  const cleanHTML = DOMPurify.sanitize(props.content, purifyConfig)

  // 2. 移除所有 class 和 id 属性，防止外部样式影响，同时修复图片路径
  const strippedHTML = stripClassAndId(cleanHTML)

  return strippedHTML
}

// 渲染内容
const renderContent = () => {
  if (!contentRef.value) return

  contentRef.value.innerHTML = getSanitizedContent()

  // 渲染后增强代码块
  nextTick(() => {
    enhanceCodeBlocks(contentRef.value)
  })
}

onMounted(() => {
  renderContent()
})

// 监听内容变化
watch(() => props.content, () => {
  renderContent()
})
</script>

<style scoped>
/* NoteViewer 容器基础样式 */
.note-viewer {
  width: 100%;
  line-height: 1.8;
  color: var(--text-primary, #333);
  word-wrap: break-word;
  overflow-wrap: anywhere;
}

/* ========================================
   Prose 排版样式 - 强制覆盖外部样式
   ======================================== */

/* 全局重置 */
.note-prose :deep(*) {
  box-sizing: border-box;
  max-width: 100%;
}

/* 块级元素 */
.note-prose :deep(div) {
  display: block;
  margin: 0.5em 0;
}

/* 标题 */
.note-prose :deep(h1) {
  font-size: 1.8em;
  font-weight: 600;
  margin: 1em 0 0.5em;
  line-height: 1.3;
  display: block;
  color: var(--text-primary, #1a1a1a);
}

.note-prose :deep(h2) {
  font-size: 1.5em;
  font-weight: 600;
  margin: 1em 0 0.5em;
  line-height: 1.35;
  display: block;
  color: var(--text-primary, #1a1a1a);
}

.note-prose :deep(h3) {
  font-size: 1.25em;
  font-weight: 600;
  margin: 1em 0 0.5em;
  line-height: 1.4;
  display: block;
  color: var(--text-primary, #1a1a1a);
}

.note-prose :deep(h4),
.note-prose :deep(h5),
.note-prose :deep(h6) {
  font-size: 1.1em;
  font-weight: 600;
  margin: 1em 0 0.5em;
  line-height: 1.4;
  display: block;
  color: var(--text-primary, #1a1a1a);
}

/* 段落 */
.note-prose :deep(p) {
  margin: 1em 0;
  line-height: 1.8;
  display: block;
  color: var(--text-primary, #333);
}

/* 链接 */
.note-prose :deep(a) {
  color: var(--primary-color, #409eff);
  text-decoration: none;
  transition: color 0.2s;
}

.note-prose :deep(a:hover) {
  color: var(--primary-color-light, #66b1ff);
  text-decoration: underline;
}

/* 列表 */
.note-prose :deep(ul),
.note-prose :deep(ol) {
  margin: 1em 0;
  padding-left: 2em;
  display: block;
}

.note-prose :deep(ul) {
  list-style-type: disc;
}

.note-prose :deep(ol) {
  list-style-type: decimal;
}

.note-prose :deep(li) {
  margin: 0.5em 0;
  line-height: 1.6;
  display: list-item;
}

/* 引用块 */
.note-prose :deep(blockquote) {
  margin: 1em 0;
  padding: 0.5em 1em;
  border-left: 4px solid var(--primary-color, #409eff);
  background: var(--bg-secondary, rgba(64, 158, 255, 0.05));
  border-radius: 0 4px 4px 0;
  display: block;
}

.note-prose :deep(blockquote p) {
  margin: 0.5em 0;
}

/* 代码 */
.note-prose :deep(code) {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  background: var(--bg-tertiary, rgba(0, 0, 0, 0.05));
  padding: 0.2em 0.4em;
  border-radius: 3px;
  font-size: 0.9em;
  color: var(--text-primary, #333);
}

.note-prose :deep(pre) {
  margin: 1em 0;
  padding: 1em;
  background: var(--bg-tertiary, #f5f5f5);
  border-radius: 8px;
  overflow-x: auto;
  display: block;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.note-prose :deep(pre code) {
  background: transparent;
  padding: 0;
  border-radius: 0;
  font-size: 0.875em;
  line-height: 1.6;
}

/* 图片 */
.note-prose :deep(img) {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 1em auto;
  border-radius: 8px;
}

/* 表格 */
.note-prose :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
  display: table;
  overflow-x: auto;
}

.note-prose :deep(th),
.note-prose :deep(td) {
  border: 1px solid var(--border-color, #e0e0e0);
  padding: 0.75em 1em;
  text-align: left;
}

.note-prose :deep(th) {
  background: var(--bg-secondary, #f5f5f5);
  font-weight: 600;
}

.note-prose :deep(tr:nth-child(even)) {
  background: var(--bg-tertiary, rgba(0, 0, 0, 0.02));
}

/* 分割线 */
.note-prose :deep(hr) {
  margin: 2em 0;
  border: none;
  border-top: 1px solid var(--border-color, #e0e0e0);
  display: block;
}

/* 强调文本 */
.note-prose :deep(strong),
.note-prose :deep(b) {
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
}

.note-prose :deep(em),
.note-prose :deep(i) {
  font-style: italic;
}

/* 删除线 */
.note-prose :deep(del),
.note-prose :deep(s) {
  text-decoration: line-through;
  opacity: 0.7;
}

/* 下划线 */
.note-prose :deep(u) {
  text-decoration: underline;
}

/* 标记高亮 */
.note-prose :deep(mark) {
  background: rgba(255, 230, 0, 0.4);
  padding: 0.1em 0.2em;
  border-radius: 2px;
}

/* 上下标 */
.note-prose :deep(sub) {
  font-size: 0.75em;
  vertical-align: sub;
}

.note-prose :deep(sup) {
  font-size: 0.75em;
  vertical-align: super;
}

/* 表单元素（按钮等） */
.note-prose :deep(button) {
  display: inline-block;
  padding: 0.5em 1em;
  background: var(--bg-secondary, #f0f0f0);
  border: 1px solid var(--border-color, #d0d0d0);
  border-radius: 4px;
  cursor: pointer;
  font-size: inherit;
  color: var(--text-primary, #333);
}

.note-prose :deep(input),
.note-prose :deep(textarea) {
  display: inline-block;
  padding: 0.5em;
  border: 1px solid var(--border-color, #d0d0d0);
  border-radius: 4px;
  font-size: inherit;
  max-width: 100%;
}

/* span 和 label */
.note-prose :deep(span) {
  display: inline;
}

.note-prose :deep(label) {
  display: inline-block;
  margin: 0.25em 0;
}

/* figure 和 figcaption */
.note-prose :deep(figure) {
  margin: 1.5em 0;
  display: block;
}

.note-prose :deep(figcaption) {
  text-align: center;
  font-size: 0.9em;
  color: var(--text-secondary, #666);
  margin-top: 0.5em;
}

/* details 和 summary */
.note-prose :deep(details) {
  margin: 1em 0;
  padding: 1em;
  background: var(--bg-secondary, #f9f9f9);
  border-radius: 4px;
}

.note-prose :deep(summary) {
  cursor: pointer;
  font-weight: 500;
}

/* 视频和音频 */
.note-prose :deep(video),
.note-prose :deep(audio) {
  max-width: 100%;
  display: block;
  margin: 1em 0;
}

/* 防止外部 flex/grid 布局影响 */
.note-prose :deep([class*="flex"]),
.note-prose :deep([class*="grid"]) {
  display: block !important;
}

/* 重置可能的定位属性 */
.note-prose :deep([style*="position: absolute"]),
.note-prose :deep([style*="position: fixed"]) {
  position: relative !important;
}

/* 确保所有容器不会溢出 */
.note-prose :deep(*) {
  max-width: 100%;
  overflow-wrap: break-word;
}

/* ========================================
   代码块增强：复制和折叠按钮
   ======================================== */

.note-prose :deep(pre.code-block-enhanced) {
  position: relative;
  padding-right: 40px;
}

/* 复制按钮 */
.note-prose :deep(pre .copy-btn) {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 32px;
  height: 32px;
  border: none;
  background: var(--bg-tertiary, rgba(0, 0, 0, 0.1));
  color: var(--text-secondary, #666);
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

.note-prose :deep(pre .copy-btn:hover) {
  background: rgba(64, 158, 255, 0.2);
  color: #409eff;
}

.note-prose :deep(pre .copy-btn.copied) {
  background: #67c23a;
  color: white;
}

.note-prose :deep(pre .copy-btn svg) {
  width: 18px;
  height: 18px;
  display: block;
  flex-shrink: 0;
}

/* 折叠按钮 */
.note-prose :deep(pre .collapse-btn) {
  position: absolute;
  bottom: 8px;
  right: 8px;
  width: 32px;
  height: 32px;
  border: none;
  background: var(--bg-tertiary, rgba(0, 0, 0, 0.1));
  color: var(--text-secondary, #666);
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

.note-prose :deep(pre .collapse-btn:hover) {
  background: rgba(64, 158, 255, 0.2);
  color: #409eff;
}

.note-prose :deep(pre .collapse-btn svg) {
  width: 18px;
  height: 18px;
  display: block;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

/* 折叠状态：箭头旋转 */
.note-prose :deep(pre.collapsed .collapse-btn svg) {
  transform: rotate(180deg);
}

/* 折叠状态：代码块显示渐变遮罩 */
.note-prose :deep(pre.collapsed code) {
  display: block;
  max-height: 5.4em;
  overflow: hidden;
  -webkit-mask-image: linear-gradient(180deg, #000 60%, transparent);
  mask-image: linear-gradient(180deg, #000 60%, transparent);
}

/* 长代码块（超过5行）显示折叠按钮 */
.note-prose :deep(pre.long-code .collapse-btn) {
  display: flex;
}
</style>
