/**
 * 笔记 API 服务层
 * 封装所有笔记相关的 API 调用
 */

import { getCsrfToken } from '@utils/csrf'
import { extractApiErrorMessage } from '@utils/apiError'

// 基础 fetch 包装器
const fetchWrapper = async (url, options = {}) => {
  const defaultOptions = {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    }
  }

  // 为需要认证的请求添加 CSRF token
  if (options.method && options.method !== 'GET') {
    defaultOptions.headers['X-CSRFToken'] = options.csrfToken || getCsrfToken()
  }

  const response = await fetch(url, { ...options, ...defaultOptions })

  if (!response.ok) {
    const data = await response.clone().json().catch(() => ({}))
    const error = new Error(
      extractApiErrorMessage(data, `HTTP ${response.status}: ${response.statusText}`)
    )
    error.status = response.status
    error.response = response
    error.data = data
    throw error
  }

  return response
}

/**
 * 笔记 API 服务
 */
export const noteApi = {
  /**
   * 获取所有笔记列表
   * @returns {Promise<Array>} 笔记列表
   */
  async fetchAll() {
    const response = await fetchWrapper('/api/notes/all/')
    return await response.json()
  },

  /**
   * 获取单个笔记详情
   * @param {string|number} noteId - 笔记 ID
   * @param {Object} options - 选项
   * @param {boolean} options.fullContent - 是否获取完整内容
   * @returns {Promise<Object>} 笔记详情
   */
  async fetch(noteId, options = {}) {
    const params = new URLSearchParams()
    if (options.fullContent) params.set('full_content', 'true')

    const url = `/api/notes/${noteId}/${params ? '?' + params.toString() : ''}`
    const response = await fetchWrapper(url)
    return await response.json()
  },

  /**
   * 创建新笔记
   * @param {Object} data - 笔记数据
   * @param {string} data.title - 笔记标题
   * @param {string} data.content - 笔记内容
   * @param {boolean} data.is_public - 是否公开
   * @param {string} [csrfToken] - CSRF token
   * @returns {Promise<Object>} 创建的笔记
   */
  async create(data, csrfToken) {
    const response = await fetchWrapper('/api/notes/create/', {
      method: 'POST',
      csrfToken,
      body: JSON.stringify(data)
    })
    return await response.json()
  },

  /**
   * 更新笔记
   * @param {string|number} noteId - 笔记 ID
   * @param {Object} data - 更新的数据
   * @param {string} [csrfToken] - CSRF token
   * @returns {Promise<Object>} 更新后的笔记
   */
  async update(noteId, data, csrfToken) {
    const response = await fetchWrapper(`/api/notes/${noteId}/`, {
      method: 'PUT',
      csrfToken,
      body: JSON.stringify(data)
    })
    return await response.json()
  },

  /**
   * 删除笔记
   * @param {string|number} noteId - 笔记 ID
   * @param {string} [csrfToken] - CSRF token
   * @returns {Promise<boolean>} 是否成功
   */
  async delete(noteId, csrfToken) {
    const response = await fetchWrapper(`/api/notes/${noteId}/`, {
      method: 'DELETE',
      csrfToken
    })
    return true
  },

  /**
   * 切换笔记公开状态
   * @param {string|number} noteId - 笔记 ID
   * @param {boolean} isPublic - 是否公开
   * @param {string} [csrfToken] - CSRF token
   * @returns {Promise<Object>} 更新后的笔记
   */
  async togglePublic(noteId, isPublic, csrfToken) {
    return this.update(noteId, { is_public: isPublic }, csrfToken)
  },

  /**
   * 上传图片
   * @param {File|Blob} file - 图片文件
   * @param {Function} onProgress - 进度回调
   * @param {string} [csrfToken] - CSRF token
   * @returns {Promise<string>} 图片 URL
   */
  async uploadImage(file, onProgress, csrfToken) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/upload/image/')

      // 添加 CSRF token
      xhr.setRequestHeader('X-CSRFToken', csrfToken || getCsrfToken())

      xhr.upload.onprogress = (e) => {
        if (onProgress && e.lengthComputable) {
          onProgress(e.loaded / e.total * 100)
        }
      }

      xhr.onload = () => {
        if (xhr.status === 403) {
          reject({ message: '请先登录', remove: true })
          return
        }
        if (xhr.status < 200 || xhr.status >= 300) {
          reject(new Error(`图片上传失败: ${xhr.status}`))
          return
        }
        const json = JSON.parse(xhr.responseText)
        if (!json || !json.location) {
          reject(new Error(`无效的响应: ${xhr.responseText}`))
          return
        }
        resolve(json.location)
      }

      xhr.onerror = () => {
        reject(new Error('网络错误，图片上传失败'))
      }

      const formData = new FormData()
      formData.append('file', file, file.name || 'image.png')
      xhr.send(formData)
    })
  }
}

/**
 * 主题设置 API 服务
 */
export const themeApi = {
  /**
   * 获取主题设置
   * @returns {Promise<Object>} 主题设置
   */
  async fetch() {
    const response = await fetchWrapper('/api/theme-settings/')
    const data = await response.json()
    if (data.status === 'success') {
      return data.settings
    }
    return null
  },

  /**
   * 保存主题设置
   * @param {Object} settings - 主题设置
   * @param {string} settings.mode - 主题模式 'light' 或 'dark'
   * @param {string} [csrfToken] - CSRF token
   * @returns {Promise<boolean>} 是否成功
   */
  async save(settings, csrfToken) {
    const response = await fetchWrapper('/api/theme-settings/', {
      method: 'POST',
      csrfToken,
      body: JSON.stringify(settings)
    })
    return response.ok
  }
}

export default {
  note: noteApi,
  theme: themeApi
}
