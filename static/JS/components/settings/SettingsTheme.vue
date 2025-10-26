<template>
  <div class="settings-content-card">
    <div class="form-section">
      <h3 class="form-section-title">外观主题</h3>
      <div class="theme-settings">
        <div class="theme-option">
          <label>主题模式：</label>
          <el-radio-group v-model="userStore.theme.mode" @change="saveThemeSettings">
            <el-radio label="light">浅色</el-radio>
            <el-radio label="dark">深色</el-radio>
            <el-radio label="system">跟随系统</el-radio>
          </el-radio-group>
        </div>

        <div class="theme-option">
          <label>主色调：</label>
          <el-color-picker 
            v-model="userStore.theme.primaryColor" 
            show-alpha
            @change="saveThemeSettings"
            :predefine="predefinedColors"
          ></el-color-picker>
        </div>

        <div class="theme-option">
          <label>布局模式：</label>
          <el-select v-model="userStore.theme.layout" @change="saveThemeSettings">
            <el-option label="默认布局" value="default"></el-option>
            <el-option label="紧凑布局" value="compact"></el-option>
            <el-option label="宽屏布局" value="wide"></el-option>
          </el-select>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useUserStore } from '../../stores/user.js';
import { apiService } from '../../services/apiService.js';
import { ElMessage } from 'element-plus';

const userStore = useUserStore();

const predefinedColors = ref([
  '#2196F3', // 默认蓝
  '#673AB7', // 深紫
  '#E91E63', // 粉红
  '#4CAF50', // 绿色
  '#FF9800', // 橙色
  '#795548', // 棕色
  '#9C27B0'  // 紫色
]);

/**
 * 保存主题设置
 */
const saveThemeSettings = async () => {
  try {
    const data = await apiService.updateThemeSettings({
      mode: userStore.theme.mode,
      primaryColor: userStore.theme.primaryColor,
      layout: userStore.theme.layout
    });
    
    if (data.status === "success") {
      ElMessage.success("主题设置已保存");
    } else {
      ElMessage.error(data.message || "保存失败");
    }
  } catch (error) {
    ElMessage.error(error.message || "网络错误");
    console.error("保存主题设置失败:", error);
  }
};

/**
 * 加载主题设置
 */
const loadThemeSettings = async () => {
  try {
    const data = await apiService.getThemeSettings();
    if (data.status === "success" && data.theme_settings) {
      userStore.updateTheme({
        mode: data.theme_settings.mode || 'system',
        primaryColor: data.theme_settings.primary_color || '#2196F3',
        layout: data.theme_settings.layout || 'default'
      });
    }
  } catch (error) {
    console.error("加载主题设置失败:", error);
  }
};

// 组件挂载时加载主题设置
onMounted(() => {
  loadThemeSettings();
});
</script>

<style scoped>
.settings-content-card {
  background: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.form-section {
  margin-bottom: 32px;
}

.form-section-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
}

.theme-settings {
  max-width: 600px;
}

.theme-option {
  display: flex;
  align-items: center;
  margin-bottom: 24px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.theme-option label {
  min-width: 120px;
  font-weight: 500;
  color: #606266;
}
</style>
