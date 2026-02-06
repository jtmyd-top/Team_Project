<template>
  <div class="breadcrumb-container">
    <nav class="breadcrumb">
      <!-- 固定的"我的空间"入口 -->
      <span
        class="breadcrumb-item root"
        @click="handleRootClick"
      >
        <i class="fas fa-home"></i>
        我的空间
      </span>

      <!-- 分隔符 -->
      <template v-if="items.length > 0">
        <span class="separator">/</span>
      </template>

      <!-- 面包屑项 -->
      <template v-for="(item, index) in items" :key="item.id">
        <span
          class="breadcrumb-item"
          :class="{ 'is-current': index === items.length - 1 }"
          @click="handleItemClick(item, index)"
        >
          {{ item.name }}

          <!-- 快速切换下拉菜单（非最后一项时显示） -->
          <button
            v-if="index < items.length - 1"
            class="dropdown-trigger"
            @click.stop="toggleDropdown(item, $event)"
          >
            <i class="fas fa-chevron-down"></i>
          </button>
        </span>

        <!-- 分隔符 -->
        <span v-if="index < items.length - 1" class="separator">/</span>
      </template>
    </nav>

    <!-- 快速切换下拉菜单 -->
    <div
      v-if="dropdownVisible"
      class="dropdown-menu"
      :style="dropdownStyle"
      @click.stop
    >
      <div class="dropdown-header">
        <span>切换到同级文件夹</span>
      </div>
      <div class="dropdown-content">
        <div
          v-for="folder in siblingFolders"
          :key="folder.id"
          class="dropdown-item"
          :class="{ 'is-active': folder.id === currentItemId }"
          @click="handleSiblingSelect(folder)"
        >
          <i class="fas fa-folder"></i>
          <span>{{ folder.name }}</span>
        </div>
        <div v-if="siblingFolders.length === 0" class="dropdown-empty">
          没有同级文件夹
        </div>
      </div>
    </div>

    <!-- 点击遮罩层关闭下拉菜单 -->
    <div
      v-if="dropdownVisible"
      class="dropdown-overlay"
      @click="closeDropdown"
    ></div>
  </div>
</template>

<script setup>
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import '@/assets/styles/components/breadcrumb.css'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['navigate', 'switch-folder'])

const {
  dropdownVisible,
  dropdownStyle,
  currentItemId,
  siblingFolders,
  handleRootClick,
  handleItemClick,
  toggleDropdown,
  closeDropdown,
  handleSiblingSelect
} = useBreadcrumb(props, emit)
</script>
