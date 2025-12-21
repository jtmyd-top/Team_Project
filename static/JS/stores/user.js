// stores/user.js - 用户状态管理
import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', {
  state: () => {
    // 兼容两种数据结构：顶层字段或嵌套在 user 对象中
    const initial = window.SETTINGS_INITIAL || {};
    const userData = initial.user || initial;
    
    return {
      // 基本信息
      nickname: userData.nickname || "",
      email: userData.email || "",
      bio: userData.bio || "",
      
      // 头像和横幅
      avatar: userData.avatar || "/static/img/default-avatar.png",
      banner: userData.banner || "",
      bannerIsVideo: false,
      
      // 统计信息
      likes_count: userData.likes_count || 0,
      notes_count: userData.notes_count || 0,
      views_count: userData.views_count || 0,
      is_liked: userData.is_liked || false,
      
      // 安全设置
      two_fa_enabled: userData.two_fa_enabled || false,
      two_fa_method: userData.two_fa_method || 'totp',
    
      // 通知偏好
      notifications: {
        notify_login: userData.notify_login !== undefined ? userData.notify_login : true,
        notify_password_change: userData.notify_password_change !== undefined ? userData.notify_password_change : true,
        notify_password_reset: userData.notify_password_reset !== undefined ? userData.notify_password_reset : true,
        notify_note_activities: userData.notify_note_activities !== undefined ? userData.notify_note_activities : false,
        notify_profile_likes: userData.notify_profile_likes !== undefined ? userData.notify_profile_likes : true,
      },
      
      // 主题设置
      theme: {
        mode: userData.theme?.mode || 'system',
        primaryColor: userData.theme?.primaryColor || '#2196F3',
        layout: userData.theme?.layout || 'default'
      }
    };
  },
  
  actions: {
    // 从服务器初始化数据
    initializeFromServer(data) {
      if (!data || !data.user) return;
      
      const { user } = data;
      this.nickname = user.nickname || this.nickname;
      this.email = user.email || this.email;
      this.bio = user.bio || this.bio;
      this.avatar = user.avatar || this.avatar;
      this.banner = user.banner || this.banner;
      this.likes_count = user.likes_count || this.likes_count;
      this.notes_count = user.notes_count || this.notes_count;
      this.views_count = user.views_count || this.views_count;
      this.is_liked = user.is_liked || this.is_liked;
      this.two_fa_enabled = user.twoFaEnabled || this.two_fa_enabled;
      this.two_fa_method = user.twoFaMethod || this.two_fa_method;
      
      // 检查横幅是否是视频
      if (this.banner) {
        const videoExtensions = ['.mp4', '.webm', '.ogg'];
        this.bannerIsVideo = videoExtensions.some(ext => 
          this.banner.toLowerCase().endsWith(ext)
        );
      }
    },
    
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
      console.log('updateNickname called with:', newNickname);
      console.log('Previous nickname:', this.nickname);
      this.nickname = newNickname;
      console.log('Current nickname:', this.nickname);

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
