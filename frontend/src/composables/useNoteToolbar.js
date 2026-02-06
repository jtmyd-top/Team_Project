/**
 * NoteToolbar 逻辑层
 * 处理笔记工具栏的格式化和工具函数
 */

export function useNoteToolbar(props, emit) {
  // ==================== 工具函数 ====================
  const formatDate = (dateStr) => {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleString()
  }

  const getAuthorName = (author) => author?.username || author || 'Unknown'

  // ==================== 事件处理 ====================
  const handleOpenSidebar = () => {
    emit('open-sidebar')
  }

  const handleToggleTheme = () => {
    emit('toggle-theme')
  }

  const handleTogglePublic = () => {
    emit('toggle-public')
  }

  const handleCopyLink = () => {
    emit('copy-link')
  }

  const handleStartEdit = () => {
    emit('start-edit')
  }

  const handleCancelEdit = () => {
    emit('cancel-edit')
  }

  const handleSave = () => {
    emit('save')
  }

  const handleDelete = () => {
    emit('delete')
  }

  // ==================== 返回 ====================
  return {
    formatDate,
    getAuthorName,
    handleOpenSidebar,
    handleToggleTheme,
    handleTogglePublic,
    handleCopyLink,
    handleStartEdit,
    handleCancelEdit,
    handleSave,
    handleDelete
  }
}
