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
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useSidebarStore } from '@/stores/sidebar'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['navigate', 'switch-folder'])

const sidebarStore = useSidebarStore()

// 状态
const dropdownVisible = ref(false)
const dropdownStyle = ref({})
const currentItemId = ref(null)
const siblingFolders = ref([])

// 方法
function handleRootClick() {
  sidebarStore.backToFolders()
  emit('navigate', null)
}

function handleItemClick(item, index) {
  // 如果是最后一项，不做任何处理
  if (index === props.items.length - 1) return
  
  // 导航到该文件夹
  sidebarStore.enterFolder(item.id)
  emit('navigate', item.id)
}

function toggleDropdown(item, event) {
  if (dropdownVisible.value && currentItemId.value === item.id) {
    closeDropdown()
    return
  }
  
  currentItemId.value = item.id
  
  // 获取同级文件夹
  fetchSiblingFolders(item)
  
  // 计算下拉菜单位置
  const rect = event.target.getBoundingClientRect()
  dropdownStyle.value = {
    top: `${rect.bottom + 5}px`,
    left: `${rect.left}px`
  }
  
  dropdownVisible.value = true
}

function closeDropdown() {
  dropdownVisible.value = false
  currentItemId.value = null
  siblingFolders.value = []
}

function fetchSiblingFolders(item) {
  // 从文件夹树中获取同级文件夹
  const findParentAndSiblings = (folders, targetId, parent = null) => {
    for (const folder of folders) {
      if (folder.id === targetId) {
        // 找到目标，返回父级的所有子项（即同级）
        return parent ? parent.children : folders
      }
      if (folder.children && folder.children.length > 0) {
        const result = findParentAndSiblings(folder.children, targetId, folder)
        if (result) return result
      }
    }
    return null
  }
  
  const siblings = findParentAndSiblings(sidebarStore.folders, item.id)
  siblingFolders.value = siblings || []
}

function handleSiblingSelect(folder) {
  sidebarStore.enterFolder(folder.id)
  emit('switch-folder', folder.id)
  closeDropdown()
}

// 关闭下拉菜单的键盘事件
function handleKeydown(e) {
  if (e.key === 'Escape' && dropdownVisible.value) {
    closeDropdown()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.breadcrumb-container {
  position: relative;
}

.breadcrumb {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  padding: 8px 16px;
  background: var(--bg-secondary, #f5f5f5);
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  font-size: 13px;
}

.breadcrumb-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary, #666);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.2s;
}

.breadcrumb-item:hover {
  color: var(--primary-color, #409eff);
  background: var(--hover-bg, rgba(0,0,0,0.05));
}

.breadcrumb-item.root {
  color: var(--text-secondary, #666);
}

.breadcrumb-item.root i {
  font-size: 12px;
}

.breadcrumb-item.is-current {
  color: var(--text-primary, #333);
  font-weight: 500;
  cursor: default;
  background: transparent;
}

.breadcrumb-item.is-current:hover {
  background: transparent;
  color: var(--text-primary, #333);
}

.separator {
  color: var(--text-tertiary, #ccc);
  font-size: 12px;
}

.dropdown-trigger {
  width: 16px;
  height: 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary, #ccc);
  font-size: 10px;
  border-radius: 3px;
  margin-left: 2px;
}

.dropdown-trigger:hover {
  background: var(--hover-bg, rgba(0,0,0,0.1));
  color: var(--primary-color, #409eff);
}

/* 下拉菜单 */
.dropdown-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999;
}

.dropdown-menu {
  position: fixed;
  z-index: 1000;
  min-width: 180px;
  max-width: 280px;
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.dropdown-header {
  padding: 8px 12px;
  font-size: 11px;
  color: var(--text-secondary, #999);
  background: var(--bg-secondary, #f5f5f5);
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.dropdown-content {
  max-height: 240px;
  overflow-y: auto;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.dropdown-item:hover {
  background: var(--hover-bg, rgba(0,0,0,0.05));
}

.dropdown-item.is-active {
  background: var(--primary-bg, rgba(64, 158, 255, 0.1));
  color: var(--primary-color, #409eff);
}

.dropdown-item i {
  color: var(--warning-color, #e6a23c);
  font-size: 14px;
}

.dropdown-item span {
  flex: 1;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-empty {
  padding: 16px;
  text-align: center;
  color: var(--text-secondary, #999);
  font-size: 12px;
}
</style>
