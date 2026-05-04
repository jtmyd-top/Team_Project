/**
 * SecondaryPanel 逻辑层
 * 处理侧边栏导航、文件夹操作、笔记列表、保密柜集成等功能
 */

import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSidebarStore } from '@/stores/sidebar'
import { useVaultStore } from '@/stores/vault'
import { useVaultEncryption } from '@/composables/useVaultEncryption'
import { useClientCrypto } from '@/composables/useClientCrypto'

export function useSecondaryPanel(props, emit) {
  // ==================== Stores & Composables ====================
  const sidebarStore = useSidebarStore()
  const vaultStore = useVaultStore()

  // 【关键】在组件顶部统一调用一次，确保整个组件使用同一个实例
  const { tryRecoverKeyFromSession } = useVaultEncryption()
  const { encryptContent, decryptContent } = useClientCrypto()

  // ==================== 响应式状态 ====================
  const isMobile = ref(false)
  const MOBILE_BREAKPOINT = 900  // 小于此宽度视为移动端/小屏

  // 拖拽相关状态
  const isInboxDragOver = ref(false)

  // 本地状态
  const searchQuery = ref('')
  const showCreateFolderDialog = ref(false)
  const newFolderName = ref('')
  const parentFolderIdForNew = ref(null)
  const folderNameInput = ref(null)

  // 右键菜单状态
  const contextMenuVisible = ref(false)
  const contextMenuX = ref(0)
  const contextMenuY = ref(0)
  const contextMenuNote = ref(null)

  // 移动对话框状态
  const moveDialogVisible = ref(false)
  const moveDialogNote = ref(null)
  const moveDialogMode = ref('move') // 'move' or 'copy'

  // 编辑状态
  const editingNoteId = ref(null)

  // 批量选择状态（回收站专用）
  const batchSelectMode = ref(false)
  const selectedItems = ref([]) // { type: 'note'|'folder', id: number }[]

  // ==================== 计算属性 ====================
  const isInTrashView = computed(() => {
    return sidebarStore.activeModule === 'trash'
  })

  const showBackButton = computed(() => {
    return sidebarStore.activeModule === 'my-space' && sidebarStore.secondaryView === 'notes'
      || (isInTrashView.value && sidebarStore.currentFolder)
  })

  const panelTitle = computed(() => {
    if (sidebarStore.activeModule === 'my-space') {
      if (sidebarStore.secondaryView === 'notes') {
        return sidebarStore.currentFolder?.name || '未分类笔记'
      }
      return '笔记分类'
    }
    if (isInTrashView.value && sidebarStore.currentFolder) {
      return sidebarStore.currentFolder.name
    }
    return sidebarStore.moduleTitle
  })

  const showNewNoteBtn = computed(() => {
    // 在保密柜模块中，只有已验证（解锁）状态才显示新建按钮
    if (sidebarStore.activeModule === 'vault') {
      return sidebarStore.vaultStatus.isVerified
    }
    return ['all-notes', 'my-space'].includes(sidebarStore.activeModule)
  })

  const showNewFolderBtn = computed(() => {
    // 在文件夹列表视图或在子文件夹内都显示新建文件夹按钮
    return sidebarStore.activeModule === 'my-space' &&
      (sidebarStore.secondaryView === 'folders' || sidebarStore.currentFolderId !== null)
  })

  const showSearch = computed(() => {
    return sidebarStore.activeModule === 'all-notes'
  })

  const showFolderInfo = computed(() => {
    return ['all-notes', 'favorites'].includes(sidebarStore.activeModule)
  })

  const showCreateNoteInEmpty = computed(() => {
    // 回收站不显示新建按钮
    if (sidebarStore.activeModule === 'trash') return false

    // 在保密柜模块中，只有已验证（解锁）状态才显示空状态下的新建按钮
    if (sidebarStore.activeModule === 'vault') {
      return sidebarStore.vaultStatus.isVerified
    }

    return true
  })

  const emptyStateText = computed(() => {
    const texts = {
      'all-notes': '还没有笔记',
      'my-space': '此文件夹为空',
      'favorites': '还没有收藏的笔记',
      'trash': '回收站是空的',
      'vault': '保密柜是空的'
    }
    return texts[sidebarStore.activeModule] || '暂无内容'
  })

  // 批量选择：是否全选
  const isAllSelected = computed(() => {
    if (!isInTrashView.value || filteredNotes.value.length === 0) return false
    return filteredNotes.value.every(item =>
      selectedItems.value.some(s => s.type === item.type && s.id === item.id)
    )
  })

  // 批量选择：是否部分选中
  const isPartialSelected = computed(() => {
    if (!isInTrashView.value || filteredNotes.value.length === 0) return false
    const selectedCount = filteredNotes.value.filter(item =>
      selectedItems.value.some(s => s.type === item.type && s.id === item.id)
    ).length
    return selectedCount > 0 && selectedCount < filteredNotes.value.length
  })

  // 批量选择：选中数量
  const selectedCount = computed(() => selectedItems.value.length)

  const filteredNotes = computed(() => {
    if (!searchQuery.value) {
      return sidebarStore.currentNotes
    }
    const query = searchQuery.value.toLowerCase()
    return sidebarStore.currentNotes.filter(note =>
      note.title.toLowerCase().includes(query)
    )
  })

  // ==================== 监听器 ====================
  // 【新增】监听保密柜解锁状态变化，触发回收站笔记标题的重新解密/清除
  watch(
    () => vaultStore.isUnlocked,
    async (unlocked) => {
      if (unlocked && sidebarStore.activeModule === 'trash') {
        console.log('[SecondaryPanel] Vault unlocked, retrying trash note decryption')
        for (const note of sidebarStore.currentNotes) {
          if (note.is_secret && note.title && !note.decryptedTitle) {
            try {
              const plainTitle = await decryptContent(note.title)
              note.decryptedTitle = plainTitle
              console.log('[SecondaryPanel] ✅ Title decrypted after unlock:', note.id)
            } catch (e) {
              console.warn('[SecondaryPanel] Failed to decrypt after unlock:', note.id)
            }
          }
        }
      } else if (!unlocked) {
        console.log('[SecondaryPanel] Vault locked, clearing decryptedTitles')
        sidebarStore.currentNotes.forEach(note => {
          if (note.is_secret && note.decryptedTitle) {
            note.decryptedTitle = undefined
          }
        })
      }
    }
  )

  // 【新增】监听回收站笔记变化，自动解密保密笔记的标题
  watch(
    () => ({
      notes: sidebarStore.currentNotes,
      isTrash: sidebarStore.activeModule === 'trash',
      unlocked: vaultStore.isUnlocked
    }),
    async ({ notes, isTrash, unlocked }) => {
      if (!isTrash) return

      for (const note of notes) {
        if (note.decryptedTitle) continue
        if (!note.is_secret || !note.title) continue

        if (unlocked) {
          try {
            const plainTitle = await decryptContent(note.title)
            note.decryptedTitle = plainTitle
          } catch (e) {
            console.warn('[SecondaryPanel] ❌ Failed to decrypt trash note title:', note.id, e.message)
          }
        }
      }
    },
    { deep: true, immediate: true }
  )

  // 监听对话框显示，自动聚焦输入框
  watch(showCreateFolderDialog, (show) => {
    if (show) {
      nextTick(() => {
        folderNameInput.value?.focus()
      })
    } else {
      newFolderName.value = ''
      parentFolderIdForNew.value = null
    }
  })

  // ==================== 响应式检测 ====================
  function checkMobile() {
    isMobile.value = window.innerWidth < MOBILE_BREAKPOINT
    // 小屏幕下自动收起侧边栏
    if (isMobile.value && !sidebarStore.isCollapsed) {
      sidebarStore.setCollapsed(true)
    }
  }

  onMounted(() => {
    checkMobile()
    window.addEventListener('resize', checkMobile)

    // 【新增】监听来自 NoteListItem 的解锁请求
    window.addEventListener('request-vault-unlock', (event) => {
      const { fromTrash, noteId } = event.detail
      console.log('[SecondaryPanel] Received vault unlock request from trash:', noteId)
      // 触发保密柜解锁对话框
      // 这将由 AppLayout 或更高级的组件处理
      window.dispatchEvent(new CustomEvent('open-vault-unlock-dialog', {
        detail: { fromTrash, noteId }
      }))
    })
  })

  onUnmounted(() => {
    window.removeEventListener('resize', checkMobile)
  })

  // ==================== 导航操作 ====================
  function handleBack() {
    if (isInTrashView.value && sidebarStore.currentFolder) {
      // 【新增】从回收站文件夹返回根目录
      sidebarStore.backToTrashRoot()
    } else {
      sidebarStore.backToFolders()
    }
  }

  function handleSearch() {
    // 搜索逻辑已通过 computed 实现
  }

  function clearSearch() {
    searchQuery.value = ''
  }

  function handleFolderClick(folder) {
    sidebarStore.enterFolder(folder.id)
  }

  function handleSubfolderClick(subfolder) {
    if (isInTrashView.value) {
      // 【新增】回收站中进入文件夹
      sidebarStore.enterTrashedFolder(subfolder.id)
    } else {
      sidebarStore.enterFolder(subfolder.id)
    }
  }

  // 【新增】回收站混合列表点击处理
  function handleTrashItemClick(item) {
    if (item.type === 'folder') {
      sidebarStore.enterTrashedFolder(item.id)
    } else {
      // 【关键修复】如果是加密笔记且未解锁，先触发解锁流程
      if (item.is_secret && !vaultStore.isUnlocked) {
        console.log('[SecondaryPanel] Encrypted note in trash clicked without DEK, triggering unlock')
        window.dispatchEvent(new CustomEvent('request-vault-unlock', {
          detail: { fromTrash: true, noteId: item.id }
        }))
        return
      }
      emit('note-select', item.id)
    }
  }

  // 【新增】回收站项目恢复
  async function handleItemRestore(item) {
    try {
      await ElMessageBox.confirm(
        item.type === 'folder'
          ? `文件夹"${item.name}"及其内容将被恢复到原位置。`
          : '笔记将被恢复到原位置。',
        '确认恢复',
        {
          confirmButtonText: '确认恢复',
          cancelButtonText: '取消',
          type: 'success'
        }
      )

      if (item.type === 'folder') {
        await sidebarStore.restoreFolder(item.id)
        ElMessage.success('文件夹已恢复')
      } else {
        await sidebarStore.restoreNote(item.id)
        ElMessage.success('笔记已恢复')
      }
    } catch {
      // 用户取消
    }
  }

  // 【新增】回收站项目删除
  async function handleItemDelete(item) {
    try {
      await ElMessageBox.confirm(
        item.type === 'folder'
          ? `文件夹"${item.name}"及其所有内容将被永久删除，此操作不可恢复。`
          : '此操作不可恢复，笔记将被永久删除。',
        item.type === 'folder' ? '永久删除文件夹' : '永久删除笔记',
        {
          confirmButtonText: '确认永久删除',
          cancelButtonText: '取消',
          type: 'error',
          confirmButtonClass: 'el-button--danger',
          customClass: 'delete-confirm-box'
        }
      )

      if (item.type === 'folder') {
        await sidebarStore.permanentDeleteFolder(item.id)
        ElMessage.success('文件夹已永久删除')
      } else {
        await sidebarStore.permanentDeleteNote(item.id)
        ElMessage.success('笔记已永久删除')
      }
    } catch {
      // 用户取消
    }
  }

  // 【新增】显示笔记标题（处理加密笔记）
  function displayTitle(item) {
    if (!item.is_secret || item.decryptedTitle) {
      return item.decryptedTitle || item.title
    }
    return '加密笔记 - 点击解锁'
  }

  // ==================== 批量操作（回收站专用）====================

  // 切换批量选择模式
  function toggleBatchSelectMode() {
    batchSelectMode.value = !batchSelectMode.value
    if (!batchSelectMode.value) {
      selectedItems.value = []
    }
  }

  // 退出批量选择模式
  function exitBatchSelectMode() {
    batchSelectMode.value = false
    selectedItems.value = []
  }

  // 检查项目是否被选中
  function isItemSelected(item) {
    return selectedItems.value.some(s => s.type === item.type && s.id === item.id)
  }

  // 切换单个项目的选中状态
  function toggleItemSelection(item) {
    const index = selectedItems.value.findIndex(s => s.type === item.type && s.id === item.id)
    if (index > -1) {
      selectedItems.value.splice(index, 1)
    } else {
      selectedItems.value.push({ type: item.type, id: item.id, name: item.name || item.title })
    }
  }

  // 全选/取消全选
  function toggleSelectAll() {
    if (isAllSelected.value) {
      // 取消全选
      selectedItems.value = []
    } else {
      // 全选当前列表
      selectedItems.value = filteredNotes.value.map(item => ({
        type: item.type,
        id: item.id,
        name: item.name || item.title
      }))
    }
  }

  // 批量恢复
  async function handleBatchRestore() {
    if (selectedItems.value.length === 0) return

    try {
      await ElMessageBox.confirm(
        `确定要恢复选中的 ${selectedItems.value.length} 个项目吗？`,
        '批量恢复',
        {
          confirmButtonText: '确认恢复',
          cancelButtonText: '取消',
          type: 'success'
        }
      )

      const errors = []
      for (const item of selectedItems.value) {
        try {
          if (item.type === 'folder') {
            await sidebarStore.restoreFolder(item.id)
          } else {
            await sidebarStore.restoreNote(item.id)
          }
        } catch (e) {
          errors.push(item.name || item.id)
        }
      }

      if (errors.length === 0) {
        ElMessage.success(`成功恢复 ${selectedItems.value.length} 个项目`)
      } else if (errors.length < selectedItems.value.length) {
        ElMessage.warning(`部分恢复成功，${errors.length} 个项目恢复失败`)
      } else {
        ElMessage.error('恢复失败')
      }

      // 清空选择并退出批量模式
      exitBatchSelectMode()
    } catch {
      // 用户取消
    }
  }

  // 批量永久删除
  async function handleBatchDelete() {
    if (selectedItems.value.length === 0) return

    try {
      await ElMessageBox.confirm(
        `确定要永久删除选中的 ${selectedItems.value.length} 个项目吗？此操作不可恢复！`,
        '批量永久删除',
        {
          confirmButtonText: '确认永久删除',
          cancelButtonText: '取消',
          type: 'error',
          confirmButtonClass: 'el-button--danger',
          customClass: 'delete-confirm-box'
        }
      )

      const errors = []
      for (const item of selectedItems.value) {
        try {
          if (item.type === 'folder') {
            await sidebarStore.permanentDeleteFolder(item.id)
          } else {
            await sidebarStore.permanentDeleteNote(item.id)
          }
        } catch (e) {
          errors.push(item.name || item.id)
        }
      }

      if (errors.length === 0) {
        ElMessage.success(`成功删除 ${selectedItems.value.length} 个项目`)
      } else if (errors.length < selectedItems.value.length) {
        ElMessage.warning(`部分删除成功，${errors.length} 个项目删除失败`)
      } else {
        ElMessage.error('删除失败')
      }

      // 清空选择并退出批量模式
      exitBatchSelectMode()
    } catch {
      // 用户取消
    }
  }

  // ==================== 文件夹操作 ====================
  function handleFolderRename(folder, newName) {
    sidebarStore.renameFolder(folder.id, newName)
  }

  async function handleFolderDelete(folder) {
    try {
      await ElMessageBox.confirm(
        `文件夹内的笔记将移动到未分类笔记。`,
        `确定删除"${folder.name}"？`,
        {
          confirmButtonText: '确认删除',
          cancelButtonText: '取消',
          type: 'error',
          confirmButtonClass: 'el-button--danger',
          customClass: 'delete-confirm-box'
        }
      )
      sidebarStore.deleteFolder(folder.id)
    } catch {
      // 用户取消
    }
  }

  function handleCreateSubfolder(parentFolder) {
    parentFolderIdForNew.value = parentFolder.id
    showCreateFolderDialog.value = true
    nextTick(() => {
      folderNameInput.value?.focus()
    })
  }

  // 点击新建文件夹按钮
  function handleNewFolderClick() {
    // 如果当前在文件夹内，创建的是子文件夹
    if (sidebarStore.secondaryView === 'notes' && sidebarStore.currentFolderId) {
      parentFolderIdForNew.value = sidebarStore.currentFolderId
    } else {
      parentFolderIdForNew.value = null
    }
    showCreateFolderDialog.value = true
    nextTick(() => {
      folderNameInput.value?.focus()
    })
  }

  async function createFolder() {
    if (!newFolderName.value.trim()) return

    try {
      await sidebarStore.createFolder(newFolderName.value.trim(), parentFolderIdForNew.value)
      showCreateFolderDialog.value = false
      newFolderName.value = ''
      parentFolderIdForNew.value = null
    } catch (e) {
      console.error('创建文件夹失败:', e)
    }
  }

  // ==================== 笔记操作 ====================
  function handleNoteClick(note) {
    emit('note-select', note.id)
  }

  function handleNoteFavorite(note) {
    sidebarStore.toggleNoteFavorite(note.id)
  }

  async function handleNoteRename(note, newTitle) {
    try {
      await sidebarStore.renameNote(note.id, newTitle)
      editingNoteId.value = null
    } catch (e) {
      console.error('重命名笔记失败:', e)
      ElMessage.error('重命名失败，请重试')
    }
  }

  async function handleNoteTrash(note) {
    try {
      await ElMessageBox.confirm(
        '笔记将被移入回收站，可以随时恢复。',
        `移入回收站？`,
        {
          confirmButtonText: '确认移入回收站',
          cancelButtonText: '取消',
          type: 'warning',
          confirmButtonClass: 'el-button--warning'
        }
      )
      sidebarStore.trashNote(note.id)
    } catch {
      // 用户取消
    }
  }

  function handleNoteRestore(note) {
    sidebarStore.restoreNote(note.id)
  }

  async function handleNoteDelete(note) {
    try {
      await ElMessageBox.confirm(
        '此操作不可恢复，笔记将被永久删除。',
        `永久删除"${note.title}"？`,
        {
          confirmButtonText: '确认永久删除',
          cancelButtonText: '取消',
          type: 'error',
          confirmButtonClass: 'el-button--danger',
          customClass: 'delete-confirm-box'
        }
      )
      sidebarStore.permanentDeleteNote(note.id)
    } catch {
      // 用户取消
    }
  }

  async function handleCreateNote() {
    emit('note-create', sidebarStore.currentFolderId)
  }

  // ==================== 保密柜相关 ====================
  /**
   * 加密笔记内容并保存
   * 使用 vaultStore.encrypt（内部走 Web Crypto + 非导出 CryptoKey），调用前需确保 vault 已解锁
   * @param {Object} note - 笔记对象
   */
  function assertEncryptionSourceIntegrity(latestNoteData, sourceSnapshot) {
    const latestContent = latestNoteData?.content || ''
    const snapshotContent = sourceSnapshot?.content || ''

    if (!snapshotContent) return

    if (latestContent.length < snapshotContent.length) {
      throw new Error(
        `安全中止：待加密内容长度异常变短（当前 ${latestContent.length}，原始 ${snapshotContent.length}）。为避免笔记内容丢失，已取消纳入保密柜。`
      )
    }
  }

  async function performEncryption(note, sourceSnapshot = null) {
    if (!note || !note.id) {
      throw new Error('笔记对象无效')
    }

    if (!vaultStore.isUnlocked) {
      throw new Error('保密柜未解锁，无法加密')
    }

    try {
      // 【关键】始终从数据库加载最新的笔记数据，确保获取的是最新内容
      console.log(`[Vault] Loading latest note data for ID: ${note.id}`)
      const fetchResp = await fetch(`/api/notes/${note.id}/?full_content=true`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })

      if (!fetchResp.ok) {
        throw new Error('加载笔记数据失败')
      }

      const noteData = await fetchResp.json()
      let plainTitle = noteData.title || ''
      let plainContent = noteData.content || ''

      assertEncryptionSourceIntegrity(noteData, sourceSnapshot)

      if (!plainContent || plainContent.trim() === '') {
        throw new Error('笔记内容为空，无法加密')
      }

      if (!plainTitle || plainTitle.trim() === '') {
        throw new Error('笔记标题为空，无法加密')
      }

      console.log('[Vault] performEncryption: Ready to encrypt', {
        noteId: note.id,
        plainTitleLength: plainTitle.length,
        plainContentLength: plainContent.length
      })

      // 【关键】同时加密 title 和 content（异步）
      const encryptedTitle = await encryptContent(plainTitle)
      const encryptedContent = await encryptContent(plainContent)

      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value

      const updateResponse = await fetch(`/api/notes/${note.id}/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          title: encryptedTitle,
          content: encryptedContent,
          vault_source_content_length: plainContent.length,
          vault_original_content_length: (sourceSnapshot?.content || '').length || plainContent.length
        })
      })

      if (!updateResponse.ok) {
        const errorData = await updateResponse.json()
        throw new Error('保存加密内容失败: ' + (errorData.message || '后端错误'))
      }

      console.log('[Vault] performEncryption: Encrypted data saved successfully')
    } catch (e) {
      console.error('[Vault] performEncryption error:', e)
      throw e
    }
  }

  /**
   * 等待保密柜解锁（用于 Branch B：用户先触发加密，再弹 2FA）
   * @returns {Promise<boolean>} 是否在超时前解锁成功
   */
  async function waitForUnlock(timeout = 5000) {
    return new Promise((resolve) => {
      if (vaultStore.isUnlocked) {
        resolve(true)
        return
      }

      const unsubscribe = vaultStore.onLockStateChange((state) => {
        if (state === 'unlock') {
          clearTimeout(timeoutHandle)
          unsubscribe()
          resolve(true)
        }
      })

      const timeoutHandle = setTimeout(() => {
        unsubscribe()
        resolve(false)
      }, timeout)
    })
  }

  /**
   * 撤销 is_secret 标志
   */
  async function revertSecretFlag(note) {
    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value
      await fetch(`/api/notes/${note.id}/toggle-secret/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'Content-Type': 'application/json'
        }
      })
    } catch (e) {
      console.warn('[Vault] Failed to revert is_secret flag:', e)
    }
  }

  /**
   * 刷新保密柜数据
   */
  async function refreshVaultData(note) {
    if (sidebarStore.activeModule === 'all-notes') {
      // 从全部笔记列表中移除
      const index = sidebarStore.currentNotes.findIndex(n => n.id === note.id)
      if (index > -1) {
        sidebarStore.currentNotes.splice(index, 1)
      }
    } else if (sidebarStore.activeModule === 'vault') {
      // 在保密柜中，刷新列表
      await sidebarStore.loadModuleData()
    } else {
      // 其他情况，重新加载数据
      await sidebarStore.loadModuleData()
    }
  }

  /**
   * 执行加密并保存
   * 包含两个分支的智能逻辑
   */
  async function executeEncryptAndSave(note, sourceSnapshot = null) {
    if (vaultStore.isUnlocked) {
      // ========== 分支 A: Smart Pass（已解锁）==========
      console.log('[Vault] Branch A: Smart Pass - Vault already unlocked')
      try {
        await performEncryption(note, sourceSnapshot)
        ElMessage.success('加入保密柜成功！内容已加密')
        await refreshVaultData(note)
      } catch (e) {
        console.error('[Vault] Smart Pass encryption failed:', e)
        ElMessage.error('加密失败: ' + e.message)
        await revertSecretFlag(note)
      }
    } else {
      // ========== 分支 B: Require Auth（未解锁）==========
      console.log('[Vault] Branch B: Require Auth - Need 2FA verification')

      // 撤销 is_secret 标志，因为加密还未完成
      await revertSecretFlag(note)

      // 定义待处理的加密操作（验证成功后执行）
      const encryptOperation = async () => {
        const unlocked = await waitForUnlock()
        if (!unlocked) {
          throw new Error('未能获取有效的加密密钥')
        }

        // 再次切换 is_secret（因为刚才撤销了）
        const retoggleResp = await fetch(`/api/notes/${note.id}/toggle-secret/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value,
            'Content-Type': 'application/json'
          }
        })

        if (!retoggleResp.ok) {
          throw new Error('重新标记为保密笔记失败')
        }

        await performEncryption(note, sourceSnapshot)
      }

      vaultStore.setPendingOperation(note.id, note.content, encryptOperation)

      // 弹出 2FA 验证对话框
      sidebarStore.vaultVerifyDialogVisible = true

      // 监听验证成功事件：此时 vault 已被 dialog 内部解锁，直接执行 pending operation
      const handleVerifySuccess = async () => {
        try {
          await vaultStore.executePendingOperation()
          ElMessage.success('加入保密柜成功！内容已加密')
          await refreshVaultData(note)
        } catch (e) {
          console.error('[Vault] Failed to execute pending operation:', e)
          ElMessage.error('加密失败: ' + e.message)
          vaultStore.clearPendingOperation()
          await revertSecretFlag(note)
        }
        window.removeEventListener('vault-verification-success', handleVerifySuccess)
      }

      window.addEventListener('vault-verification-success', handleVerifySuccess, { once: true })
    }
  }

  /**
   * 处理笔记保密状态切换
   * 智能逻辑：
   * - 分支 A（Smart Pass）：如果已有有效的 DEK，直接加密，无需弹窗
   * - 分支 B（Require Auth）：如果没有有效 DEK，先弹窗验证，验证后自动继续加密
   */
  async function handleToggleSecret(note) {
    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value

      // 【关键修复】移出保密柜时需要调整顺序：
      // 先获取笔记数据和 is_secret 状态，再切换标记

      // 1. 先获取笔记的当前状态
      const currentNoteResp = await fetch(`/api/notes/${note.id}/?full_content=true`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })

      if (!currentNoteResp.ok) {
        throw new Error('获取笔记数据失败')
      }

      const currentNote = await currentNoteResp.json()
      const wasSecret = currentNote.is_secret  // 切换前的状态

      console.log('[Vault] Current note status:', {
        noteId: note.id,
        isSecret: currentNote.is_secret,
        titleLength: currentNote.title?.length || 0,
        contentLength: currentNote.content?.length || 0
      })

      // 2. 切换 is_secret 标记
      const response = await fetch(`/api/notes/${note.id}/toggle-secret/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error('切换失败')
      }

      const data = await response.json()

      // 3. 根据切换后的状态处理
      if (!data.is_secret) {
        // ========== 移出保密柜 ==========
        // 【关键】如果笔记之前是加密的，需要解密并保存明文

        if (wasSecret) {
          console.log('[Vault] Moving note out of vault, will decrypt and save plaintext...')

          // 确保 vault 已解锁
          if (!vaultStore.isUnlocked) {
            console.log('[Vault] Vault locked, attempting to recover...')
            await tryRecoverKeyFromSession()

            if (!vaultStore.isUnlocked) {
              console.error('[Vault] Cannot get key for decryption')
              ElMessage.error('无法获取解密密钥，请先进行 2FA 验证')
              // 恢复 is_secret 标记
              await fetch(`/api/notes/${note.id}/toggle-secret/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken }
              })
              return
            }
          }

          // 解密 title 和 content
          let decryptedTitle = currentNote.title || ''
          let decryptedContent = currentNote.content || ''

          console.log('[Vault] Attempting to decrypt...', {
            titleLength: decryptedTitle.length,
            contentLength: decryptedContent.length
          })

          try {
            if (decryptedTitle) {
              try {
                const result = await decryptContent(decryptedTitle)
                console.log('[Vault] Title decrypted successfully, length:', result.length)
                decryptedTitle = result
              } catch (e) {
                console.warn('[Vault] Title decryption failed, treating as plaintext:', e.message)
                decryptedTitle = currentNote.title || ''
              }
            }

            if (decryptedContent) {
              try {
                const result = await decryptContent(decryptedContent)
                console.log('[Vault] Content decrypted successfully, length:', result.length)
                decryptedContent = result
              } catch (e) {
                console.warn('[Vault] Content decryption failed, treating as plaintext:', e.message)
                decryptedContent = currentNote.content || ''
              }
            }

            // 保存明文内容到数据库
            console.log('[Vault] Saving plaintext to database...', {
              titleLength: decryptedTitle.length,
              contentLength: decryptedContent.length
            })

            const saveResponse = await fetch(`/api/notes/${note.id}/`, {
              method: 'PATCH',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
              },
              body: JSON.stringify({
                title: decryptedTitle,
                content: decryptedContent
              })
            })

            if (!saveResponse.ok) {
              const errorData = await saveResponse.json()
              throw new Error('保存明文内容失败: ' + (errorData.error || '后端错误'))
            }

            console.log('[Vault] Plaintext saved successfully to database')
          } catch (e) {
            console.error('[Vault] Error during decrypt and save:', e)
            ElMessage.error('处理笔记内容时出错: ' + e.message)
            // 恢复 is_secret 标记
            await fetch(`/api/notes/${note.id}/toggle-secret/`, {
              method: 'POST',
              headers: { 'X-CSRFToken': csrfToken }
            })
            return
          }
        } else {
          console.log('[Vault] Note was not encrypted, no decryption needed')
        }

        // 显示成功消息
        if (data.is_secret === false && !data.is_public) {
          ElMessage.success('移出保密柜成功！已自动取消分享')
        } else {
          ElMessage.success('移出保密柜成功')
        }

        // 【P0】触发事件：笔记已从保密柜移出
        window.dispatchEvent(new CustomEvent('note-moved-from-vault', {
          detail: { noteId: note.id }
        }))

        // 刷新数据
        if (sidebarStore.activeModule === 'vault') {
          // 从保密柜列表中移除
          const index = sidebarStore.currentNotes.findIndex(n => n.id === note.id)
          if (index > -1) {
            sidebarStore.currentNotes.splice(index, 1)
          }
        } else {
          await sidebarStore.loadModuleData()
        }
      } else {
        // ========== 加入保密柜 ==========
        // 需要加密内容，执行智能流程
        await executeEncryptAndSave(note, currentNote)

        // 【P0】触发事件：笔记已移入保密柜
        window.dispatchEvent(new CustomEvent('note-moved-to-vault', {
          detail: { noteId: note.id }
        }))

        ElMessage.success('加入保密柜成功')
      }

      // 如果当前正在编辑该笔记，更新其状态
      if (props.activeNoteId === note.id) {
        try {
          // 派发事件通知 KnowledgeList 更新笔记状态
          window.dispatchEvent(new CustomEvent('note-secret-toggled', {
            detail: {
              noteId: note.id,
              isSecret: data.is_secret,
              isPublic: data.is_public
            }
          }))
        } catch (e) {
          console.warn('Failed to dispatch note-secret-toggled event:', e)
        }
      }
    } catch (error) {
      console.error('[Vault] Toggle secret failed:', error)
      ElMessage.error(`操作失败: ${error.message}`)
    }
  }

  // 锁定保密柜
  async function handleLockVault() {
    try {
      await sidebarStore.lockVault()
      ElMessage.success('保密柜已锁定')
      sidebarStore.setActiveModule('all-notes')
    } catch (e) {
      ElMessage.error('锁定失败')
    }
  }

  // 格式化保密柜剩余时间
  function formatVaultTime(seconds) {
    if (!seconds || seconds <= 0) return '0:00'
    const minutes = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${minutes}:${secs.toString().padStart(2, '0')}`
  }

  // 解锁保密柜（显示验证对话框）
  function handleUnlockVault() {
    sidebarStore.vaultVerifyDialogVisible = true
  }

  // ==================== 右键菜单处理 ====================

  // 显示右键菜单
  function handleNoteContextMenu({ note, x, y }) {
    contextMenuNote.value = note
    contextMenuX.value = x
    contextMenuY.value = y
    contextMenuVisible.value = true
  }

  // 处理右键菜单操作
  async function handleContextMenuAction(action, note) {
    switch (action) {
      case 'create':
        handleCreateNote()
        break

      case 'rename':
        // 触发原位重命名
        editingNoteId.value = note.id
        break

      case 'favorite':
        handleNoteFavorite(note)
        break

      case 'toggle-secret':
        handleToggleSecret(note)
        break

      case 'move':
        moveDialogNote.value = note
        moveDialogMode.value = 'move'
        moveDialogVisible.value = true
        break

      case 'copy':
        moveDialogNote.value = note
        moveDialogMode.value = 'copy'
        moveDialogVisible.value = true
        break

      case 'copyLink':
        try {
          const link = `${window.location.origin}/knowledge/?note=${note.id}`

          // 尝试使用现代 Clipboard API
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(link)
            ElMessage.success('链接已复制')
          } else {
            // 降级方案：使用旧的 document.execCommand 方法
            const textArea = document.createElement('textarea')
            textArea.value = link
            textArea.style.position = 'fixed'
            textArea.style.left = '-999999px'
            textArea.style.top = '-999999px'
            document.body.appendChild(textArea)
            textArea.focus()
            textArea.select()

            try {
              const successful = document.execCommand('copy')
              document.body.removeChild(textArea)

              if (successful) {
                ElMessage.success('链接已复制')
              } else {
                throw new Error('execCommand failed')
              }
            } catch (err) {
              document.body.removeChild(textArea)
              throw err
            }
          }
        } catch (e) {
          console.error('复制失败:', e)
          ElMessage.error('复制失败，请手动复制')
        }
        break

      case 'openNew':
        window.open(`/note/${note.id}`, '_blank')
        break

      case 'trash':
        handleNoteTrash(note)
        break
    }
  }

  // 移动完成回调
  function handleMoveConfirm({ noteId, folderId, folderName }) {
    // 移动已在 MoveToDialog 内部完成
    // 这里可以做额外的处理，如刷新列表
  }

  // ==================== 拖拽放置处理 ====================

  // 收件箱（未分类）拖拽悬停
  function handleInboxDragOver(event) {
    event.dataTransfer.dropEffect = 'move'
    isInboxDragOver.value = true
  }

  // 收件箱拖拽离开
  function handleInboxDragLeave(event) {
    const rect = event.currentTarget.getBoundingClientRect()
    const x = event.clientX
    const y = event.clientY

    if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
      isInboxDragOver.value = false
    }
  }

  // 放置到收件箱（移动到未分类）
  async function handleInboxDrop(event) {
    isInboxDragOver.value = false

    const data = event.dataTransfer.getData('application/json')
    if (!data) return

    try {
      const payload = JSON.parse(data)

      if (payload.type === 'NOTE_ITEM') {
        // 如果已经在未分类中，不执行移动
        if (payload.currentFolderId === null) {
          console.log('笔记已在未分类中，无需移动')
          return
        }

        await moveNoteToFolder(payload.id, null, '未分类笔记')
      }
    } catch (e) {
      console.error('处理拖拽失败:', e)
    }
  }

  // 放置到文件夹
  async function handleNoteDrop(dropData) {
    const { noteId, noteTitle, targetFolderId, targetFolderName } = dropData
    await moveNoteToFolder(noteId, targetFolderId, targetFolderName)
  }

  // 移动笔记到文件夹的通用方法
  async function moveNoteToFolder(noteId, folderId, folderName) {
    try {
      await sidebarStore.moveNoteToFolder(noteId, folderId)
      ElMessage.success(`已移动到「${folderName}」`)
    } catch (e) {
      console.error('移动笔记失败:', e)
      ElMessage.error('移动失败，请重试')
    }
  }

  // ==================== 返回 ====================
  return {
    // 状态
    isMobile,
    isInboxDragOver,
    searchQuery,
    showCreateFolderDialog,
    newFolderName,
    parentFolderIdForNew,
    folderNameInput,
    contextMenuVisible,
    contextMenuX,
    contextMenuY,
    contextMenuNote,
    moveDialogVisible,
    moveDialogNote,
    moveDialogMode,
    editingNoteId,

    // 批量选择状态
    batchSelectMode,
    selectedItems,
    isAllSelected,
    isPartialSelected,
    selectedCount,

    // 计算属性
    isInTrashView,
    showBackButton,
    panelTitle,
    showNewNoteBtn,
    showNewFolderBtn,
    showSearch,
    showFolderInfo,
    showCreateNoteInEmpty,
    emptyStateText,
    filteredNotes,

    // 导航操作
    handleBack,
    handleSearch,
    clearSearch,
    handleFolderClick,
    handleSubfolderClick,
    handleTrashItemClick,
    handleItemRestore,
    handleItemDelete,
    displayTitle,

    // 批量操作
    toggleBatchSelectMode,
    exitBatchSelectMode,
    isItemSelected,
    toggleItemSelection,
    toggleSelectAll,
    handleBatchRestore,
    handleBatchDelete,

    // 文件夹操作
    handleFolderRename,
    handleFolderDelete,
    handleCreateSubfolder,
    handleNewFolderClick,
    createFolder,

    // 笔记操作
    handleNoteClick,
    handleNoteFavorite,
    handleNoteRename,
    handleNoteTrash,
    handleNoteRestore,
    handleNoteDelete,
    handleCreateNote,

    // 保密柜操作
    handleLockVault,
    formatVaultTime,
    handleUnlockVault,
    handleToggleSecret,

    // 右键菜单
    handleNoteContextMenu,
    handleContextMenuAction,
    handleMoveConfirm,

    // 拖拽操作
    handleInboxDragOver,
    handleInboxDragLeave,
    handleInboxDrop,
    handleNoteDrop,

    // Stores
    sidebarStore
  }
}
