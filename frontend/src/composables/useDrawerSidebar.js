import { ref, reactive, computed } from 'vue'

/**
 * DrawerSidebar 组件的业务逻辑
 * @param {Object} props - 组件 props
 * @param {Function} emit - 组件 emit 函数
 * @returns {Object} 组件所需的状态和方法
 */
export function useDrawerSidebar(props, emit) {
  // 当前视图 (全部笔记 / 文件夹)
  const currentView = ref(props.defaultView || 'notes')

  // 收件箱数量
  const inboxCount = computed(() => props.inboxItems?.length || 0)

  // 展开/收起的区域状态
  const expandedSections = reactive({
    inbox: true,
    favorites: true,
    recent: true,
    allNotes: false,
    private: true,
    shared: true
  })

  // 切换视图
  const switchView = (view) => {
    currentView.value = view
    emit('view-change', view)
    // 持久化到 localStorage
    localStorage.setItem('sidebarView', view)
  }

  // 初始化从 localStorage 读取视图设置
  const initViewFromStorage = () => {
    const savedView = localStorage.getItem('sidebarView')
    if (savedView && ['notes', 'folders'].includes(savedView)) {
      currentView.value = savedView
    }
  }

  // 切换区域展开/收起
  const toggleSection = (section) => {
    expandedSections[section] = !expandedSections[section]
  }

  // 格式化日期
  const formatDate = (dateStr) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now - date

    // 今天内
    if (diff < 24 * 60 * 60 * 1000 && date.getDate() === now.getDate()) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }
    // 昨天
    const yesterday = new Date(now)
    yesterday.setDate(yesterday.getDate() - 1)
    if (date.getDate() === yesterday.getDate() && date.getMonth() === yesterday.getMonth()) {
      return '昨天'
    }
    // 一周内
    if (diff < 7 * 24 * 60 * 60 * 1000) {
      const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
      return days[date.getDay()]
    }
    // 更久
    return `${date.getMonth() + 1}/${date.getDate()}`
  }

  // 初始化
  initViewFromStorage()

  return {
    // 状态
    currentView,
    expandedSections,
    // 计算属性
    inboxCount,
    // 方法
    switchView,
    toggleSection,
    formatDate
  }
}
