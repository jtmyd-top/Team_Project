// stores/user.js - 用户状态管理
import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', {
  state: () => ({
    // 基本信息
    nickname: window.SETTINGS_INITIAL?.nickname || "",
    email: window.SETTINGS_INITIAL?.email || "",
    bio: window.SETTINGS_INITIAL?.bio || "",
    
    // 头像和横幅
    avatar: window.SETTINGS_INITIAL?.avatar || "/static/img/default-avatar.png",
    banner: window.SETTINGS_INITIAL?.banner || "",
    bannerIsVideo: false,
    
    // 统计信息
    likes_count: window.SETTINGS_INITIAL?.likes_count || 0,
    notes_count: window.SETTINGS_INITIAL?.notes_count || 0,
    views_count: window.SETTINGS_INITIAL?.views_count || 0,
    is_liked: window.SETTINGS_INITIAL?.is_liked || false,
    
    // 安全设置
    two_fa_enabled: window.SETTINGS_INITIAL?.two_fa_enabled || false,
    two_fa_method: window.SETTINGS_INITIAL?.two_fa_method || 'totp',
    
    // 通知偏好
    notifications: {
      notify_login: true,
      notify_password_change: true,
      notify_password_reset: true,
      notify_note_activities: false,
      notify_profile_likes: true,
    },
    
    // 主题设置
    theme: {
      mode: 'system',
      primaryColor: '#2196F3',
      layout: 'default'
    }
  }),
  
  actions: {
    // 更新头像
    updateAvatar(newAvatarUrl) {
      this.avatar = newAvatarUrl;
      
      // 同步更新导航栏头像
      const navAvatar = document.getElementById("nav-avatar");
      if (navAvatar) {
        navAvatar.src = newAvatarUrl;
      }
    },
    
    // 更新横幅
    updateBanner(newBannerUrl, isVideo = false) {
      this.banner = newBannerUrl;
      this.bannerIsVideo = isVideo;
    },
    
    // 更新昵称
    updateNickname(newNickname) {
      this.nickname = newNickname;
      
      // 同步更新导航栏用户名
      const navUsername = document.getElementById("id_username");
      const navUsername2 = document.getElementsByClassName("username");
      if (navUsername) {
        navUsername.textContent = newNickname;
      }
      for (let i = 0; i < navUsername2.length; i++) {
        navUsername2[i].textContent = newNickname;
      }
    },
    
    // 更新邮箱
    updateEmail(newEmail) {
      this.email = newEmail;
    },
    
    // 更新个性签名
    updateBio(newBio) {
      this.bio = newBio;
    },
    
    // 更新点赞数
    updateLikesCount(newCount) {
      this.likes_count = newCount;
    },
    
    // 切换点赞状态
    toggleLike(newLikedState, newCount) {
      this.is_liked = newLikedState;
      this.likes_count = newCount;
    },
    
    // 更新2FA状态
    update2FAStatus(enabled, method = null) {
      this.two_fa_enabled = enabled;
      if (method) {
        this.two_fa_method = method;
      }
    },
    
    // 更新通知偏好
    updateNotificationPreference(key, value) {
      if (this.notifications.hasOwnProperty(key)) {
        this.notifications[key] = value;
      }
    },
    
    // 批量更新通知偏好
    updateNotificationPreferences(preferences) {
      this.notifications = { ...this.notifications, ...preferences };
    },
    
    // 更新主题设置
    updateTheme(themeSettings) {
      this.theme = { ...this.theme, ...themeSettings };
    }
  },
  
  getters: {
    // 是否已点赞
    isLiked: (state) => state.is_liked,
    
    // 是否启用2FA
    is2FAEnabled: (state) => state.two_fa_enabled,
    
    // 获取完整的用户信息
    userInfo: (state) => ({
      nickname: state.nickname,
      email: state.email,
      bio: state.bio,
      avatar: state.avatar,
      banner: state.banner
    })
  }
})
