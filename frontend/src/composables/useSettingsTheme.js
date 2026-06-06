import { reactive, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { apiService } from '../services/apiService.js';

export function useSettingsTheme() {
  const theme = reactive({
    mode: 'light',
    primary_color: '#409EFF',
    font_size: 14,
    compact_mode: false,
    animations: true
  });

  const predefineColors = [
    '#409EFF',
    '#67C23A',
    '#E6A23C',
    '#F56C6C',
    '#909399',
    '#ff4500',
    '#ff8c00',
    '#ffd700',
    '#90ee90',
    '#00ced1',
    '#1e90ff',
    '#c71585',
  ];

  const fontSizeMarks = {
    12: '小',
    14: '默认',
    16: '中',
    18: '大',
    20: '特大'
  };

  const loadTheme = async () => {
    try {
      const data = await apiService.getThemeSettings();
      if (data.status === 'success' && data.settings) {
        Object.assign(theme, data.settings);
        applyTheme();
      }
    } catch (error) {
      console.error('加载主题设置失败:', error);
    }
  };

  const saveTheme = async () => {
    try {
      const data = await apiService.updateThemeSettings(theme);
      if (data.status === 'success') {
        ElMessage.success('主题设置已保存');
        applyTheme();
      } else {
        ElMessage.error(data.message || data.error || '保存失败');
      }
    } catch (error) {
      ElMessage.error(error.message || '网络错误');
    }
  };

  const applyTheme = () => {
    // 使用全局主题管理器应用主题
    if (window.themeManager) {
      window.themeManager.applyTheme(theme);
    } else {
      // 回退到直接DOM操作
      document.documentElement.setAttribute('data-theme', theme.mode);
      document.documentElement.style.setProperty('--primary-color', theme.primary_color);
      document.documentElement.style.setProperty('--font-size-base', theme.font_size + 'px');

      if (theme.compact_mode) {
        document.body.classList.add('compact-mode');
      } else {
        document.body.classList.remove('compact-mode');
      }

      if (!theme.animations) {
        document.body.classList.add('no-animations');
      } else {
        document.body.classList.remove('no-animations');
      }
    }
  };

  const resetTheme = async () => {
    try {
      await ElMessageBox.confirm(
        '确定要重置为默认主题吗？此操作不可撤销。',
        '确认重置',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        }
      );

      // 重置为默认值
      theme.mode = 'light';
      theme.primary_color = '#409EFF';
      theme.font_size = 14;
      theme.compact_mode = false;
      theme.animations = true;

      await saveTheme();
    } catch {
      // 用户取消
    }
  };

  onMounted(() => {
    loadTheme();
  });

  return {
    theme,
    predefineColors,
    fontSizeMarks,
    loadTheme,
    saveTheme,
    applyTheme,
    resetTheme
  };
}
