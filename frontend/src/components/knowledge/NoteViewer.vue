<template>
  <!-- 加密笔记未解锁提示 -->
  <div v-if="props.isSecret && !isKeyValid" class="encrypted-prompt">
    <el-alert
      title="保密笔记"
      type="warning"
      description="此笔记已加密。请完成 2FA 验证后查看内容。"
      :closable="false"
    />
  </div>

  <!-- 加密笔记解密中 -->
  <div v-else-if="isDecrypting" class="decrypting-state">
    <el-skeleton :rows="5" animated />
    <p style="text-align: center; color: #999; margin-top: 10px;">解密中...</p>
  </div>

  <!-- 解密错误提示 -->
  <div v-else-if="decryptError" class="decrypt-error">
    <el-alert
      :title="decryptError"
      type="error"
      closable
      @close="decryptError = ''"
    />
  </div>

  <!-- 已解密或非加密笔记 -->
  <div v-else ref="contentRef" class="note-viewer note-prose"></div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick, computed } from 'vue'
import { ElAlert, ElSkeleton } from 'element-plus'
import DOMPurify from 'dompurify'
import { useCodeEnhancer } from '../composables/useCodeEnhancer'
import { useVaultEncryption } from '@/composables/useVaultEncryption'
import { useClientCrypto } from '@/composables/useClientCrypto'

const props = defineProps({
  content: {
    type: String,
    default: ''
  },
  isSecret: {
    type: Boolean,
    default: false
  },
  noteId: {
    type: Number,
    default: null
  }
})

const contentRef = ref(null)
const isDecrypting = ref(false)
const decryptError = ref('')
const decryptedContent = ref('')

// 使用加密组合式
const { isKeyValid, dek } = useVaultEncryption()
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
 *
 * 逻辑判断：
 * 1. 如果 !isSecret: 返回原内容
 * 2. 如果 isSecret && isKeyValid: 返回已解密的内容
 * 3. 如果 isSecret && !isKeyValid: 返回空字符串（模板显示加密提示）
 */
const displayContent = computed(() => {
  if (!props.isSecret) {
    // 普通笔记，直接返回内容
    return props.content
  }

  if (isKeyValid.value) {
    // 已解锁的加密笔记，返回解密后的内容
    return decryptedContent.value
  }

  // 未解锁的加密笔记，返回空字符串（模板显示加密提示）
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
    console.warn('contentRef is not available')
    return
  }

  try {
    contentRef.value.innerHTML = getSanitizedContent(content)
  } catch (e) {
    console.warn('Error setting innerHTML:', e)
    return
  }

  nextTick(() => {
    if (!contentRef.value) {
      console.warn('contentRef has been cleared before code enhancement')
      return
    }

    try {
      enhanceCodeBlocks(contentRef.value)
    } catch (e) {
      console.warn('Error enhancing code blocks:', e)
    }
  })
}

/**
 * 解密加密笔记的内容
 */
async function decryptContent() {
  if (!props.isSecret || !props.content || !props.noteId) {
    return
  }

  // 检查是否有有效的 DEK
  if (!isKeyValid.value || !dek.value) {
    decryptError.value = '未能获取解密密钥，请进行 2FA 验证'
    return
  }

  isDecrypting.value = true
  decryptError.value = ''

  try {
    // 【改进】使用前端 useClientCrypto 进行解密
    const plaintext = await decryptClientContent(props.content, dek.value)
    decryptedContent.value = plaintext
    renderContent(plaintext)
    console.log('[Vault] Content decrypted successfully in viewer')
  } catch (e) {
    console.error('[Vault] Decryption error in viewer:', e)
    decryptError.value = '解密失败: ' + e.message
    decryptedContent.value = ''
  } finally {
    isDecrypting.value = false
  }
}

onMounted(() => {
  // 如果是非加密笔记，直接渲染
  if (!props.isSecret) {
    renderContent(props.content)
  } else if (isKeyValid.value) {
    // 加密笔记且已解锁，立即解密
    decryptContent()
  }
  // 如果加密且未解锁，等待 watch isKeyValid 的变化
})

/**
 * 监听 displayContent 变化，重新渲染内容
 * 当 displayContent computed 变化时（由 isKeyValid 或 content 触发），
 * 自动更新视图
 */
watch(() => displayContent.value, (newContent) => {
  if (newContent) {
    renderContent(newContent)
  }
})

/**
 * 监听 isKeyValid 变化：
 * 当保险柜解锁时（isKeyValid 从 false 变为 true），
 * 立即触发解密，无需用户操作
 */
watch(() => isKeyValid.value, (valid) => {
  if (valid && props.isSecret && props.content && !decryptedContent.value) {
    // 密钥刚刚变有效，且还没有解密内容，立即解密
    decryptContent()
  }
})

/**
 * 监听 content 变化，如果是加密笔记且已有解密密钥，重新解密
 */
watch(() => props.content, (newContent) => {
  if (newContent && props.isSecret && isKeyValid.value) {
    // 笔记内容变化且已解锁，重新解密
    decryptContent()
  }
})
</script>

<style scoped>
.encrypted-prompt {
  padding: 20px;
  margin-bottom: 20px;
}

.decrypting-state {
  padding: 20px;
}

.decrypt-error {
  padding: 20px;
}

/* NoteViewer 容器基础样式 */
.note-viewer {
  width: 100%;
  line-height: 1.8;
  color: var(--text-primary, #333);
  word-wrap: break-word;
  overflow-wrap: anywhere;
}

/* Prose 排版样式 */
.note-prose :deep(*) {
  box-sizing: border-box;
  max-width: 100%;
}

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
  margin: 0.8em 0 0.4em;
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

/* 表单元素 */
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
</style>
