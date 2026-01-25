<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="visible"
        class="context-menu-overlay"
        @click="handleOverlayClick"
        @contextmenu.prevent
      >
        <div
          ref="menuRef"
          class="context-menu"
          :style="menuStyle"
          @click.stop
        >
          <!-- 新建笔记 -->
          <div class="menu-item" @click="handleAction('create')">
            <i class="fas fa-plus"></i>
            <span>新建笔记</span>
          </div>

          <div class="menu-divider"></div>

          <!-- 重命名 -->
          <div class="menu-item" @click="handleAction('rename')">
            <i class="fas fa-edit"></i>
            <span>重命名</span>
            <span class="shortcut">F2</span>
          </div>

          <!-- 收藏/取消收藏 -->
          <div class="menu-item" @click="handleAction('favorite')">
            <i class="fas" :class="note?.is_favorited ? 'fa-star' : 'fa-star'"></i>
            <span>{{ note?.is_favorited ? '取消收藏' : '添加收藏' }}</span>
          </div>

          <div class="menu-divider"></div>

          <!-- 移动到 -->
          <div class="menu-item has-submenu" @click="handleAction('move')">
            <i class="fas fa-folder-open"></i>
            <span>移动到...</span>
            <i class="fas fa-chevron-right submenu-arrow"></i>
          </div>

          <!-- 复制到 -->
          <div class="menu-item has-submenu" @click="handleAction('copy')">
            <i class="fas fa-copy"></i>
            <span>复制到...</span>
            <i class="fas fa-chevron-right submenu-arrow"></i>
          </div>

          <div class="menu-divider"></div>

          <!-- 复制链接 -->
          <div class="menu-item" @click="handleAction('copyLink')">
            <i class="fas fa-link"></i>
            <span>复制链接</span>
          </div>

          <!-- 在新窗口打开 -->
          <div class="menu-item" @click="handleAction('openNew')">
            <i class="fas fa-external-link-alt"></i>
            <span>在新标签页打开</span>
          </div>

          <div class="menu-divider"></div>

          <!-- 移入回收站 -->
          <div class="menu-item danger" @click="handleAction('trash')">
            <i class="fas fa-trash"></i>
            <span>移入回收站</span>
            <span class="shortcut">Del</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  x: {
    type: Number,
    default: 0
  },
  y: {
    type: Number,
    default: 0
  },
  note: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'action'])

const menuRef = ref(null)
const adjustedX = ref(0)
const adjustedY = ref(0)

// 计算菜单位置，确保不超出屏幕
const menuStyle = computed(() => {
  return {
    left: `${adjustedX.value}px`,
    top: `${adjustedY.value}px`
  }
})

// 调整菜单位置
async function adjustPosition() {
  await nextTick()

  if (!menuRef.value) return

  const menuRect = menuRef.value.getBoundingClientRect()
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight

  let x = props.x
  let y = props.y

  // 如果菜单超出右边界，向左偏移
  if (x + menuRect.width > viewportWidth - 10) {
    x = viewportWidth - menuRect.width - 10
  }

  // 如果菜单超出下边界，向上偏移
  if (y + menuRect.height > viewportHeight - 10) {
    y = viewportHeight - menuRect.height - 10
  }

  // 确保不小于0
  adjustedX.value = Math.max(10, x)
  adjustedY.value = Math.max(10, y)
}

// 处理遮罩点击
function handleOverlayClick() {
  emit('close')
}

// 处理菜单项点击
function handleAction(action) {
  emit('action', action, props.note)
  emit('close')
}

// 处理键盘事件
function handleKeydown(event) {
  if (!props.visible) return

  if (event.key === 'Escape') {
    emit('close')
  }
}

// 监听 visible 变化，调整位置
watch(() => props.visible, (newVal) => {
  if (newVal) {
    adjustPosition()
  }
})

// 监听坐标变化
watch([() => props.x, () => props.y], () => {
  if (props.visible) {
    adjustPosition()
  }
})

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.context-menu-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
}

.context-menu {
  position: fixed;
  min-width: 200px;
  background: var(--bg-primary, #fff);
  border-radius: 8px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1);
  border: 1px solid var(--border-color, #e0e0e0);
  padding: 6px 0;
  z-index: 2001;
  overflow: hidden;
}

.menu-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.15s;
  gap: 12px;
  font-size: 13px;
  color: var(--text-primary, #333);
}

.menu-item:hover {
  background: var(--hover-bg, rgba(0, 0, 0, 0.05));
}

.menu-item i:first-child {
  width: 16px;
  text-align: center;
  color: var(--text-secondary, #666);
  font-size: 13px;
}

.menu-item span:first-of-type {
  flex: 1;
}

.menu-item .shortcut {
  font-size: 11px;
  color: var(--text-tertiary, #999);
  background: var(--bg-tertiary, #f0f0f0);
  padding: 2px 6px;
  border-radius: 4px;
}

.menu-item.has-submenu .submenu-arrow {
  font-size: 10px;
  color: var(--text-tertiary, #999);
}

.menu-item.danger {
  color: var(--error-color, #f56c6c);
}

.menu-item.danger i:first-child {
  color: var(--error-color, #f56c6c);
}

.menu-item.danger:hover {
  background: rgba(245, 108, 108, 0.1);
}

.menu-divider {
  height: 1px;
  background: var(--border-color, #e0e0e0);
  margin: 6px 0;
}

/* 过渡动画 */
.fade-enter-active {
  transition: opacity 0.15s ease;
}

.fade-leave-active {
  transition: opacity 0.1s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-enter-from .context-menu {
  transform: scale(0.95);
}
</style>
