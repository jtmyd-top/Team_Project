// services/apiService.js - 统一的API请求服务
import { request } from '/static/JS/utils/request.js';

const csrfToken = window.SETTINGS_INITIAL?.csrfToken || "";
const csrfHeader = { "X-CSRFToken": csrfToken };

/**
 * 统一的 POST 请求封装
 */
async function postRequest(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { 
      "Content-Type": "application/json", 
      ...csrfHeader 
    },
    body: JSON.stringify(body),
  });
  
  const data = await response.json();
  
  if (!response.ok) {
    throw new Error(data.message || '请求失败');
  }
  
  return data;
}

/**
 * 统一的 GET 请求封装
 */
async function getRequest(url, params = {}) {
  const queryString = new URLSearchParams(params).toString();
  const fullUrl = queryString ? `${url}?${queryString}` : url;
  
  const response = await fetch(fullUrl, {
    method: "GET",
    headers: csrfHeader,
  });
  
  const data = await response.json();
  
  if (!response.ok) {
    throw new Error(data.message || '请求失败');
  }
  
  return data;
}

/**
 * API 服务对象
 */
export const apiService = {
  // ==================== 个人资料相关 ====================
  
  /**
   * 更新个人资料（昵称或个性签名）
   */
  updateProfile(payload) {
    return postRequest(window.API_ENDPOINTS.updateProfile, payload);
  },
  
  /**
   * 检查用户名是否可用
   */
  checkUsername(username) {
    return getRequest('/check-username/', { username });
  },
  
  /**
   * 切换点赞状态
   */
  toggleLike() {
    return postRequest(window.API_ENDPOINTS.toggleLike || '/api/toggle-like/', {});
  },
  
  // ==================== 邮箱相关 ====================
  
  /**
   * 检查邮箱是否可用
   */
  checkEmail(email, excludeSelf = false) {
    return getRequest(window.API_ENDPOINTS.checkEmail, { 
      email, 
      exclude_self: excludeSelf ? '1' : '0' 
    });
  },
  
  /**
   * 发送邮箱验证码
   */
  sendEmailCode(payload) {
    return postRequest(window.API_ENDPOINTS.sendEmailCode, payload);
  },
  
  /**
   * 修改邮箱
   */
  updateEmail(payload) {
    return postRequest(window.API_ENDPOINTS.updateEmail, payload);
  },
  
  // ==================== 账户安全相关 ====================
  
  /**
   * 修改密码
   */
  changePassword(payload) {
    return postRequest('/api/security/change-password/', payload);
  },
  
  /**
   * 发送操作2FA验证码
   */
  sendOperation2FA() {
    return postRequest('/api/security/send-operation-2fa/', {});
  },
  
  /**
   * 启用2FA
   */
  enable2FA(method) {
    return postRequest('/api/security/enable-2fa/', { method });
  },
  
  /**
   * 验证2FA设置
   */
  verify2FASetup(code) {
    return postRequest('/api/security/verify-2fa-setup/', { code });
  },
  
  /**
   * 禁用2FA
   */
  disable2FA(password) {
    return postRequest('/api/security/disable-2fa/', { password });
  },
  
  /**
   * 重新生成备用验证码
   */
  regenerateBackupCodes(password) {
    return postRequest('/api/security/regenerate-backup-codes/', { password });
  },
  
  // ==================== 通知偏好相关 ====================
  
  /**
   * 获取通知偏好设置
   */
  getNotificationPreferences() {
    return getRequest('/api/notification-preferences/');
  },
  
  /**
   * 更新通知偏好设置
   */
  updateNotificationPreferences(preferences) {
    return postRequest('/api/notification-preferences/', preferences);
  },
  
  // ==================== 主题设置相关 ====================
  
  /**
   * 获取主题设置
   */
  getThemeSettings() {
    return getRequest('/api/theme-settings/');
  },
  
  /**
   * 更新主题设置
   */
  updateThemeSettings(settings) {
    return postRequest('/api/theme-settings/', settings);
  },
};

export default apiService;
