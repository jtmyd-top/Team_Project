/**
 * KnowledgeList 逻辑层
 * 处理笔记管理、编辑、保存、加密/解密、面包屑导航等核心功能
 */

import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useSidebarStore } from '@/stores/sidebar'
import { useVaultStore } from '@/stores/vault'
import { useVaultEncryption } from '@/composables/useVaultEncryption'
import { useClientCrypto } from '@/composables/useClientCrypto'
import { ElMessage, ElMessageBox } from 'element-plus'

export function useKnowledgeList() {
  // ==================== Stores & Composables ====================
  const sidebarStore = useSidebarStore()
  const vaultStore = useVaultStore()

  // Vault encryption
  const { isKeyValid, dek, keyExpireTime, tryRecoverKeyFromSession } = useVaultEncryption()
  const { decryptContent, encryptContent, looksLikeEncrypted } = useClientCrypto()

  // ==================== 状态 ====================
  const currentNoteId = ref(null)
  const viewMode = ref('read') // 'read' | 'edit'
  const isSaving = ref(false)
  const hasUnsavedChanges = ref(false)
  const isLoadingNote = ref(false) // 笔记加载中标志
  const noteEditorRef = ref(null)
  const decryptedTitle = ref('') // 存储解密后的标题

  // 当前笔记数据
  const currentNoteData = ref({
    id: null,
    title: '',
    content: '',
    toc: [],
    updated_at: null,
    author: null,
    is_public: false,
    is_secret: false,
    is_trashed: false,
    public_url: ''
  })

  // 原始标题，用于检测标题是否被修改
  let originalTitle = ''

  // ==================== 计算属性 ====================
  const showBreadcrumb = computed(() => {
    return sidebarStore.activeModule === 'my-space' && sidebarStore.secondaryView === 'notes' && sidebarStore.currentFolderId
  })

  const isDarkMode = computed(() => {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  // 计算属性：显示的标题（已解密或原标题）
  const displayTitle = computed(() => {
    if (!currentNoteData.value.is_secret) {
      return currentNoteData.value.title || '无标题'
    }

    if (decryptedTitle.value) {
      return decryptedTitle.value
    }

    return currentNoteData.value.title || '无标题'
  })

  // ==================== 笔记操作 ====================
  // 解密笔记标题
  async function decryptNoteTitle() {
    if (!currentNoteData.value.is_secret) {
      decryptedTitle.value = ''
      return
    }

    if (!currentNoteData.value.title) {
      decryptedTitle.value = ''
      return
    }

    const dekToUse = dek.value || vaultStore.dek

    if (!dekToUse) {
      console.log('[KnowledgeList] decryptNoteTitle: No DEK available')
      decryptedTitle.value = ''
      return
    }

    try {
      const plainTitle = decryptContent(currentNoteData.value.title, dekToUse)
      decryptedTitle.value = plainTitle
      console.log('[KnowledgeList] Title decrypted successfully:', plainTitle.substring(0, 20))
    } catch (e) {
      console.warn('[KnowledgeList] Failed to decrypt title:', e.message)
      decryptedTitle.value = ''
    }
  }

  // 获取笔记详情
  async function fetchNoteDetail(noteId) {
    try {
      const response = await fetch(`/api/notes/${noteId}/?full_content=true`)
      if (!response.ok) throw new Error('Failed to fetch note')

      const data = await response.json()

      currentNoteData.value = {
        id: data.id,
        title: data.title,
        content: data.content,
        toc: data.toc || [],
        updated_at: data.updated_at,
        author: data.author,
        is_public: data.is_public || false,
        is_secret: data.is_secret || false,
        is_trashed: data.is_trashed || false,
        public_url: data.public_url || ''
      }

      hasUnsavedChanges.value = false
    } catch (e) {
      ElMessage.error('无法加载笔记内容')
    }
  }

  // 选中笔记
  async function handleNoteSelect(noteId) {
    if (hasUnsavedChanges.value) {
      try {
        await ElMessageBox.confirm('当前笔记有未保存的更改，是否保存？', '提示', {
          confirmButtonText: '保存',
          cancelButtonText: '放弃',
          type: 'warning'
        })
        await handleSave()
      } catch (e) {
        if (e !== 'cancel') {
          hasUnsavedChanges.value = false
        } else {
          return
        }
      }
    }

    isLoadingNote.value = true
    await fetchNoteDetail(noteId)
    currentNoteId.value = noteId
    sidebarStore.setCurrentNoteId(noteId)

    // 回收站中的笔记强制使用阅读模式
    if (currentNoteData.value.is_trashed) {
      viewMode.value = 'read'
    } else if (!currentNoteData.value.content && !currentNoteData.value.title) {
      viewMode.value = 'edit'
    } else {
      viewMode.value = 'read'
    }

    // 如果是加密笔记且已解锁，解密标题
    if (currentNoteData.value.is_secret) {
      await decryptNoteTitle()
    } else {
      decryptedTitle.value = ''
    }

    isLoadingNote.value = false
  }

  // 创建笔记
  async function handleCreateNote(folderId = null) {
    if (hasUnsavedChanges.value) {
      try {
        await ElMessageBox.confirm('当前笔记有未保存的更改，是否保存？', '提示', {
          confirmButtonText: '保存',
          cancelButtonText: '放弃',
          distinguishCancelAndClose: true,
          type: 'warning'
        })
        await handleSave()
      } catch (action) {
        if (action === 'close') {
          return
        }
        hasUnsavedChanges.value = false
      }
    }

    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value
      const targetFolderId = folderId ?? sidebarStore.currentFolderId
      const isVaultModule = sidebarStore.activeModule === 'vault'

      const response = await fetch('/api/notes/create/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          title: '无标题笔记',
          content: '',
          folder_id: targetFolderId,
          is_secret: isVaultModule
        })
      })

      const data = await response.json()

      if (data.error) {
        throw new Error(data.error)
      }

      const noteId = data.id || data.note_id

      if (noteId) {
        // 根据当前模块刷新数据
        switch (sidebarStore.activeModule) {
          case 'all-notes':
            await sidebarStore.loadAllNotes()
            break
          case 'my-space':
            if (sidebarStore.secondaryView === 'notes') {
              if (sidebarStore.currentFolderId) {
                await sidebarStore.enterFolder(sidebarStore.currentFolderId)
              } else {
                await sidebarStore.enterInbox()
              }
            } else {
              await sidebarStore.loadFolders()
            }
            break
          default:
            await sidebarStore.loadModuleData()
        }

        currentNoteId.value = null
        await fetchNoteDetail(noteId)

        if (isVaultModule) {
          currentNoteData.value.is_secret = true
        }

        currentNoteId.value = noteId
        sidebarStore.setCurrentNoteId(noteId)
        viewMode.value = 'edit'
      } else {
        throw new Error('创建失败：未返回笔记 ID')
      }
    } catch (e) {
      ElMessage.error('创建笔记失败')
    }
  }

  // 编辑器内容变化
  function handleEditorChange(content) {
    if (viewMode.value !== 'edit') return

    if (!content && currentNoteData.value.content && currentNoteData.value.content.length > 0) {
      return
    }

    hasUnsavedChanges.value = true
    if (content !== undefined) {
      currentNoteData.value.content = content
    }
  }

  // 切换到阅读模式（带防呆检查）
  async function handleSwitchToReadMode() {
    if (viewMode.value === 'read') return

    if (hasUnsavedChanges.value) {
      try {
        await ElMessageBox.confirm('当前笔记有未保存的更改，是否保存？', '提示', {
          confirmButtonText: '保存',
          cancelButtonText: '放弃',
          distinguishCancelAndClose: true,
          type: 'warning'
        })
        await handleSave()
      } catch (action) {
        if (action === 'close') {
          return
        }
        hasUnsavedChanges.value = false
        viewMode.value = 'read'
      }
    } else {
      viewMode.value = 'read'
    }
  }

  // 保存笔记
  async function handleSave() {
    if (!currentNoteId.value) return

    isSaving.value = true
    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value

      let contentToSave = ''
      let titleToSave = ''
      let plainTextTitle = ''

      if (noteEditorRef.value && noteEditorRef.value.getCurrentTitle) {
        titleToSave = noteEditorRef.value.getCurrentTitle()
        plainTextTitle = titleToSave
      } else {
        titleToSave = currentNoteData.value.title
        plainTextTitle = titleToSave
      }

      if (noteEditorRef.value && noteEditorRef.value.getContent) {
        contentToSave = noteEditorRef.value.getContent()
      } else {
        contentToSave = currentNoteData.value.content
      }

      // 如果是加密笔记，在前端进行加密
      if (currentNoteData.value.is_secret) {
        try {
          if (!isKeyValid.value) {
            const recovered = await tryRecoverKeyFromSession()
            if (!recovered || !isKeyValid.value) {
              ElMessage.error('加密密钥已失效，请重新进行 2FA 验证')
              isSaving.value = false
              return
            }
          }

          if (!dek.value) {
            ElMessage.error('无法获取加密密钥')
            isSaving.value = false
            return
          }

          if (titleToSave) {
            try {
              if (!looksLikeEncrypted(titleToSave)) {
                titleToSave = encryptContent(titleToSave, dek.value)
              }
            } catch (e) {
              // Error encrypting title
            }
          }

          if (!looksLikeEncrypted(contentToSave)) {
            contentToSave = encryptContent(contentToSave, dek.value)
          }
        } catch (e) {
          ElMessage.error('加密失败: ' + e.message)
          isSaving.value = false
          return
        }
      }

      const response = await fetch(`/api/notes/${currentNoteId.value}/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          title: titleToSave,
          content: contentToSave
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      ElMessage.success('保存成功')
      hasUnsavedChanges.value = false

      if (data.updated_at) {
        currentNoteData.value.updated_at = data.updated_at
      }

      const note = sidebarStore.currentNotes.find(n => n.id === currentNoteId.value)
      if (note) {
        note.title = plainTextTitle
      }

      decryptedTitle.value = plainTextTitle

      if (data.toc) {
        currentNoteData.value.toc = data.toc
      }

      window.dispatchEvent(new CustomEvent('note-title-updated', {
        detail: {
          noteId: currentNoteId.value,
          newTitle: plainTextTitle
        }
      }))

      viewMode.value = 'read'
    } catch (e) {
      ElMessage.error('保存失败，请重试')
    } finally {
      isSaving.value = false
    }
  }

  // 删除笔记
  async function handleDelete() {
    if (!currentNoteId.value) return

    try {
      await ElMessageBox.confirm(
        '确定要删除这篇笔记吗？它将被移动到回收站。',
        '确认删除',
        {
          confirmButtonText: '确认删除',
          cancelButtonText: '取消',
          type: 'error',
          confirmButtonClass: 'el-button--danger',
          customClass: 'delete-confirm-box'
        }
      )

      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value

      const response = await fetch(`/api/notes/${currentNoteId.value}/delete/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        }
      })

      const data = await response.json()

      if (data.status === 'success') {
        ElMessage.success('笔记已移至回收站')
        currentNoteId.value = null
        currentNoteData.value = { id: null, title: '', content: '', toc: [] }
        await sidebarStore.loadModuleData()
      }
    } catch (e) {
      if (e !== 'cancel') {
        ElMessage.error('删除失败')
      }
    }
  }

  // 切换笔记公开状态
  async function handleTogglePublic() {
    if (!currentNoteId.value) return

    const newPublicState = !currentNoteData.value.is_public
    const actionText = newPublicState ? '公开' : '设为私密'

    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value

      const response = await fetch(`/api/notes/${currentNoteId.value}/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          is_public: newPublicState
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      currentNoteData.value.is_public = newPublicState
      if (newPublicState && data.public_url) {
        currentNoteData.value.public_url = data.public_url
      }
      ElMessage.success(`笔记已${actionText}`)
    } catch (e) {
      ElMessage.error(`${actionText}失败，请重试`)
    }
  }

  // 复制公开链接
  async function handleCopyPublicLink() {
    if (!currentNoteData.value.public_url) {
      ElMessage.warning('该笔记没有公开链接')
      return
    }

    const fullUrl = window.location.origin + currentNoteData.value.public_url

    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(fullUrl)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = fullUrl
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      ElMessage.success('链接已复制到剪贴板')
    } catch (e) {
      ElMessage.error('复制失败，请手动复制')
    }
  }

  // ==================== 导航操作 ====================
  function handleUserProfile() {
    window.location.href = '/settings/'
  }

  function handleBreadcrumbNavigate(folderId) {
    // Breadcrumb 组件已处理导航
  }

  function handleFolderSwitch(folderId) {
    // Breadcrumb 组件已处理切换
  }

  // ==================== 保密柜操作 ====================
  async function handleVaultVerified(data) {
    sidebarStore.vaultStatus.isVerified = true
    sidebarStore.vaultStatus.remainingSeconds = data.remainingSeconds
    await sidebarStore.onVaultVerified()
  }

  function handleVaultCancel() {
    // 取消 2FA 验证时，不切换模块，只是关闭弹窗
  }

  function handleGoToSettings() {
    window.location.href = '/settings/?tab=security'
  }

  function handleVaultSetupCancel() {
    sidebarStore.vaultSetup2faDialogVisible = false
    sidebarStore.setActiveModule('all-notes')
  }

  // ==================== 工具函数 ====================
  function formatDate(dateString) {
    if (!dateString) return ''
    const date = new Date(dateString)
    return date.toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // ==================== 页面离开前防呆 ====================
  function handleBeforeUnload(e) {
    if (hasUnsavedChanges.value && viewMode.value === 'edit') {
      const message = '您有未保存的更改，确定要离开吗？'
      e.preventDefault()
      e.returnValue = message
      return message
    }
  }

  // ==================== 处理事件 ====================
  function handleNoteSecretToggled(event) {
    try {
      if (!event || !event.detail) {
        return
      }

      const { noteId, isSecret, isPublic } = event.detail

      if (!currentNoteId.value || currentNoteId.value !== noteId) {
        return
      }

      if (!currentNoteData.value) {
        return
      }

      currentNoteData.value.is_secret = isSecret
      currentNoteData.value.is_public = isPublic

      if (isSecret) {
        ElMessage.info('笔记已加入保密柜')
      }
    } catch (e) {
      // 组件卸载时，静默处理错误
    }
  }

  // ==================== 监听器 ====================
  // 监听标题变化，用于标记未保存状态和同步解密标题
  watch(() => currentNoteData.value.title, (newTitle, oldTitle) => {
    if (viewMode.value !== 'edit' || !currentNoteId.value) return

    if (currentNoteData.value.is_secret) {
      decryptedTitle.value = newTitle
    }

    if (newTitle !== oldTitle && originalTitle !== '' && newTitle !== originalTitle) {
      hasUnsavedChanges.value = true
    }
  })

  // 监听保险柜解锁状态：当 DEK 恢复或验证成功时，自动解密标题
  watch(() => isKeyValid.value, async (valid) => {
    if (valid && currentNoteData.value.is_secret && currentNoteData.value.title) {
      console.log('[KnowledgeList] isKeyValid became true, attempting to decrypt title')
      await decryptNoteTitle()
    } else if (!valid && currentNoteData.value.is_secret) {
      console.log('[KnowledgeList] isKeyValid became false, clearing decrypted title')
      decryptedTitle.value = ''
    }
  })

  // 监听 dek.value 变化
  watch(() => dek.value, async (newDek) => {
    if (newDek && currentNoteData.value.is_secret && currentNoteData.value.title) {
      console.log('[KnowledgeList] dek.value updated, attempting to decrypt title')
      await decryptNoteTitle()
    } else if (!newDek && currentNoteData.value.is_secret && !vaultStore.dek) {
      console.log('[KnowledgeList] dek.value lost and vaultStore.dek unavailable, clearing title')
      decryptedTitle.value = ''
    }
  })

  // 监听 vaultStore.dek 变化
  watch(() => vaultStore.dek, async (newVaultDek) => {
    if (newVaultDek && currentNoteData.value.is_secret && currentNoteData.value.title) {
      console.log('[KnowledgeList] vaultStore.dek available, attempting to decrypt title')
      await decryptNoteTitle()
    } else if (!newVaultDek && currentNoteData.value.is_secret) {
      console.log('[KnowledgeList] vaultStore.dek cleared, clearing decrypted title')
      decryptedTitle.value = ''
    }
  })

  // 当笔记加载完成后，记录原始标题
  watch(() => currentNoteId.value, () => {
    nextTick(() => {
      originalTitle = currentNoteData.value.title || ''
    })
  })

  // 监听当前模块变化，从保密柜切换时清空预览区
  watch(() => sidebarStore.activeModule, (newModule, previousModule) => {
    if (previousModule === 'vault' && newModule !== 'vault') {
      console.log('[KnowledgeList] Switched from vault, clearing preview area')
      currentNoteId.value = null
      currentNoteData.value = { id: null, title: '', content: '', toc: [] }
      decryptedTitle.value = ''
      hasUnsavedChanges.value = false
      viewMode.value = 'read'
      ElMessage.info('已切换模块，预览已清空')
    }
  })

  // ==================== 生命周期 ====================
  onMounted(async () => {
    await vaultStore.checkAndInitVault()

    window.addEventListener('beforeunload', handleBeforeUnload)
    window.addEventListener('note-secret-toggled', handleNoteSecretToggled)

    // 监听笔记移入保密柜
    window.addEventListener('note-moved-to-vault', async (event) => {
      const { noteId } = event.detail
      if (currentNoteId.value === noteId) {
        currentNoteId.value = null
        currentNoteData.value = { id: null, title: '', content: '', toc: [] }
        ElMessage.warning('笔记已移入保密柜，预览已清空')
      }
    })

    // 监听笔记从保密柜移出
    window.addEventListener('note-moved-from-vault', async (event) => {
      const { noteId } = event.detail
      if (currentNoteId.value === noteId) {
        try {
          await fetchNoteDetail(noteId)
          ElMessage.success('笔记已从保密柜移出')
        } catch (e) {
          ElMessage.error('重新加载笔记失败')
        }
      }
    })

    // 监听笔记移入回收站
    window.addEventListener('note-moved-to-trash', (event) => {
      const { noteId } = event.detail
      if (currentNoteId.value === noteId) {
        currentNoteId.value = null
        currentNoteData.value = { id: null, title: '', content: '', toc: [] }
        ElMessage.info('笔记已移入回收站')
      }
    })

    // 监听文件夹变更
    window.addEventListener('note-folder-changed', async (event) => {
      const { noteId, oldFolderId, newFolderId } = event.detail
      if (currentNoteId.value === noteId) {
        if (sidebarStore.secondaryView === 'notes' && sidebarStore.currentFolderId === oldFolderId) {
          currentNoteId.value = null
          currentNoteData.value = { id: null, title: '', content: '', toc: [] }
          ElMessage.info('笔记已移动到其他文件夹')
        } else {
          try {
            await fetchNoteDetail(noteId)
          } catch (e) {
          }
        }
      }
    })

    // 监听笔记重命名
    window.addEventListener('note-renamed', (event) => {
      const { noteId, newTitle } = event.detail
      if (currentNoteId.value === noteId) {
        currentNoteData.value.title = newTitle
      }
    })

    // 监听搜索结果点击
    window.addEventListener('search-result-clicked', async (event) => {
      const { noteId, highlightKeyword } = event.detail
      try {
        await handleNoteSelect(noteId)
        if (highlightKeyword) {
          window.dispatchEvent(new CustomEvent('highlight-search-text', {
            detail: { keyword: highlightKeyword }
          }))
        }
      } catch (e) {
        ElMessage.error('加载笔记失败')
      }
    })

    // 全局监听 vault-verification-success 事件
    const handleVaultVerificationSuccess = (event) => {
      try {
        const { dek: dekFromEvent, expireTime } = event.detail || {}
        if (dekFromEvent && expireTime) {
          vaultStore.setDEK(dekFromEvent, expireTime)
        }
      } catch (e) {
      }
    }
    window.addEventListener('vault-verification-success', handleVaultVerificationSuccess)
    window.__vaultVerificationHandler = handleVaultVerificationSuccess

    // 监听保密柜解锁请求
    const handleVaultUnlockDialog = (event) => {
      const { fromTrash, noteId } = event.detail || {}
      console.log('[KnowledgeList] Received vault unlock dialog request:', { fromTrash, noteId })
      sidebarStore.vaultVerifyDialogVisible = true
    }
    window.addEventListener('open-vault-unlock-dialog', handleVaultUnlockDialog)
    window.__vaultUnlockDialogHandler = handleVaultUnlockDialog

    // 尝试从 Redis 恢复加密密钥
    const keyRecovered = await tryRecoverKeyFromSession()

    // 从 URL 恢复状态
    const { noteId } = await sidebarStore.initFromUrl()

    const needsModuleData =
      sidebarStore.activeModule !== 'my-space' ||
      (sidebarStore.activeModule === 'my-space' && sidebarStore.secondaryView === 'folders')

    if (needsModuleData) {
      await sidebarStore.loadModuleData()
    }

    if (noteId) {
      isLoadingNote.value = true
      currentNoteId.value = noteId
      await fetchNoteDetail(noteId)
      viewMode.value = 'read'

      if (currentNoteData.value.is_secret && isKeyValid.value) {
        await decryptNoteTitle()
      }

      isLoadingNote.value = false
    }
  })

  onUnmounted(() => {
    window.removeEventListener('beforeunload', handleBeforeUnload)
    window.removeEventListener('note-secret-toggled', handleNoteSecretToggled)
    if (window.__vaultVerificationHandler) {
      window.removeEventListener('vault-verification-success', window.__vaultVerificationHandler)
      delete window.__vaultVerificationHandler
    }
    if (window.__vaultUnlockDialogHandler) {
      window.removeEventListener('open-vault-unlock-dialog', window.__vaultUnlockDialogHandler)
      delete window.__vaultUnlockDialogHandler
    }
  })

  // ==================== 返回 ====================
  return {
    // 状态
    currentNoteId,
    viewMode,
    isSaving,
    hasUnsavedChanges,
    isLoadingNote,
    noteEditorRef,
    decryptedTitle,
    currentNoteData,

    // 计算属性
    showBreadcrumb,
    isDarkMode,
    displayTitle,

    // Stores
    sidebarStore,
    vaultStore,

    // 笔记操作
    handleNoteSelect,
    handleCreateNote,
    handleEditorChange,
    handleSwitchToReadMode,
    handleSave,
    handleDelete,
    handleTogglePublic,
    handleCopyPublicLink,

    // 导航操作
    handleUserProfile,
    handleBreadcrumbNavigate,
    handleFolderSwitch,

    // 保密柜操作
    handleVaultVerified,
    handleVaultCancel,
    handleGoToSettings,
    handleVaultSetupCancel,

    // 工具函数
    formatDate
  }
}
