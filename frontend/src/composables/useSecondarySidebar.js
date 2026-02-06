/**
 * SecondarySidebar 逻辑层
 * 处理二级侧边栏的无限滚动功能
 */

import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'

export function useSecondarySidebar(props, emit) {
  // ==================== Refs ====================
  const contentRef = ref(null)
  const loadTrigger = ref(null)
  let observer = null

  // ==================== 方法 ====================
  function setupObserver() {
    if (observer) observer.disconnect()

    observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && props.hasMore && !props.isLoadingMore) {
        emit('load-more')
      }
    }, {
      root: contentRef.value,
      threshold: 0.1
    })

    if (loadTrigger.value) {
      observer.observe(loadTrigger.value)
    }
  }

  // ==================== 监听器 ====================
  watch(() => props.hasMore, (newVal) => {
    if (newVal) {
      nextTick(setupObserver)
    }
  })

  // ==================== 生命周期 ====================
  onMounted(() => {
    setupObserver()
  })

  onUnmounted(() => {
    if (observer) observer.disconnect()
  })

  // ==================== 返回 ====================
  return {
    contentRef,
    loadTrigger
  }
}
