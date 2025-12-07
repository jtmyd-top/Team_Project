<template>
  <div>
    <el-alert
      title="主题设置"
      type="info"
      :closable="false"
      style="margin-bottom: 24px;">
      自定义您的界面外观
    </el-alert>

    <div class="theme-section">
      <h3 class="section-title">主题模式</h3>
      <el-radio-group v-model="theme.mode" @change="saveTheme" class="theme-radio-group">
        <el-radio label="light" border>
          <i class="fas fa-sun"></i>
          <span>浅色模式</span>
        </el-radio>
        <el-radio label="dark" border>
          <i class="fas fa-moon"></i>
          <span>深色模式</span>
        </el-radio>
        <el-radio label="auto" border>
          <i class="fas fa-adjust"></i>
          <span>自动切换</span>
        </el-radio>
      </el-radio-group>
    </div>

    <el-divider />

    <div class="theme-section">
      <h3 class="section-title">主题色</h3>
      <div class="color-picker-container">
        <el-color-picker 
          v-model="theme.primary_color" 
          @change="saveTheme"
          show-alpha 
          :predefine="predefineColors" />
        <span class="color-hint">选择您喜欢的主题色</span>
      </div>
    </div>

    <el-divider />

    <div class="theme-section">
      <h3 class="section-title">字体大小</h3>
      <el-slider 
        v-model="theme.font_size" 
        @change="saveTheme"
        :min="12"
        :max="20"
        :step="1"
        show-stops
        :marks="fontSizeMarks"
        style="max-width: 400px;" />
      <div class="font-preview" :style="{ fontSize: theme.font_size + 'px' }">
        预览文字：这是一段示例文本 ({{ theme.font_size }}px)
      </div>
    </div>

    <el-divider />

    <div class="theme-section">
      <h3 class="section-title">其他设置</h3>
      <el-form label-position="left" label-width="120px">
        <el-form-item label="紧凑模式">
          <el-switch v-model="theme.compact_mode" @change="saveTheme" />
          <div class="form-hint">使用更紧凑的布局</div>
        </el-form-item>

        <el-form-item label="显示动画">
          <el-switch v-model="theme.animations" @change="saveTheme" />
          <div class="form-hint">启用界面过渡动画</div>
        </el-form-item>
      </el-form>
    </div>

    <div class="theme-actions">
      <el-button @click="resetTheme">重置为默认主题</el-button>
    </div>
  </div>
</template>

<script setup>
import { reactive, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { apiService } from '../../services/apiService.js';

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
      ElMessage.error(data.message || '保存失败');
    }
  } catch (error) {
    ElMessage.error(error.message || '网络错误');
  }
};

const applyTheme = () => {
  // 应用主题到页面
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
</script>

<style scoped>
.theme-section {
  padding: 24px;
  border-radius: 8px;
}

.theme-section:nth-of-type(odd) {
  background-color: #fff;
}

.theme-section:nth-of-type(even) {
  background-color: #f9f9fa;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
}

.theme-radio-group {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.theme-radio-group :deep(.el-radio) {
  margin-right: 0;
}

.theme-radio-group i {
  margin-right: 8px;
}

.color-picker-container {
  display: flex;
  align-items: center;
  gap: 16px;
}

.color-hint {
  color: #909399;
  font-size: 14px;
}

.font-preview {
  margin-top: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 4px;
  transition: font-size 0.3s;
}

.form-hint {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}

.theme-actions {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #e4e7ed;
}
</style>
