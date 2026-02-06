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
import { useSettingsTheme } from '@composables/useSettingsTheme.js';
import '@/assets/styles/components/settings-theme.css';

const {
  theme,
  predefineColors,
  fontSizeMarks,
  saveTheme,
  resetTheme
} = useSettingsTheme();
</script>
