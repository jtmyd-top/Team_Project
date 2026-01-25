/**
 * 全局主题管理器
 * 负责在所有页面应用和管理用户主题设置
 */

class ThemeManager {
  constructor() {
    this.defaultSettings = {
      mode: 'light',
      primary_color: '#409EFF',
      font_size: 14,
      compact_mode: false,
      animations: true
    };

    this.currentSettings = { ...this.defaultSettings };
    this.isInitialized = false;
  }

  /**
   * 应用主题设置到页面
   */
  applyTheme(settings = {}) {
    const mergedSettings = { ...this.defaultSettings, ...settings };
    this.currentSettings = mergedSettings;

  
    // 设置主题模式属性
    document.documentElement.setAttribute('data-theme', mergedSettings.mode);
    
    // 设置CSS变量
    document.documentElement.style.setProperty('--primary-color', mergedSettings.primary_color);
    document.documentElement.style.setProperty('--font-size-base', mergedSettings.font_size + 'px');
    
    // 应用紧凑模式
    if (mergedSettings.compact_mode) {
      document.body.classList.add('compact-mode');
      
    } else {
      document.body.classList.remove('compact-mode');
      
    }

    // 应用动画设置
    if (!mergedSettings.animations) {
      document.body.classList.add('no-animations');
      
    } else {
      document.body.classList.remove('no-animations');
      
    }

    // 保存到localStorage作为缓存
    try {
      localStorage.setItem('theme-settings', JSON.stringify(mergedSettings));
    } catch (error) {
      // 保存失败，忽略
    }
  }

  /**
   * 从服务器加载主题设置
   */
  async loadFromServer() {
    try {
      // 检查是否已定义API服务
      if (window.apiService && window.apiService.getThemeSettings) {
        const data = await window.apiService.getThemeSettings();
        if (data.status === 'success' && data.settings) {
          this.applyTheme(data.settings);
          return data.settings;
        }
      }
    } catch (error) {
      // 加载失败，忽略
    }
    return null;
  }

  /**
   * 从localStorage加载缓存的设置
   */
  loadFromCache() {
    try {
      const cached = localStorage.getItem('theme-settings');
      if (cached) {
        const settings = JSON.parse(cached);
        this.applyTheme(settings);
        return settings;
      }
    } catch (error) {
      // 加载失败，忽略
    }
    return null;
  }

  /**
   * 初始化主题系统
   */
  async initialize() {
    if (this.isInitialized) {
      return this.currentSettings;
    }

    try {
      // 1. 首先尝试从缓存加载（快速显示）
      const cachedSettings = this.loadFromCache();

      // 2. 立即应用默认主题或缓存主题
      this.applyTheme(cachedSettings || this.defaultSettings);

      // 3. 然后尝试从服务器加载（可能覆盖缓存）
      try {
        const serverSettings = await this.loadFromServer();
        if (serverSettings) {
          this.applyTheme(serverSettings);
        }
      } catch (serverError) {
        // 服务器加载失败，忽略
      }

      this.isInitialized = true;
      return this.currentSettings;

    } catch (error) {
      // 确保至少应用默认主题
      this.applyTheme(this.defaultSettings);
      this.isInitialized = true;
      return this.currentSettings;
    }
  }

  /**
   * 获取当前主题设置
   */
  getCurrentSettings() {
    return { ...this.currentSettings };
  }

  /**
   * 监听系统主题变化（自动模式）
   */
  watchSystemTheme() {
    if (window.matchMedia) {
      const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');

      const handleThemeChange = (e) => {
        if (this.currentSettings.mode === 'auto') {
          // 如果是自动模式，重新应用主题以触发CSS媒体查询
          this.applyTheme(this.currentSettings);
        }
      };

      // 监听系统主题变化
      darkModeQuery.addListener(handleThemeChange);
    }
  }
}

// 创建全局主题管理器实例
window.themeManager = new ThemeManager();

// 自动初始化
document.addEventListener('DOMContentLoaded', () => {
  // 确保在页面加载完成后初始化主题
  window.themeManager.initialize().then(() => {
    // 监听系统主题变化
    window.themeManager.watchSystemTheme();
  }).catch(() => {});
});

// 如果页面已经加载完成，立即初始化
if (document.readyState === 'loading') {
  // DOM还在加载中，等待DOMContentLoaded事件
} else {
  // DOM已经加载完成，立即初始化
  window.themeManager.initialize().catch(() => {});
}

// 导出为模块（如果支持ES6模块）
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ThemeManager;
}