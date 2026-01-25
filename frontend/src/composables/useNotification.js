/**
 * useNotification - 全局通知系统
 *
 * 提供一个简单的通知 API，可以在任何地方使用
 * 统一了 KnowledgeList.vue、PublicNoteView.vue 等组件中的通知逻辑
 */

import { ref, createApp, h } from 'vue'
import BaseNotification from '../components/common/BaseNotification.vue'

// 单例实例
let notificationInstance = null
let notificationApp = null

/**
 * 初始化通知组件
 */
function initNotification() {
  if (notificationInstance) return notificationInstance

  // 创建挂载容器
  const container = document.createElement('div')
  container.id = 'global-notification-container'
  document.body.appendChild(container)

  // 创建 Vue 应用
  notificationApp = createApp(BaseNotification)
  notificationInstance = notificationApp.mount(container)

  return notificationInstance
}

/**
 * 获取通知实例
 */
function getInstance() {
  if (!notificationInstance) {
    initNotification()
  }
  return notificationInstance
}

/**
 * 显示通知
 * @param {Object|string} options - 配置或消息
 */
export function showNotification(options) {
  return getInstance().show(options)
}

/**
 * 显示成功通知
 * @param {string} message - 消息
 * @param {Object} options - 额外配置
 */
export function showSuccess(message, options = {}) {
  return getInstance().success(message, options)
}

/**
 * 显示错误通知
 * @param {string} message - 消息
 * @param {Object} options - 额外配置
 */
export function showError(message, options = {}) {
  return getInstance().error(message, options)
}

/**
 * 显示警告通知
 * @param {string} message - 消息
 * @param {Object} options - 额外配置
 */
export function showWarning(message, options = {}) {
  return getInstance().warning(message, options)
}

/**
 * 显示信息通知
 * @param {string} message - 消息
 * @param {Object} options - 额外配置
 */
export function showInfo(message, options = {}) {
  return getInstance().info(message, options)
}

/**
 * 关闭指定通知
 * @param {number} id - 通知ID
 */
export function closeNotification(id) {
  getInstance().close(id)
}

/**
 * 关闭所有通知
 */
export function closeAllNotifications() {
  getInstance().closeAll()
}

/**
 * Vue Composable: useNotification
 *
 * 用法:
 * ```js
 * import { useNotification } from '@/composables/useNotification'
 *
 * const { success, error, warning, info } = useNotification()
 *
 * success('操作成功')
 * error('操作失败')
 * ```
 */
export function useNotification() {
  return {
    show: showNotification,
    success: showSuccess,
    error: showError,
    warning: showWarning,
    info: showInfo,
    close: closeNotification,
    closeAll: closeAllNotifications
  }
}

/**
 * 销毁通知系统（用于测试或清理）
 */
export function destroyNotification() {
  if (notificationApp) {
    notificationApp.unmount()
    notificationApp = null
  }
  if (notificationInstance) {
    notificationInstance = null
  }
  const container = document.getElementById('global-notification-container')
  if (container) {
    container.remove()
  }
}

export default useNotification
