// Vite 入口文件 - 用于构建设置页面
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import {
  ElAlert,
  ElAvatar,
  ElBadge,
  ElButton,
  ElColorPicker,
  ElDialog,
  ElDivider,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElRadio,
  ElRadioGroup,
  ElSkeleton,
  ElSlider,
  ElStep,
  ElSteps,
  ElSwitch,
  ElTag,
  ElTooltip,
  ElUpload
} from 'element-plus';
import 'element-plus/es/components/alert/style/css';
import 'element-plus/es/components/avatar/style/css';
import 'element-plus/es/components/badge/style/css';
import 'element-plus/es/components/button/style/css';
import 'element-plus/es/components/color-picker/style/css';
import 'element-plus/es/components/dialog/style/css';
import 'element-plus/es/components/divider/style/css';
import 'element-plus/es/components/empty/style/css';
import 'element-plus/es/components/form/style/css';
import 'element-plus/es/components/form-item/style/css';
import 'element-plus/es/components/input/style/css';
import 'element-plus/es/components/input-number/style/css';
import 'element-plus/es/components/message/style/css';
import 'element-plus/es/components/message-box/style/css';
import 'element-plus/es/components/radio/style/css';
import 'element-plus/es/components/radio-group/style/css';
import 'element-plus/es/components/skeleton/style/css';
import 'element-plus/es/components/slider/style/css';
import 'element-plus/es/components/step/style/css';
import 'element-plus/es/components/steps/style/css';
import 'element-plus/es/components/switch/style/css';
import 'element-plus/es/components/tag/style/css';
import 'element-plus/es/components/tooltip/style/css';
import 'element-plus/es/components/upload/style/css';

// 导入 API 服务（会自动挂载到 window.apiService）
import { apiService } from '@services/apiService';

// 导入主应用组件
import SettingsApp from '@components/settings/SettingsApp/index.vue';
import { registerElementComponents } from './element-plus-components';

// 导入用户状态管理
import { useUserStore } from '@stores/user.js';

// 全局主题应用函数
const applyGlobalTheme = (themeSettings) => {
  const defaultSettings = {
    mode: 'light',
    primary_color: '#409EFF',
    font_size: 14,
    compact_mode: false,
    animations: true
  };

  const settings = { ...defaultSettings, ...themeSettings };

  // 应用主题到页面
  document.documentElement.setAttribute('data-theme', settings.mode);
  document.documentElement.style.setProperty('--primary-color', settings.primary_color);
  document.documentElement.style.setProperty('--font-size-base', settings.font_size + 'px');

  if (settings.compact_mode) {
    document.body.classList.add('compact-mode');
  } else {
    document.body.classList.remove('compact-mode');
  }

  if (!settings.animations) {
    document.body.classList.add('no-animations');
  } else {
    document.body.classList.remove('no-animations');
  }
};

// 初始化主题设置
const initializeTheme = async () => {
  try {
    // 先尝试从服务器获取主题设置
    const data = await apiService.getThemeSettings();
    if (data.status === 'success' && data.settings) {
      applyGlobalTheme(data.settings);
    }
  } catch (error) {
    console.warn('无法加载主题设置，使用默认主题:', error);
    // 使用默认主题
    applyGlobalTheme({});
  }
};

// 创建 Vue 应用
const app = createApp(SettingsApp);

// 使用 Pinia 状态管理
const pinia = createPinia();
app.use(pinia);

// 使用 Element Plus UI 组件库
registerElementComponents(app, [
  ElAlert,
  ElAvatar,
  ElBadge,
  ElButton,
  ElColorPicker,
  ElDialog,
  ElDivider,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElRadio,
  ElRadioGroup,
  ElSkeleton,
  ElSlider,
  ElStep,
  ElSteps,
  ElSwitch,
  ElTag,
  ElTooltip,
  ElUpload
]);

// 初始化用户数据（从 Django 模板注入的全局变量）
if (window.SETTINGS_INITIAL) {
  const userStore = useUserStore();
  userStore.initializeFromServer(window.SETTINGS_INITIAL);
}

// 初始化主题设置（在挂载前执行，确保主题立即生效）
initializeTheme().then(() => {
  console.log('主题初始化完成');
}).catch(error => {
  console.error('主题初始化失败:', error);
});

// 挂载到 DOM
app.mount('#settings-app');
