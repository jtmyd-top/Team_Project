/**
 * NoteShadowViewer Shadow DOM 样式配置
 * 这些样式作为 JS 字符串注入到 Shadow DOM 中
 */

import { getCodeEnhancerStyles } from '@composables/useCodeEnhancer'

/**
 * 获取 Shadow DOM 内部样式
 * @param {boolean} isDark - 是否为暗色主题
 * @returns {string} CSS 样式字符串
 */
export function getShadowStyles(isDark) {
  return `
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
    overflow-x: hidden;
  }

  /* 回收站中保密笔记的锁定提示样式 */
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

  .note-content audio {
    display: block;
    width: min(100%, 420px);
    margin: 1em 0;
  }

  .note-content video {
    display: block;
    width: min(100%, 100%);
    max-width: 760px;
    margin: 1em 0;
    border-radius: 12px;
    background: #000;
  }

  .note-content .ubb-music-card {
    margin: 1em 0;
  }

  .note-content .ubb-music-frame {
    display: block;
    width: 100%;
    max-width: 420px;
    border: none;
    border-radius: 12px;
    background: ${isDark ? '#111827' : '#f8fafc'};
  }

  .note-content .ubb-code-block {
    margin: 1em 0;
    padding: 1em;
    border-radius: 10px;
    background: ${isDark ? '#111827' : '#0f172a'};
    color: #e2e8f0;
  }

  .note-content .ubb-code-block code {
    background: transparent;
    color: inherit;
    padding: 0;
    white-space: pre-wrap;
  }

  .note-content .ubb-countdown {
    display: inline-flex;
    align-items: center;
    padding: 0.08rem 0.5rem;
    border-radius: 999px;
    background: ${isDark ? 'rgba(245, 158, 11, 0.18)' : 'rgba(245, 158, 11, 0.12)'};
    color: ${isDark ? '#fbbf24' : '#b45309'};
    font-size: 0.82em;
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
    display: block;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-wrap: normal;
  }

  .note-content pre code {
    background: transparent;
    padding: 0;
    border-radius: 0;
    font-size: 0.875em;
    line-height: 1.6;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-wrap: normal;
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
}

/**
 * DOMPurify 清洗配置
 */
export const purifyConfig = {
  FORBID_TAGS: ['script', 'iframe', 'frame', 'object', 'embed', 'form', 'meta', 'link'],
  FORBID_ATTR: ['onerror', 'onclick', 'onmouseover', 'onload', 'onmouseenter', 'onfocus', 'onblur', 'onsubmit'],
  ADD_TAGS: ['audio', 'video'],
  ADD_ATTR: ['controls', 'preload', 'playsinline', 'src', 'data-song-id', 'data-date', 'data-ubb-now'],
  ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|data):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
}

/**
 * 目录显示阈值
 */
export const TOC_THRESHOLD = 3
