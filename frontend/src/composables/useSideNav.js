/**
 * SideNav 组件的业务逻辑
 * @param {Function} emit - 组件 emit 函数
 * @returns {Object} 组件所需的状态和方法
 */
export function useSideNav(emit) {
  // 导航项配置
  const navItems = [
    { id: 'all', label: '全部笔记', icon: 'fas fa-home' },
    { id: 'spaces', label: '我的空间', icon: 'fas fa-folder' },
    { id: 'favorites', label: '收藏夹', icon: 'fas fa-star' },
    { id: 'private', label: '保密柜', icon: 'fas fa-lock' },
    { id: 'trash', label: '回收站', icon: 'fas fa-trash-alt' }
  ]

  /**
   * 处理导航点击
   * @param {string} itemId - 导航项 ID
   */
  const handleClick = (itemId) => {
    emit('nav-change', itemId)
  }

  return {
    navItems,
    handleClick
  }
}
