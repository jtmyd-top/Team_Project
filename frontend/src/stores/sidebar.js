/**
 * 侧边栏状态管理 Store
 * 管理二级侧边栏的显示状态、当前模块、文件夹树等
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { folderApi } from '@/api/folder'

// ==================== URL 状态管理工具 ====================

// localStorage key
const SIDEBAR_COLLAPSED_KEY = 'sidebar_collapsed'

/**
 * 从 localStorage 读取侧边栏收起状态
 */
function getSidebarCollapsedState() {
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true'
  } catch {
    return false
  }
}

/**
 * 保存侧边栏收起状态到 localStorage
 */
function saveSidebarCollapsedState(collapsed) {
  try {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? 'true' : 'false')
  } catch {
    // ignore
  }
}

/**
 * 从 URL 读取状态
 */
function getStateFromUrl() {
  const params = new URLSearchParams(window.location.search)
  return {
    module: params.get('module') || 'all-notes',
    folder: params.get('folder') ? parseInt(params.get('folder')) : null,
    note: params.get('note') ? parseInt(params.get('note')) : null,
    view: params.get('view') || null  // 'folders' | 'notes' | 'inbox'
  }
}

/**
 * 将状态保存到 URL
 */
function saveStateToUrl(state) {
  const params = new URLSearchParams()

  if (state.module && state.module !== 'all-notes') {
    params.set('module', state.module)
  }
  if (state.folder) {
    params.set('folder', state.folder)
  }
  if (state.note) {
    params.set('note', state.note)
  }
  if (state.view && state.view !== 'folders') {
    params.set('view', state.view)
  }

  const queryString = params.toString()
  const newUrl = queryString
    ? `${window.location.pathname}?${queryString}`
    : window.location.pathname

  // 使用 replaceState 避免产生过多历史记录
  window.history.replaceState({}, '', newUrl)
}

export const useSidebarStore = defineStore('sidebar', () => {
  // ==================== 状态 ====================

  // 当前激活的模块: 'all-notes' | 'my-space' | 'favorites' | 'trash' | 'vault' | 'settings'
  const activeModule = ref('all-notes')

  // 二级侧边栏是否收起（从 localStorage 恢复）
  const isCollapsed = ref(getSidebarCollapsedState())

  // 二级侧边栏当前视图: 'folders' | 'notes'
  const secondaryView = ref('folders')

  // 当前选中的文件夹 ID
  const currentFolderId = ref(null)

  // 当前选中的笔记 ID（用于持久化）
  const currentNoteId = ref(null)

  // 文件夹树数据
  const folders = ref([])

  // 收件箱笔记数量
  const inboxCount = ref(0)

  // 当前文件夹下的笔记列表
  const currentNotes = ref([])

  // 当前文件夹下的子文件夹列表
  const currentSubfolders = ref([])

  // 当前文件夹信息
  const currentFolder = ref(null)

  // 面包屑路径
  const breadcrumb = ref([])

  // 加载状态
  const isLoading = ref(false)

  // 错误信息
  const error = ref(null)

  // 是否已初始化（从 URL 恢复状态）
  const isInitialized = ref(false)

  // ==================== 保密柜状态 ====================
  const vaultStatus = ref({
    twoFaEnabled: false,
    twoFaMethod: null,
    isVerified: false,
    remainingSeconds: 0,
    secretNotesCount: 0
  })
  const vaultVerifyDialogVisible = ref(false)
  const vaultSetup2faDialogVisible = ref(false)

  // ==================== 计算属性 ====================
  
  // 是否显示二级侧边栏
  const showSecondary = computed(() => {
    return ['all-notes', 'my-space', 'favorites', 'trash', 'vault'].includes(activeModule.value) && !isCollapsed.value
  })

  // 当前模块标题
  const moduleTitle = computed(() => {
    const titles = {
      'all-notes': '全部笔记',
      'my-space': '我的空间',
      'favorites': '收藏夹',
      'trash': '回收站',
      'vault': '保密柜',
      'settings': '设置'
    }
    return titles[activeModule.value] || ''
  })

  // ==================== 动作 ====================
  
  /**
   * 切换模块
   */
  function setActiveModule(module) {
    const previousModule = activeModule.value
    activeModule.value = module

    // 【安全】从保密柜切换到其他模块时，清空当前笔记 ID
    // 这样预览区会被清空，防止解密内容泄露
    if (previousModule === 'vault' && module !== 'vault') {
      currentNoteId.value = null
      console.log('[Sidebar] Switched from vault, clearing currentNoteId for security')
    }

    // 根据模块重置视图
    if (module === 'my-space') {
      secondaryView.value = 'folders'
      currentFolderId.value = null
      currentFolder.value = null
      breadcrumb.value = []
    } else {
      secondaryView.value = 'notes'
      currentFolderId.value = null
    }

    // 更新 URL
    updateUrl()

    // 加载对应模块的数据
    loadModuleData()
  }

  /**
   * 设置当前笔记 ID（用于 URL 持久化）
   */
  function setCurrentNoteId(noteId) {
    currentNoteId.value = noteId
    updateUrl()
  }

  /**
   * 更新 URL（内部方法）
   */
  function updateUrl() {
    if (!isInitialized.value) return

    saveStateToUrl({
      module: activeModule.value,
      folder: currentFolderId.value,
      note: currentNoteId.value,
      view: activeModule.value === 'my-space' && secondaryView.value === 'notes'
        ? (currentFolderId.value ? 'notes' : 'inbox')
        : null
    })
  }

  /**
   * 从 URL 恢复状态（初始化时调用）
   */
  async function initFromUrl() {
    if (isInitialized.value) return { noteId: currentNoteId.value }

    const urlState = getStateFromUrl()

    // 设置模块
    activeModule.value = urlState.module

    // 记录笔记 ID
    currentNoteId.value = urlState.note

    // 根据模块和 URL 参数恢复状态
    if (urlState.module === 'my-space') {
      if (urlState.view === 'inbox' || (urlState.view === 'notes' && !urlState.folder)) {
        // 进入收件箱 - 需要加载收件箱笔记
        secondaryView.value = 'notes'
        currentFolder.value = { id: null, name: '未分类笔记' }
        currentFolderId.value = null
        // 标记需要加载收件箱数据
        isInitialized.value = true
        await loadInboxNotes()
        return { noteId: urlState.note }
      } else if (urlState.folder) {
        // 进入指定文件夹 - 需要加载文件夹笔记
        currentFolderId.value = urlState.folder
        secondaryView.value = 'notes'
        isInitialized.value = true
        await loadFolderNotes(urlState.folder)
        return { noteId: urlState.note }
      } else {
        // 显示文件夹列表
        secondaryView.value = 'folders'
      }
    } else {
      secondaryView.value = 'notes'
    }

    isInitialized.value = true

    return { noteId: urlState.note }
  }

  /**
   * 加载收件箱笔记（内部方法）
   */
  async function loadInboxNotes() {
    isLoading.value = true
    error.value = null
    try {
      const data = await folderApi.fetchNotes(null)
      currentNotes.value = data.notes || []
    } catch (e) {
      error.value = e.message
      console.error('加载收件箱失败:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 加载文件夹笔记（内部方法）
   */
  async function loadFolderNotes(folderId) {
    isLoading.value = true
    error.value = null
    try {
      const data = await folderApi.fetchNotes(folderId)
      currentNotes.value = data.notes || []
      currentSubfolders.value = data.subfolders || []
      currentFolder.value = data.folder || null

      // 加载面包屑
      if (folderId) {
        const breadcrumbData = await folderApi.getBreadcrumb(folderId)
        breadcrumb.value = breadcrumbData.breadcrumb || []
      }
    } catch (e) {
      error.value = e.message
      console.error('加载文件夹笔记失败:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 切换侧边栏收起状态
   */
  function toggleCollapse() {
    isCollapsed.value = !isCollapsed.value
    saveSidebarCollapsedState(isCollapsed.value)
  }

  /**
   * 设置侧边栏收起状态
   */
  function setCollapsed(collapsed) {
    isCollapsed.value = collapsed
    saveSidebarCollapsedState(collapsed)
  }

  /**
   * 加载当前模块数据
   */
  async function loadModuleData() {
    isLoading.value = true
    error.value = null
    
    try {
      switch (activeModule.value) {
        case 'all-notes':
          await loadAllNotes()
          break
        case 'my-space':
          await loadFolders()
          break
        case 'favorites':
          await loadFavoritedNotes()
          break
        case 'trash':
          await loadTrashedNotes()
          break
        case 'vault':
          await enterVault()
          break
      }
    } catch (e) {
      error.value = e.message
      console.error('加载模块数据失败:', e)
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * 加载所有笔记（扁平列表）
   */
  async function loadAllNotes() {
    const response = await fetch('/api/notes/flat/')
    const data = await response.json()
    currentNotes.value = data.notes || []
  }
  
  /**
   * 加载文件夹树
   */
  async function loadFolders() {
    const data = await folderApi.fetchAll()
    folders.value = data.folders || []
    inboxCount.value = data.inbox_count || 0
  }
  
  /**
   * 加载收藏的笔记
   */
  async function loadFavoritedNotes() {
    const response = await fetch('/api/notes/favorited/')
    const data = await response.json()
    currentNotes.value = data.notes || []
  }

  /**
   * 加载回收站笔记和文件夹
   */
  async function loadTrashedNotes() {
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch('/api/folders/trashed-items/')
      const data = await response.json()

      // 存储混合列表（文件夹 + 笔记）
      currentNotes.value = data.items || []

      // 重置当前文件夹（在回收站根目录）
      currentFolder.value = null
      currentSubfolders.value = []

      secondaryView.value = 'trash'
    } catch (e) {
      error.value = e.message
      console.error('加载回收站失败:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 【新增】进入回收站中的文件夹
   */
  async function enterTrashedFolder(folderId) {
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch(`/api/folders/trashed/${folderId}/contents/`)
      const data = await response.json()

      currentFolder.value = {
        id: data.folder.id,
        name: data.folder.name,
        trashed_at: data.folder.trashed_at
      }

      // 合并子文件夹和笔记显示
      currentNotes.value = [
        ...(data.subfolders || []).map(item => ({ ...item, type: 'folder' })),
        ...(data.notes || []).map(item => ({ ...item, type: 'note' }))
      ]

      currentSubfolders.value = data.subfolders || []
    } catch (e) {
      error.value = e.message
      console.error('加载回收站文件夹内容失败:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 【新增】从回收站文件夹返回根目录
   */
  async function backToTrashRoot() {
    await loadTrashedNotes()
  }

  /**
   * 【新增】恢复文件夹
   */
  async function restoreFolder(folderId) {
    try {
      const response = await fetch(`/api/folders/${folderId}/restore/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        }
      })

      if (!response.ok) {
        throw new Error('恢复失败')
      }

      const data = await response.json()

      // 从当前列表移除
      currentNotes.value = currentNotes.value.filter(item => item.id !== folderId)

      // 触发事件
      window.dispatchEvent(new CustomEvent('folder-restored-from-trash', {
        detail: { folderId }
      }))

      return data
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  /**
   * 【新增】永久删除文件夹
   */
  async function permanentDeleteFolder(folderId) {
    try {
      const response = await fetch(`/api/folders/${folderId}/permanent-delete/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        }
      })

      if (!response.ok) {
        throw new Error('删除失败')
      }

      const data = await response.json()

      // 从当前列表移除
      currentNotes.value = currentNotes.value.filter(item => item.id !== folderId)

      return data
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  /**
   * 加载保密柜状态
   */
  async function loadVaultStatus() {
    try {
      const response = await fetch('/api/vault/status/')
      const data = await response.json()
      vaultStatus.value = {
        twoFaEnabled: data.two_fa_enabled,
        twoFaMethod: data.two_fa_method,
        isVerified: data.is_verified,
        remainingSeconds: data.remaining_seconds,
        secretNotesCount: data.secret_notes_count
      }
      return data
    } catch (e) {
      console.error('加载保密柜状态失败:', e)
      throw e
    }
  }

  /**
   * 加载保密柜笔记
   */
  async function loadVaultNotes() {
    const response = await fetch('/api/vault/notes/')
    const data = await response.json()

    // 检查是否需要2FA验证
    if (data.status === 'require_vault_2fa') {
      vaultVerifyDialogVisible.value = true
      return { requireVerify: true, method: data.method }
    }

    currentNotes.value = data.notes || []
    vaultStatus.value.remainingSeconds = data.remaining_seconds || 0
    return { requireVerify: false }
  }

  /**
   * 进入保密柜
   */
  async function enterVault() {
    isLoading.value = true
    error.value = null

    // 进入保密柜时先清空笔记列表，防止显示之前的数据
    currentNotes.value = []
    currentSubfolders.value = []
    secondaryView.value = 'notes'

    try {
      // 先检查保密柜状态
      await loadVaultStatus()

      // 如果未启用2FA，提示用户设置
      if (!vaultStatus.value.twoFaEnabled) {
        vaultSetup2faDialogVisible.value = true
        isLoading.value = false
        return
      }

      // 如果未验证，显示验证对话框
      if (!vaultStatus.value.isVerified) {
        vaultVerifyDialogVisible.value = true
        isLoading.value = false
        return
      }

      // 已验证，加载保密柜笔记
      await loadVaultNotes()
    } catch (e) {
      error.value = e.message
      console.error('进入保密柜失败:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 保密柜验证成功后的回调
   */
  async function onVaultVerified() {
    vaultVerifyDialogVisible.value = false
    vaultStatus.value.isVerified = true
    secondaryView.value = 'notes'
    await loadVaultNotes()
  }

  /**
   * 锁定保密柜
   */
  async function lockVault() {
    try {
      await fetch('/api/vault/lock/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        }
      })
      vaultStatus.value.isVerified = false
      vaultStatus.value.remainingSeconds = 0
      currentNotes.value = []

      // 【关键修复】清除 vaultStore 中的 DEK，确保锁定后无法解密
      const { useVaultStore } = await import('./vault.js')
      const vaultStore = useVaultStore()
      vaultStore.clearDEK()
      console.log('[Sidebar] Vault locked, DEK cleared')
    } catch (e) {
      console.error('锁定保密柜失败:', e)
      throw e
    }
  }

  /**
   * 进入文件夹（显示该文件夹下的笔记）
   */
  async function enterFolder(folderId) {
    isLoading.value = true
    error.value = null

    try {
      currentFolderId.value = folderId
      secondaryView.value = 'notes'

      // 更新 URL
      updateUrl()

      // 加载文件夹下的笔记和子文件夹
      const data = await folderApi.fetchNotes(folderId)
      currentNotes.value = data.notes || []
      currentSubfolders.value = data.subfolders || []
      currentFolder.value = data.folder || null

      // 加载面包屑
      if (folderId) {
        const breadcrumbData = await folderApi.getBreadcrumb(folderId)
        breadcrumb.value = breadcrumbData.breadcrumb || []
      }
    } catch (e) {
      error.value = e.message
      console.error('进入文件夹失败:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 进入收件箱
   */
  async function enterInbox() {
    isLoading.value = true
    error.value = null

    try {
      currentFolderId.value = null
      secondaryView.value = 'notes'
      currentFolder.value = { id: null, name: '未分类笔记' }
      breadcrumb.value = []

      // 更新 URL
      updateUrl()

      // 加载收件箱笔记
      const data = await folderApi.fetchNotes(null)
      currentNotes.value = data.notes || []
    } catch (e) {
      error.value = e.message
      console.error('加载收件箱失败:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 返回文件夹列表视图
   */
  async function backToFolders() {
    secondaryView.value = 'folders'
    currentFolderId.value = null
    currentFolder.value = null
    breadcrumb.value = []
    currentNotes.value = []
    currentSubfolders.value = []

    // 更新 URL
    updateUrl()

    // 重新加载文件夹列表
    await loadFolders()
  }
  
  /**
   * 创建文件夹
   */
  async function createFolder(name, parentId = null) {
    try {
      const newFolder = await folderApi.create({ name, parent_id: parentId })

      // 重新加载文件夹树
      await loadFolders()

      // 【新增】如果当前在某个文件夹内，且新创建的子文件夹属于当前文件夹，刷新子文件夹列表
      if (secondaryView.value === 'notes' && currentFolderId.value === parentId) {
        const data = await folderApi.fetchNotes(currentFolderId.value)
        currentSubfolders.value = data.subfolders || []
      }
      // 如果在文件夹列表视图，不需要额外操作，因为 loadFolders 已经更新了 folders

      return newFolder
    } catch (e) {
      error.value = e.message
      throw e
    }
  }
  
  /**
   * 重命名文件夹
   */
  async function renameFolder(folderId, newName) {
    try {
      await folderApi.update(folderId, { name: newName })

      // 重新加载文件夹树
      await loadFolders()

      // 【新增】如果当前在某个文件夹内，刷新子文件夹列表
      if (secondaryView.value === 'notes' && currentFolderId.value) {
        const data = await folderApi.fetchNotes(currentFolderId.value)
        currentSubfolders.value = data.subfolders || []
        // 同时更新当前文件夹信息（可能重命名的是当前文件夹）
        if (data.folder) {
          currentFolder.value = data.folder
        }
      }
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  /**
   * 重命名笔记
   */
  async function renameNote(noteId, newTitle) {
    try {
      const response = await fetch(`/api/notes/${noteId}/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        },
        body: JSON.stringify({ title: newTitle })
      })

      if (!response.ok) {
        throw new Error('重命名失败')
      }

      // 更新本地状态
      const note = currentNotes.value.find(n => n.id === noteId)
      if (note) {
        note.title = newTitle
      }

      // 【P2】触发事件：笔记已重命名
      window.dispatchEvent(new CustomEvent('note-renamed', {
        detail: { noteId, newTitle }
      }))
    } catch (e) {
      error.value = e.message
      throw e
    }
  }
  
  /**
   * 删除文件夹
   */
  async function deleteFolder(folderId) {
    try {
      await folderApi.delete(folderId)

      // 如果当前在这个文件夹中，返回文件夹列表
      if (currentFolderId.value === folderId) {
        backToFolders()
      }

      // 重新加载文件夹树
      await loadFolders()

      // 【新增】如果当前在某个文件夹内，刷新子文件夹列表（可能删除的是子文件夹）
      if (secondaryView.value === 'notes' && currentFolderId.value) {
        const data = await folderApi.fetchNotes(currentFolderId.value)
        currentSubfolders.value = data.subfolders || []
      }
    } catch (e) {
      error.value = e.message
      throw e
    }
  }
  
  /**
   * 移动笔记到文件夹
   */
  async function moveNoteToFolder(noteId, folderId) {
    try {
      // 获取移动前的文件夹信息
      const note = currentNotes.value.find(n => n.id === noteId)
      const oldFolderId = note?.folder?.id || null

      await folderApi.moveNote(noteId, folderId)

      // 【P1】触发事件：笔记文件夹已变更
      window.dispatchEvent(new CustomEvent('note-folder-changed', {
        detail: { noteId, oldFolderId, newFolderId: folderId }
      }))

      // 刷新当前视图
      if (activeModule.value === 'my-space') {
        // 如果在 my-space 模块，需要根据当前视图决定刷新内容
        if (secondaryView.value === 'folders') {
          // 文件夹列表视图：只刷新文件夹树
          await loadFolders()
        } else if (secondaryView.value === 'notes') {
          // 笔记列表视图：刷新当前文件夹的笔记和子文件夹
          const data = await folderApi.fetchNotes(currentFolderId.value)
          currentNotes.value = data.notes || []
          currentSubfolders.value = data.subfolders || []
        }
      } else {
        // 其他模块：统一调用 loadModuleData
        await loadModuleData()
      }
    } catch (e) {
      error.value = e.message
      throw e
    }
  }
  
  /**
   * 收藏/取消收藏笔记
   */
  async function toggleNoteFavorite(noteId) {
    try {
      const response = await fetch(`/api/notes/${noteId}/favorite/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        }
      })
      const data = await response.json()
      
      // 更新本地状态
      const note = currentNotes.value.find(n => n.id === noteId)
      if (note) {
        note.is_favorited = data.is_favorited
      }
      
      return data.is_favorited
    } catch (e) {
      error.value = e.message
      throw e
    }
  }
  
  /**
   * 移入回收站
   */
  async function trashNote(noteId) {
    try {
      await fetch(`/api/notes/${noteId}/trash/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        }
      })

      // 【P1】触发事件：笔记已移入回收站
      window.dispatchEvent(new CustomEvent('note-moved-to-trash', {
        detail: { noteId }
      }))

      // 从当前列表移除
      currentNotes.value = currentNotes.value.filter(n => n.id !== noteId)
    } catch (e) {
      error.value = e.message
      throw e
    }
  }
  
  /**
   * 从回收站恢复
   */
  async function restoreNote(noteId) {
    try {
      await fetch(`/api/notes/${noteId}/restore/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        }
      })

      // 從當前列表移除（回收站視圖）
      currentNotes.value = currentNotes.value.filter(n => n.id !== noteId)

      // 【新增】觸發筆記還原事件，讓預覽區清空
      window.dispatchEvent(new CustomEvent('note-restored-from-trash', {
        detail: { noteId }
      }))
    } catch (e) {
      error.value = e.message
      throw e
    }
  }
  
  /**
   * 永久删除笔记
   */
  async function permanentDeleteNote(noteId) {
    try {
      await fetch(`/api/notes/${noteId}/permanent-delete/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        }
      })
      
      // 从当前列表移除
      currentNotes.value = currentNotes.value.filter(n => n.id !== noteId)
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  return {
    // 状态
    activeModule,
    isCollapsed,
    secondaryView,
    currentFolderId,
    currentNoteId,
    folders,
    inboxCount,
    currentNotes,
    currentSubfolders,
    currentFolder,
    breadcrumb,
    isLoading,
    error,
    isInitialized,

    // 保密柜状态
    vaultStatus,
    vaultVerifyDialogVisible,
    vaultSetup2faDialogVisible,

    // 计算属性
    showSecondary,
    moduleTitle,

    // 动作
    setActiveModule,
    setCurrentNoteId,
    initFromUrl,
    toggleCollapse,
    setCollapsed,
    loadModuleData,
    loadAllNotes,
    loadFolders,
    loadFavoritedNotes,
    loadTrashedNotes,
    enterFolder,
    enterInbox,
    backToFolders,
    createFolder,
    renameFolder,
    renameNote,
    deleteFolder,
    moveNoteToFolder,
    toggleNoteFavorite,
    trashNote,
    restoreNote,
    permanentDeleteNote,
    enterTrashedFolder,      // 【新增】
    backToTrashRoot,         // 【新增】
    restoreFolder,           // 【新增】
    permanentDeleteFolder,   // 【新增】

    // 保密柜动作
    loadVaultStatus,
    loadVaultNotes,
    enterVault,
    onVaultVerified,
    lockVault
  }
})
