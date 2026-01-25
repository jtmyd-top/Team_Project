/**
 * useTheme - 主题管理 Composable
 *
 * 提供主题切换、同步等功能
 */

import { ref, watch } from 'vue'

// 获取初始主题状态
const getInitialTheme = () => {
  try {
    const cached = localStorage.getItem('theme-settings')
    if (cached) {
      const settings = JSON.parse(cached)
      return settings.mode !== 'dark'
    }
  } catch (e) {
    console.warn('读取主题缓存失败:', e)
  }
  return true
}

// 全局共享的主题状态
const isLightTheme = ref(getInitialTheme())

/**
 * 主题管理 Composable
 * @param {Object} context - 上下文对象
 * @param {Function} context.themeApi - 主题 API
 * @param {Object} context.initialData - 初始数据（包含 csrf_token）
 * @returns {Object} 主题管理方法和状态
 */
export function useTheme({ themeApi, initialData } = {}) {
  const localTheme = ref(isLightTheme.value)

  /**
   * 应用主题到 DOM
   * @param {boolean} isLight - 是否为浅色主题
   */
  const applyThemeToDOM = (isLight) => {
    const newMode = isLight ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', newMode)
  }

  /**
   * 保存主题到 localStorage
   * @param {boolean} isLight - 是否为浅色主题
   */
  const saveThemeToStorage = (isLight) => {
    const newMode = isLight ? 'light' : 'dark'
    const settings = { mode: newMode }

    try {
      localStorage.setItem('theme-settings', JSON.stringify(settings))
    } catch (e) {
      console.warn('保存主题到 localStorage 失败:', e)
    }
  }

  /**
   * 保存主题到服务器
   * @param {boolean} isLight - 是否为浅色主题
   */
  const saveThemeToServer = async (isLight) => {
    if (!themeApi || !initialData?.value?.csrf_token) return

    const newMode = isLight ? 'light' : 'dark'
    const settings = { mode: newMode }

    try {
      await themeApi.save(settings, initialData.value.csrf_token)
    } catch (e) {
      console.warn('保存主题到服务器失败:', e)
    }
  }

  /**
   * 使用全局 themeManager 应用主题
   * @param {boolean} isLight - 是否为浅色主题
   */
  const applyThemeWithManager = (isLight) => {
    if (window.themeManager) {
      const newMode = isLight ? 'light' : 'dark'
      window.themeManager.applyTheme({ mode: newMode })
    }
  }

  /**
   * 从服务器同步主题设置
   */
  const syncThemeFromServer = async () => {
    if (!themeApi) return

    try {
      const settings = await themeApi.fetch()
      if (settings) {
        const serverMode = settings.mode || 'light'
        const isServerLight = serverMode !== 'dark'
        localTheme.value = isServerLight
        isLightTheme.value = isServerLight

        applyThemeToDOM(isServerLight)
        applyThemeWithManager(isServerLight)
      }
    } catch (e) {
      console.warn('同步主题设置失败:', e)
    }
  }

  /**
   * 从全局 themeManager 同步主题
   */
  const syncThemeFromManager = () => {
    if (window.themeManager) {
      const s = window.themeManager.getCurrentSettings()
      const isLight = s.mode !== 'dark'
      localTheme.value = isLight
      isLightTheme.value = isLight
    }
  }

  /**
   * 切换主题
   */
  const toggleTheme = async () => {
    const newThemeValue = !localTheme.value
    localTheme.value = newThemeValue
    isLightTheme.value = newThemeValue

    applyThemeToDOM(newThemeValue)
    applyThemeWithManager(newThemeValue)
    saveThemeToStorage(newThemeValue)

    // 异步保存到服务器
    saveThemeToServer(newThemeValue)
  }

  /**
   * 设置主题
   * @param {boolean} isLight - 是否为浅色主题
   */
  const setTheme = async (isLight) => {
    if (localTheme.value === isLight) return

    localTheme.value = isLight
    isLightTheme.value = isLight

    applyThemeToDOM(isLight)
    applyThemeWithManager(isLight)
    saveThemeToStorage(isLight)

    // 异步保存到服务器
    saveThemeToServer(isLight)
  }

  // 监听本地主题变化，同步全局状态
  watch(localTheme, (newVal) => {
    isLightTheme.value = newVal
  })

  return {
    // 状态
    isLightTheme: localTheme,
    // 方法
    toggleTheme,
    setTheme,
    applyThemeToDOM,
    saveThemeToStorage,
    saveThemeToServer,
    syncThemeFromServer,
    syncThemeFromManager
  }
}

/**
 * 获取全局主题状态（用于非组件中）
 */
export function getGlobalTheme() {
  return isLightTheme
}

/**
 * 导出供直接使用的主题状态
 */
export { isLightTheme }
