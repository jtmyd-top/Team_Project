// services/apiService.js - 统一的API请求服务
// 改为直接使用fetch，避免ES6模块问题

import { getCsrfToken } from '@utils/csrf'
import { extractApiErrorMessage } from '@utils/apiError'

function createResponseError(message, response, data) {
  const error = new Error(message);
  error.response = {
    status: response.status,
    data
  };
  throw error;
}

function extractNonJsonErrorMessage(response, text) {
  const trimmed = (text || '').trim();
  if (trimmed && !trimmed.startsWith('<')) {
    return trimmed;
  }

  if (response.status === 404) {
    return 'API端点不存在 (404)';
  } else if (response.status === 403) {
    return '访问被拒绝 (403)';
  } else if (response.status === 500) {
    return '服务器内部错误 (500)';
  }

  return `请求失败 (${response.status})`;
}

/**
 * 统一的 POST 请求封装
 */
async function postRequest(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken()
    },
    body: JSON.stringify(body),
  });

  // 先读取文本，避免 body stream already read 错误
  const text = await response.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    createResponseError(extractNonJsonErrorMessage(response, text), response, text);
  }

  if (!response.ok) {
    const errorMessage = extractApiErrorMessage(data, '请求失败');
    createResponseError(errorMessage, response, data);
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
    headers: {
      "X-CSRFToken": getCsrfToken()
    },
  });

  // 先读取文本，避免 body stream already read 错误
  const text = await response.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    createResponseError(extractNonJsonErrorMessage(response, text), response, text);
  }

  if (!response.ok) {
    const errorMessage = extractApiErrorMessage(data, '请求失败');
    createResponseError(errorMessage, response, data);
  }

  return data;
}

/**
 * API 服务对象
 */
const apiService = {
  // ==================== 认证相关 ====================

  auth: {
    /**
     * 登录
     */
    login(credentials) {
      return postRequest('/api/login/', credentials);
    },

    /**
     * 注册
     */
    register(userData) {
      return postRequest('/signup/', userData);
    },

    /**
     * 检查用户名是否可用
     */
    checkUsername(username) {
      return getRequest('/check-username/', { username });
    },

    /**
     * 检查邮箱是否可用
     */
    checkEmail(email, excludeSelf = false) {
      return getRequest('/check-email/', {
        email,
        exclude_self: excludeSelf ? '1' : '0'
      });
    },

    /**
     * 发送邮箱验证码
     */
    sendEmailCode(params) {
      // 支持两种调用方式：
      // 1. 旧方式：sendEmailCode(email, purpose)
      // 2. 新方式：sendEmailCode({email, purpose, captcha_type, turnstile_token, image_captcha})
      let requestData = {};

      if (typeof params === 'string') {
        // 旧方式：第一个参数是email，第二个参数是purpose
        requestData = {
          email: arguments[0],
          purpose: arguments[1] || 'register'
        };
      } else if (typeof params === 'object') {
        // 新方式：传递参数对象，支持完整的验证码参数
        requestData = {
          email: params.email,
          purpose: params.purpose || 'register',
          // 验证码参数
          captcha_type: params.captcha_type || 'turnstile',
          turnstile_token: params.turnstile_token || '',
          image_captcha: params.image_captcha || ''
        };
      }

      return postRequest('/send-email-code/', requestData);
    },

    /**
     * 验证2FA
     */
    verify2FA(data) {
      return postRequest('/api/2fa/verify/', data);
    },

    /**
     * 重新发送2FA验证码
     */
    resend2FACode(data) {
      return postRequest('/api/2fa/resend-email/', data);
    },

    /**
     * 登出
     */
    logout() {
      return postRequest('/api/logout/', {});
    }
  },

  // ==================== 个人资料相关 ====================
  
  /**
   * 更新个人资料（昵称或个性签名）
   */
  updateProfile(payload) {
    return postRequest('/update-profile/', payload);
  },


  /**
   * 切换点赞状态
   */
  toggleLike() {
    return postRequest('/api/toggle-like/', {});
  },

  // ==================== 邮箱相关 ====================

  /**
   * 修改邮箱
   */
  updateEmail(payload) {
    return postRequest('/update-email/', payload);
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
  disable2FA(password, code, useBackup = false) {
    return postRequest('/api/security/disable-2fa/', { password, code, use_backup: useBackup });
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

  listNotifications(params = {}) {
    return getRequest('/api/notifications/', params);
  },

  getUnreadNotificationCount() {
    return getRequest('/api/notifications/unread-count/');
  },

  markNotificationsRead(payload = {}) {
    return postRequest('/api/notifications/mark-read/', payload);
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

  // ==================== 保密柜（Vault）相关 ====================

  vault: {
    /**
     * 获取保密柜状态
     */
    getStatus() {
      return getRequest('/api/vault/status/');
    },

    /**
     * 验证保密柜2FA（方案 C：需携带客户端 ECDH 临时公钥）
     */
    verify(code, useBackup = false, clientPubB64 = null) {
      const body = { code, use_backup: useBackup };
      if (clientPubB64) body.client_pub = clientPubB64;
      return postRequest('/api/vault/verify/', body);
    },

    /**
     * 锁定保密柜
     */
    lock() {
      return postRequest('/api/vault/lock/', {});
    },

    /**
     * 发送保密柜邮箱验证码
     */
    sendEmailCode() {
      return postRequest('/api/vault/send-email-code/', {});
    },

    /**
     * 获取保密柜笔记列表
     */
    getNotes() {
      return getRequest('/api/vault/notes/');
    },

    /**
     * 切换笔记保密状态
     */
    toggleNoteSecret(noteId) {
      return postRequest(`/api/notes/${noteId}/toggle-secret/`, {});
    }
  },
};

// 将apiService挂载到window对象上，使其全局可用
window.apiService = apiService;

// ES6 导出
export { apiService };

// 默认导出
export default apiService;
