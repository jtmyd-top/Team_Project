// 重构后的设置应用主文件
import { useUserStore } from './stores/user.js';
import SettingsProfile from './components/settings/SettingsProfile.vue';
import SettingsSecurity from './components/settings/SettingsSecurity.vue';
import SettingsAccount from './components/settings/SettingsAccount.vue';
import SettingsNotifications from './components/settings/SettingsNotifications.vue';
import SettingsTheme from './components/settings/SettingsTheme.vue';

const { createApp, ref, watch, onMounted, computed } = Vue;
const { createPinia } = Pinia;

// 创建应用实例
const app = createApp({
  delimiters: ['[[', ']]'],
  
  components: {
    SettingsProfile,
    SettingsSecurity,
    SettingsAccount,
    SettingsNotifications,
    SettingsTheme,
  },

  setup() {
    const pinia = createPinia();
    
    // 从localStorage读取上次激活的标签页
    const active = ref(localStorage.getItem('settings_active_tab') || 'profile');

    // 组件映射
    const componentMap = {
      profile: 'SettingsProfile',
      security: 'SettingsSecurity',
      account: 'SettingsAccount',
      notifications: 'SettingsNotifications',
      theme: 'SettingsTheme',
    };

    // 当前激活的组件
    const activeComponent = computed(() => componentMap[active.value] || 'SettingsProfile');

    // 监听标签页变化，保存到localStorage
    watch(active, (newValue) => {
      localStorage.setItem('settings_active_tab', newValue);
    });

    // 组件挂载时初始化用户store
    onMounted(() => {
      const userStore = useUserStore();
      
      // 从window.SETTINGS_INITIAL加载初始数据（已在store中处理）
      console.log('Settings app mounted, user:', userStore.nickname);
    });

    return {
      active,
      activeComponent,
    };
  },
});

// 使用Pinia状态管理
app.use(createPinia());

// 使用Element Plus
app.use(ElementPlus);

// 挂载应用
app.mount('#settings-app');
