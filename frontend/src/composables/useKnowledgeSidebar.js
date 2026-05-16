/**
 * KnowledgeSidebar 逻辑层
 * 处理知识库侧边栏的无限滚动、笔记列表显示等功能
 */

import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { formatDateOnly } from '@utils/datetime'

export function useKnowledgeSidebar(props, emit) {
  // ==================== Refs ====================
  const listRef = ref(null)
  const loadTrigger = ref(null)
  const noteItemRefs = ref(new Map())

  // 显示的笔记数量（用于无限滚动）
  const displayedCount = ref(props.pageSize)

  // Intersection Observer 实例
  let intersectionObserver = null

  // ==================== 计算属性 ====================
  const displayNotes = computed(() => {
    return props.notes.slice(0, displayedCount.value)
  })

  // ==================== 方法 ====================
  // 设置笔记元素引用
  function setNoteRef(el, noteId) {
    if (el) {
      noteItemRefs.value.set(noteId, el)
    }
  }

  // 格式化日期
  function formatDate(dateStr) {
    return formatDateOnly(dateStr)
  }

  // 设置 Intersection Observer 用于无限滚动
  function setupIntersectionObserver() {
    if (typeof IntersectionObserver === 'undefined') return

    intersectionObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && props.hasMore && !props.isLoadingMore) {
          emit('load-more')
        }
      })
    }, {
      root: listRef.value,
      rootMargin: '200px',
      threshold: 0.1
    })

    nextTick(() => {
      if (loadTrigger.value) {
        intersectionObserver.observe(loadTrigger.value)
      }
    })
  }

  // 加载更多
  function loadMore() {
    displayedCount.value += props.pageSize
  }

  // 获取笔记元素
  function getNoteElement(noteId) {
    return noteItemRefs.value.get(noteId)
  }

  // ==================== 监听器 ====================
  // 监听显示数量变化，触发加载更多
  watch(displayedCount, (newVal) => {
    if (newVal < props.notes.length) {
      nextTick(() => {
        if (loadTrigger.value && intersectionObserver) {
          intersectionObserver.observe(loadTrigger.value)
        }
      })
    }
  })

  // 监听笔记列表变化，重置显示数量
  watch(() => props.notes, () => {
    displayedCount.value = props.pageSize
  })

  // 监听搜索关键词变化，重置显示数量
  watch(() => props.searchQuery, () => {
    displayedCount.value = props.pageSize
  })

  // ==================== 生命周期 ====================
  onMounted(() => {
    setupIntersectionObserver()
  })

  onUnmounted(() => {
    if (intersectionObserver) {
      intersectionObserver.disconnect()
    }
  })

  // ==================== 返回 ====================
  return {
    // Refs
    listRef,
    loadTrigger,
    noteItemRefs,
    displayedCount,

    // 计算属性
    displayNotes,

    // 方法
    setNoteRef,
    formatDate,
    loadMore,
    getNoteElement
  }
}
