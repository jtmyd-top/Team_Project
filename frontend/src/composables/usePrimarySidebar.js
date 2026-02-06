/**
 * PrimarySidebar 逻辑层
 * 处理主导航栏的点击和模块切换
 */

import { useSidebarStore } from '@/stores/sidebar'

export function usePrimarySidebar(emit) {
  const sidebarStore = useSidebarStore()

  const navItems = [
    { id: 'all-notes', label: '全部笔记', icon: 'fas fa-house' },
    { id: 'my-space', label: '我的空间', icon: 'fas fa-folder' },
    { id: 'favorites', label: '收藏夹', icon: 'fas fa-star' },
    { id: 'vault', label: '保密柜', icon: 'fas fa-lock' },
    { id: 'trash', label: '回收站', icon: 'fas fa-trash' },
  ]

  const handleNavClick = (item) => {
    sidebarStore.setActiveModule(item.id)

    // 如果侧边栏是收起的，则展开
    if (sidebarStore.isCollapsed) {
      sidebarStore.setCollapsed(false)
    }
  }

  const handleUserProfile = () => {
    emit('user-profile')
  }

  return {
    sidebarStore,
    navItems,
    handleNavClick,
    handleUserProfile
  }
}
