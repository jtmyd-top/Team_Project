/**
 * 统一的错误处理工具
 * 用于处理前端API请求中的各种错误情况
 */

import { extractApiErrorMessage } from '@utils/apiError'

/**
 * 处理API错误并返回用户友好的错误消息
 * @param {Error} error - 错误对象
 * @param {string} defaultMessage - 默认错误消息
 * @returns {string} 用户友好的错误消息
 */
export function handleApiError(error, defaultMessage = '操作失败') {
  // 优先使用后端响应体中的业务错误文案
  if (error.response?.data) {
    const responseMessage = extractApiErrorMessage(error.response.data, '')
    if (responseMessage) return responseMessage
  }

  // 优先使用 error.message（适用于网络错误、超时等）
  if (error.message && error.message !== '请求失败') {
    // 网络相关错误的特殊处理
    if (error.message.includes('Network Error') ||
        error.message.includes('ERR_NETWORK') ||
        error.message.includes('ERR_INTERNET_DISCONNECTED') ||
        error.message.includes('timeout') ||
        error.message.includes('TIMEOUT')) {
      return '网络连接失败，请检查网络设置后重试'
    }

    if (error.message.includes('401') || error.message.includes('Unauthorized')) {
      return '登录已过期，请重新登录'
    }

    if (error.message.includes('403') || error.message.includes('Forbidden')) {
      return '没有操作权限，请检查账户状态'
    }

    if (error.message.includes('404') || error.message.includes('Not Found')) {
      return '请求的资源不存在'
    }

    if (error.message.includes('429') || error.message.includes('Too Many Requests')) {
      return '请求过于频繁，请稍后再试'
    }

    if (error.message.includes('500') || error.message.includes('Internal Server Error')) {
      return '服务器内部错误，请稍后重试'
    }

    return error.message
  }

  // 根据不同的操作提供更具体的默认错误消息
  const contextMessages = {
    login: '登录失败，请检查用户名和密码',
    register: '注册失败，请检查填写的信息',
    verify2fa: '验证失败，请检查验证码',
    sendCode: '发送验证码失败，请稍后重试',
    resetPassword: '密码重置失败，请稍后重试',
    updateProfile: '更新资料失败，请稍后重试',
    changePassword: '修改密码失败，请稍后重试',
    uploadFile: '文件上传失败，请稍后重试',
    saveSettings: '保存设置失败，请稍后重试'
  }

  // 使用上下文相关的默认消息
  if (error.operationType && contextMessages[error.operationType]) {
    return contextMessages[error.operationType]
  }

  // 通用网络错误检测
  if (!navigator.onLine) {
    return '网络连接已断开，请检查网络设置'
  }

  return defaultMessage
}

/**
 * 显示错误消息（使用Element Plus的ElMessage）
 * @param {Error} error - 错误对象
 * @param {string} defaultMessage - 默认错误消息
 * @param {string} type - 消息类型：'error'（默认）、'warning'、'info'
 */
export function showApiError(error, defaultMessage = '操作失败', type = 'error') {
  const { ElMessage } = window.ElementPlus || {}
  const message = handleApiError(error, defaultMessage)

  if (ElMessage) {
    ElMessage({
      type,
      message,
      duration: 4000
    })
  } else {
    // 降级方案：使用原生 alert
    alert(message)
  }
}

/**
 * 为错误对象添加操作类型
 * @param {Error} error - 原始错误对象
 * @param {string} operationType - 操作类型
 * @returns {Error} 增强的错误对象
 */
export function enhanceError(error, operationType) {
  error.operationType = operationType
  return error
}

/**
 * 为Vue应用设置全局错误处理
 * @param {import('vue').App} app - Vue应用实例
 */
export function setupGlobalErrorHandler(app) {
  // Vue 3 的全局错误处理器
  app.config.errorHandler = (err, instance, info) => {
    console.error('Vue Error:', err)
    console.error('Component Instance:', instance)
    console.error('Error Info:', info)

    // 显示用户友好的错误消息
    showApiError(err, '应用程序发生错误，请刷新页面重试')
  }

  // 捕获未处理的Promise rejection
  window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled Promise Rejection:', event.reason)
    showApiError(new Error(event.reason), '请求处理失败，请稍后重试')
  })

  // 捕获全局JavaScript错误
  window.addEventListener('error', (event) => {
    console.error('Global Error:', event.error)
    showApiError(event.error, '页面发生错误，请刷新重试')
  })
}
