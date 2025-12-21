// services/apiService.js - 统一的API请求服务
// 改为直接使用fetch，避免ES6模块问题

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

  let data;
  try {
    data = await response.json();
  } catch (e) {
    // 如果不是JSON格式，可能是HTML错误页面
    const text = await response.text();
    if (response.status === 404) {
      throw new Error('API端点不存在 (404)');
    } else if (response.status === 403) {
      throw new Error('访问被拒绝 (403)');
    } else if (response.status === 500) {
      throw new Error('服务器内部错误 (500)');
    } else {
      throw new Error(`请求失败 (${response.status})`);
    }
  }

  if (!response.ok) {
    // 创建一个包含更多信息的错误对象
    const error = new Error('请求失败');
    error.response = {
      status: response.status,
      data: data
    };
    throw error;
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

  let data;
  try {
    data = await response.json();
  } catch (e) {
    // 如果不是JSON格式，可能是HTML错误页面
    const text = await response.text();
    if (response.status === 404) {
      throw new Error('API端点不存在 (404)');
    } else if (response.status === 403) {
      throw new Error('访问被拒绝 (403)');
    } else if (response.status === 500) {
      throw new Error('服务器内部错误 (500)');
    } else {
      throw new Error(`请求失败 (${response.status})`);
    }
  }

  if (!response.ok) {
    // 创建一个包含更多信息的错误对象
    // 优先使用 error 字段，如果没有则使用 message
    const errorMessage = data.error || data.message || '请求失败';
    const error = new Error(errorMessage);
    error.response = {
      status: response.status,
      data: data
    };
    throw error;
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
    sendEmailCode(email, purpose = 'register', captchaPreValidated = false) {
      return postRequest('/send-email-code/', {
        email,
        purpose,
        captcha_pre_validated: captchaPreValidated
      });
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

// 将apiService挂载到window对象上，使其全局可用
window.apiService = apiService;

// ES6 导出
export { apiService };

// 默认导出
export default apiService;
