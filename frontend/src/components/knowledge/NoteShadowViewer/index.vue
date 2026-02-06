<template>
  <div class="note-viewer-container" :class="{ 'has-toc': showToc }">
    <!-- 阅读进度条 -->
    <div v-if="showToc" class="reading-progress-bar" :style="{ width: scrollProgress + '%' }"></div>

    <!-- 主内容区 -->
    <div ref="hostRef" class="shadow-host"></div>

    <!-- 目录侧边栏（阈值触发显示） -->
    <Transition name="slide-in">
      <aside v-if="showToc" class="note-toc">
        <div class="toc-sticky">
          <h3>目录</h3>
          <ul class="toc-list">
            <li
              v-for="item in tocItems"
              :key="item.id"
              :class="['toc-item', `toc-level-${item.level}`, { 'active': activeTocId === item.id }]"
              @click="scrollToHeading(item.id)"
            >
              {{ item.text }}
            </li>
          </ul>
        </div>
      </aside>
    </Transition>
  </div>
</template>

<script setup>
import { useNoteShadowViewer } from '@composables/useNoteShadowViewer'

const props = defineProps({
  content: {
    type: String,
    default: ''
  },
  toc: {
    type: Array,
    default: () => []
  },
  isDark: {
    type: Boolean,
    default: false
  },
  isSecret: {
    type: Boolean,
    default: false
  },
  isTrashed: {
    type: Boolean,
    default: false
  },
  noteId: {
    type: Number,
    default: null
  }
})

const {
  hostRef,
  showToc,
  tocItems,
  activeTocId,
  scrollProgress,
  scrollToHeading
} = useNoteShadowViewer(props)
</script>

<style scoped>
/* 容器布局 */
.note-viewer-container {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  display: flex;
  justify-content: center;
  position: relative;
  overflow-x: hidden;
}

.shadow-host {
  width: 100%;
  max-width: 800px;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
  transition: max-width 0.3s ease;
}

.note-viewer-container.has-toc {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 30px;
  max-width: 100%;
  padding: 0;
}

.note-viewer-container.has-toc .shadow-host {
  max-width: 100%;
  min-width: 0;
}

.reading-progress-bar {
  position: fixed;
  top: 0;
  left: 0;
  height: 3px;
  background: linear-gradient(90deg, #409eff, #67c23a);
  z-index: 1000;
  transition: width 0.1s ease-out;
}

.note-toc {
  position: relative;
}

.note-toc h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  color: v-bind(isDark ? '#e0e0e0' : '#333');
}

.toc-sticky {
  position: sticky;
  top: 20px;
  max-height: calc(100vh - 40px);
  overflow-y: auto;
}

.toc-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.toc-item {
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s ease;
  font-size: 14px;
  color: v-bind(isDark ? '#999' : '#666');
  line-height: 1.5;
}

.toc-item:hover {
  background-color: v-bind(isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)');
  color: v-bind(isDark ? '#409eff' : '#409eff');
}

.toc-item.active {
  background-color: v-bind(isDark ? 'rgba(64, 158, 255, 0.1)' : 'rgba(64, 158, 255, 0.1)');
  color: #409eff;
  font-weight: 500;
}

.toc-level-1 {
  font-weight: 600;
  margin-top: 4px;
}

.toc-level-2 {
  margin-left: 16px;
  font-size: 0.9em;
}

.toc-level-3 {
  margin-left: 32px;
  font-size: 0.85em;
}

.slide-in-enter-active,
.slide-in-leave-active {
  transition: all 0.3s ease;
}

.slide-in-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.slide-in-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

@media (max-width: 1100px) {
  .note-viewer-container.has-toc {
    grid-template-columns: 1fr;
  }

  .note-toc {
    display: none;
  }
}

@media (max-width: 768px) {
  .shadow-host {
    max-width: 100%;
  }

  .note-viewer-container.has-toc {
    gap: 0;
    padding: 0;
  }
}
</style>
