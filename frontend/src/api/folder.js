import { getCsrfToken } from '@utils/csrf'
import { extractApiErrorMessage } from '@utils/apiError'

/**
 * 文件夹 API 服务层
 * 封装所有文件夹相关的 API 调用
 */

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
 * 文件夹 API 服务
 */
export const folderApi = {
  /**
   * 获取所有文件夹（树形结构）
   * @returns {Promise<Array>} 文件夹树
   */
  async fetchAll() {
    const response = await fetchWrapper('/api/folders/')
    return await response.json()
  },

  /**
   * 获取单个文件夹详情
   * @param {string|number} folderId - 文件夹 ID
   * @returns {Promise<Object>} 文件夹详情
   */
  async fetch(folderId) {
    const response = await fetchWrapper(`/api/folders/${folderId}/`)
    return await response.json()
  },

  /**
   * 获取文件夹下的笔记列表
   * @param {string|number} folderId - 文件夹 ID，为 null 时获取收件箱笔记
   * @returns {Promise<Array>} 笔记列表
   */
  async fetchNotes(folderId = null) {
    const url = folderId ? `/api/folders/${folderId}/notes/` : '/api/folders/inbox/notes/'
    const response = await fetchWrapper(url)
    return await response.json()
  },

  /**
   * 创建文件夹
   * @param {Object} data - 文件夹数据
   * @param {string} data.name - 文件夹名称
   * @param {number|null} data.parent_id - 父文件夹 ID
   * @param {string} [csrfToken] - CSRF token
   * @returns {Promise<Object>} 创建的文件夹
   */
  async create(data, csrfToken) {
    const response = await fetchWrapper('/api/folders/', {
      method: 'POST',
      csrfToken,
      body: JSON.stringify(data)
    })
    return await response.json()
  },

  /**
   * 更新文件夹（重命名）
   * @param {string|number} folderId - 文件夹 ID
   * @param {Object} data - 更新的数据
   * @param {string} [csrfToken] - CSRF token
   * @returns {Promise<Object>} 更新后的文件夹
   */
  async update(folderId, data, csrfToken) {
    const response = await fetchWrapper(`/api/folders/${folderId}/`, {
      method: 'PUT',
      csrfToken,
      body: JSON.stringify(data)
    })
    return await response.json()
  },

  /**
   * 删除文件夹（笔记会移动到收件箱）
   * @param {string|number} folderId - 文件夹 ID
   * @param {string} [csrfToken] - CSRF token
   * @returns {Promise<Object>} 删除结果
   */
  async delete(folderId, csrfToken) {
    const response = await fetchWrapper(`/api/folders/${folderId}/`, {
      method: 'DELETE',
      csrfToken
    })
    return await response.json()
  },

  /**
   * 移动笔记到文件夹
   * @param {string|number} noteId - 笔记 ID
   * @param {string|number|null} folderId - 目标文件夹 ID，为 null 时移动到收件箱
   * @param {string} [csrfToken] - CSRF token
   * @returns {Promise<Object>} 移动结果
   */
  async moveNote(noteId, folderId, csrfToken) {
    const response = await fetchWrapper(`/api/notes/${noteId}/move/`, {
      method: 'POST',
      csrfToken,
      body: JSON.stringify({ folder_id: folderId })
    })
    return await response.json()
  },

  /**
   * 获取文件夹面包屑路径
   * @param {string|number} folderId - 文件夹 ID
   * @returns {Promise<Array>} 面包屑路径
   */
  async getBreadcrumb(folderId) {
    const response = await fetchWrapper(`/api/folders/${folderId}/breadcrumb/`)
    return await response.json()
  }
}

export default folderApi
