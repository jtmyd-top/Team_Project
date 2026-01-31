<template>
  <div class="knowledge-layout">
    <!-- 一级侧边栏 -->
    <PrimarySidebar @user-profile="handleUserProfile" />

    <!-- 二级侧边栏 -->
    <SecondaryPanel
      :active-note-id="currentNoteId"
      @note-select="handleNoteSelect"
      @note-create="handleCreateNote"
    />

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 面包屑导航 -->
      <Breadcrumb
        v-if="showBreadcrumb"
        :items="sidebarStore.breadcrumb"
        @navigate="handleBreadcrumbNavigate"
        @switch-folder="handleFolderSwitch"
      />

      <!-- 编辑器/阅览器容器 -->
      <div class="editor-container" :class="{ 'with-breadcrumb': showBreadcrumb }">
        <!-- 保密柜未验证时显示空白 -->
        <div v-if="sidebarStore.activeModule === 'vault' && !sidebarStore.vaultStatus.isVerified" class="vault-empty-state">
          <!-- 空白状态，等待验证 -->
        </div>

        <!-- 正常笔记显示 -->
        <div v-else-if="currentNoteId" class="note-workspace">
          <!-- 顶部工具栏 -->
          <div class="workspace-toolbar">
            <div class="toolbar-left">
              <!-- 展开侧边栏按钮 -->
              <button 
                v-if="sidebarStore.isCollapsed"
                class="icon-btn expand-btn" 
                @click="sidebarStore.toggleCollapse()"
                title="展开侧边栏"
              >
                <i class="fas fa-align-justify"></i>
              </button>

              <span class="note-info" v-if="currentNoteData.updated_at">
                <span class="info-item title">{{ displayTitle }}</span>
                <span v-if="hasUnsavedChanges && viewMode === 'edit'" class="unsaved-indicator" title="有未保存的更改">
                  <i class="fas fa-circle"></i> 未保存
                </span>
                <span class="separator">-</span>
                <span class="info-item author">{{ currentNoteData.author?.username || '未知作者' }}</span>
                <span class="separator">-</span>
                <span class="info-item time">最后修改: {{ formatDate(currentNoteData.updated_at) }}</span>
              </span>
            </div>
            <div class="toolbar-right">
              <!-- 模式切换 - 回收站中隐藏编辑按钮 -->
              <div v-if="!currentNoteData.is_trashed" class="mode-switch">
                <button
                  class="toolbar-btn"
                  :class="{ active: viewMode === 'read' }"
                  @click="handleSwitchToReadMode"
                  title="阅读模式"
                >
                  <i class="fas fa-book-open"></i>
                </button>
                <button
                  class="toolbar-btn"
                  :class="{ active: viewMode === 'edit' }"
                  @click="viewMode = 'edit'"
                  title="编辑模式"
                >
                  <i class="fas fa-pen"></i>
                </button>
              </div>

              <div class="divider"></div>

              <!-- 操作按钮 -->
              <button
                v-if="viewMode === 'edit'"
                class="toolbar-btn primary"
                @click="handleSave"
                :disabled="isSaving"
              >
                <i class="fas fa-save"></i> {{ isSaving ? '保存中...' : '保存' }}
              </button>

              <!-- 公开分享按钮 - 回收站中隐藏 -->
              <button
                v-if="!currentNoteData.is_trashed"
                class="toolbar-btn"
                @click="handleTogglePublic"
                :title="currentNoteData.is_public ? '设为私密' : '公开分享'"
              >
                <i :class="currentNoteData.is_public ? 'fas fa-globe' : 'fas fa-lock'"></i>
              </button>

              <!-- 复制公开链接按钮 - 回收站中隐藏 -->
              <button
                v-if="currentNoteData.is_public && !currentNoteData.is_trashed"
                class="toolbar-btn"
                @click="handleCopyPublicLink"
                title="复制公开链接"
              >
                <i class="fas fa-link"></i>
              </button>

              <button class="toolbar-btn danger" @click="handleDelete" title="删除笔记">
                <i class="fas fa-trash-alt"></i>
              </button>
            </div>
          </div>

          <!-- 内容区域 -->
          <div class="workspace-content">
            <!-- 加载状态指示器 -->
            <div v-if="isLoadingNote" class="loading-overlay">
              <div class="loading-spinner">
                <i class="fas fa-spinner fa-spin"></i>
                <span>加载笔记中...</span>
              </div>
            </div>

            <!-- 阅读模式 -->
            <div v-if="!isLoadingNote && viewMode === 'read'" class="viewer-wrapper">

              <NoteShadowViewer
                :content="currentNoteData.content"
                :toc="currentNoteData.toc"
                :is-dark="isDarkMode"
                :is-secret="currentNoteData.is_secret"
                :is-trashed="currentNoteData.is_trashed"
                :note-id="currentNoteData.id"
              />
            </div>

            <!-- 编辑模式 -->
            <div v-if="!isLoadingNote && viewMode === 'edit'" class="editor-wrapper">
              <NoteEditor
                :key="currentNoteId"
                ref="noteEditorRef"
                v-model="currentNoteData"
                :is-light-theme="!isDarkMode"
                :is-secret="currentNoteData.is_secret"
                @change="handleEditorChange"
                @save="handleSave"
              />
            </div>
          </div>
        </div>

        <!-- 空状态（非保密柜或保密柜已验证时显示） -->
        <div v-else-if="sidebarStore.activeModule !== 'vault' || sidebarStore.vaultStatus.isVerified" class="empty-editor-state">
          <i class="fas fa-book-open"></i>
          <p>选择或创建一篇笔记开始写作</p>
          <button class="primary-btn" @click="handleCreateNote">
            <i class="fas fa-plus"></i> 新建笔记
          </button>
        </div>
      </div>
    </main>

    <!-- 拖拽放置浮动面板 -->
    <DragDropOverlay />

    <!-- 保密柜验证对话框 -->
    <VaultVerifyDialog
      v-model="sidebarStore.vaultVerifyDialogVisible"
      :two-fa-method="sidebarStore.vaultStatus.twoFaMethod"
      @verified="handleVaultVerified"
      @cancel="handleVaultCancel"
    />

    <!-- 保密柜设置提示对话框 -->
    <VaultSetupDialog
      v-model="sidebarStore.vaultSetup2faDialogVisible"
      @go-to-settings="handleGoToSettings"
      @cancel="handleVaultSetupCancel"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useSidebarStore } from '@/stores/sidebar'
import { useVaultStore } from '@/stores/vault'
import { useVaultEncryption } from '@/composables/useVaultEncryption'
import { useClientCrypto } from '@/composables/useClientCrypto'
import { ElMessage, ElMessageBox } from 'element-plus'
import PrimarySidebar from '@/components/layout/PrimarySidebar.vue'
import SecondaryPanel from '@/components/layout/SecondaryPanel.vue'
import Breadcrumb from '@/components/common/Breadcrumb.vue'
import NoteEditor from '@/components/knowledge/NoteEditor.vue'
import NoteShadowViewer from '@/components/knowledge/NoteShadowViewer.vue'
import DragDropOverlay from '@/components/common/DragDropOverlay.vue'
import VaultVerifyDialog from '@/components/common/VaultVerifyDialog.vue'
import VaultSetupDialog from '@/components/common/VaultSetupDialog.vue'

// Store
const sidebarStore = useSidebarStore()
const vaultStore = useVaultStore()

// Vault encryption
const { isKeyValid, dek, keyExpireTime, tryRecoverKeyFromSession } = useVaultEncryption()
const { decryptContent, encryptContent, looksLikeEncrypted } = useClientCrypto()

// 状态
const currentNoteId = ref(null)
const viewMode = ref('read') // 'read' | 'edit'
const isSaving = ref(false)
const hasUnsavedChanges = ref(false)
const isLoadingNote = ref(false) // 笔记加载中标志，用于显示骨架屏
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
  is_trashed: false,  // 【新增】回收站状态
  public_url: ''
})

// 计算属性
const showBreadcrumb = computed(() => {
  return sidebarStore.activeModule === 'my-space' && sidebarStore.secondaryView === 'notes' && sidebarStore.currentFolderId
})

const isDarkMode = computed(() => {
  // 这里可以从主题 store 获取，暂时根据系统偏好
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
})

// 计算属性：显示的标题（已解密或原标题）
const displayTitle = computed(() => {
  if (!currentNoteData.value.is_secret) {
    // 普通笔记，直接返回标题
    return currentNoteData.value.title || '无标题'
  }

  // 加密笔记，返回解密后的标题
  if (decryptedTitle.value) {
    return decryptedTitle.value
  }

  // 如果还没解密，返回原标题（可能是密文）
  return currentNoteData.value.title || '无标题'
})

// 方法
function handleUserProfile() {
  window.location.href = '/settings/'
}

// 保密柜验证成功
async function handleVaultVerified(data) {
  sidebarStore.vaultStatus.isVerified = true
  sidebarStore.vaultStatus.remainingSeconds = data.remainingSeconds
  await sidebarStore.onVaultVerified()
}

// 保密柜验证取消
function handleVaultCancel() {
  // 切换回全部笔记
  sidebarStore.setActiveModule('all-notes')
}

// 前往设置页面
function handleGoToSettings() {
  window.location.href = '/settings/?tab=security'
}

// 保密柜设置提示取消
function handleVaultSetupCancel() {
  sidebarStore.vaultSetup2faDialogVisible = false
  // 切换回全部笔记
  sidebarStore.setActiveModule('all-notes')
}

// 格式化日期
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

// 解密笔记标题
async function decryptNoteTitle() {
  // 如果不是加密笔记，不需要解密
  if (!currentNoteData.value.is_secret) {
    decryptedTitle.value = ''
    return
  }

  // 如果没有标题，不需要解密
  if (!currentNoteData.value.title) {
    decryptedTitle.value = ''
    return
  }

  // 如果没有有效的 DEK，不能解密
  if (!isKeyValid.value || !dek.value) {
    decryptedTitle.value = ''
    return
  }

  try {
    // 尝试解密标题
    const plainTitle = decryptContent(currentNoteData.value.title, dek.value)
    decryptedTitle.value = plainTitle
  } catch (e) {
    // 标题可能是明文（旧笔记），保留原值
    decryptedTitle.value = ''  // 让 displayTitle computed 显示原标题
  }
}

// 选中笔记
async function handleNoteSelect(noteId) {
  // 如果有未保存的更改，提示保存
  if (hasUnsavedChanges.value) {
    try {
      await ElMessageBox.confirm('当前笔记有未保存的更改，是否保存？', '提示', {
        confirmButtonText: '保存',
        cancelButtonText: '放弃',
        type: 'warning'
      })
      await handleSave()
    } catch (e) {
      // 用户选择放弃，或者取消
      if (e !== 'cancel') {
        hasUnsavedChanges.value = false
      } else {
        return // 取消切换
      }
    }
  }

  // 开始加载新笔记（不清空 currentNoteId，避免闪屏）
  isLoadingNote.value = true

  // 加载笔记数据
  await fetchNoteDetail(noteId)

  // 数据加载完成后，再设置笔记 ID 和更新 store
  currentNoteId.value = noteId
  sidebarStore.setCurrentNoteId(noteId)

  // 切换笔记时，默认进入阅读模式，除非是新创建的空笔记
  if (!currentNoteData.value.content && !currentNoteData.value.title) {
    viewMode.value = 'edit'
  } else {
    viewMode.value = 'read'
  }

  // 如果是加密笔记且已解锁，解密标题
  if (currentNoteData.value.is_secret && isKeyValid.value) {
    await decryptNoteTitle()
  } else {
    decryptedTitle.value = ''
  }

  isLoadingNote.value = false
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
      toc: data.toc || [], // 确保有 toc 字段
      updated_at: data.updated_at,
      author: data.author,
      is_public: data.is_public || false,
      is_secret: data.is_secret || false,
      is_trashed: data.is_trashed || false,  // 【新增】保存回收站状态
      public_url: data.public_url || ''
    }

    hasUnsavedChanges.value = false
  } catch (e) {
    ElMessage.error('无法加载笔记内容')
  }
}

// 创建笔记
async function handleCreateNote(folderId = null) {
  // 如果有未保存的更改，提示保存
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
        // 用户点击关闭按钮，取消新建操作
        return
      }
      // 用户选择放弃，继续新建
      hasUnsavedChanges.value = false
    }
  }

  try {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value

    // 使用当前文件夹 ID（如果没有传入）
    const targetFolderId = folderId ?? sidebarStore.currentFolderId

    // 检查是否在保险柜视图中
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
        is_secret: isVaultModule  // 在保险柜中创建时自动标记为保密
      })
    })

    const data = await response.json()

    // 后端返回 { id, title } 或 { error }
    if (data.error) {
      throw new Error(data.error)
    }

    const noteId = data.id || data.note_id

    if (noteId) {
      // 根据当前模块刷新数据
      switch (sidebarStore.activeModule) {
        case 'all-notes':
          // 全部笔记：重新加载全部笔记列表
          await sidebarStore.loadAllNotes()
          break
        case 'my-space':
          if (sidebarStore.secondaryView === 'notes') {
            // 在笔记列表视图：重新加载当前文件夹/收件箱的笔记
            if (sidebarStore.currentFolderId) {
              await sidebarStore.enterFolder(sidebarStore.currentFolderId)
            } else {
              await sidebarStore.enterInbox()
            }
          } else {
            // 在文件夹列表视图：加载文件夹树（更新收件箱计数）
            await sidebarStore.loadFolders()
          }
          break
        default:
          // 其他模块（收藏夹、回收站等）：重新加载模块数据
          await sidebarStore.loadModuleData()
      }

      // 选中新创建的笔记并进入编辑模式
      // 先清空当前笔记 ID，确保编辑器不会在数据加载前渲染
      currentNoteId.value = null

      // 加载新笔记数据
      await fetchNoteDetail(noteId)

      // 在 fetchNoteDetail 后，检查是否在保险柜中创建，如果是则设置 is_secret
      if (isVaultModule) {
        currentNoteData.value.is_secret = true
      }

      // 数据加载完成后，再设置笔记 ID
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
  // 只有在编辑模式下才标记有未保存的更改
  // 防止组件销毁时触发的事件导致状态错误
  if (viewMode.value !== 'edit') return

  // 忽略空内容更新，防止编辑器初始化时的事件覆盖已有内容
  // 但如果原本就是空内容（新建笔记），则允许标记为已修改
  if (!content && currentNoteData.value.content && currentNoteData.value.content.length > 0) {
    return
  }

  hasUnsavedChanges.value = true
  // 同步编辑器内容到数据模型
  if (content !== undefined) {
    currentNoteData.value.content = content
  }
}

// 切换到阅读模式（带防呆检查）
async function handleSwitchToReadMode() {
  // 如果已经是阅读模式，直接返回
  if (viewMode.value === 'read') return

  // 如果有未保存的更改，提示保存
  if (hasUnsavedChanges.value) {
    try {
      await ElMessageBox.confirm('当前笔记有未保存的更改，是否保存？', '提示', {
        confirmButtonText: '保存',
        cancelButtonText: '放弃',
        distinguishCancelAndClose: true,
        type: 'warning'
      })
      await handleSave()
      // handleSave 成功后会自动切换到阅读模式
    } catch (action) {
      if (action === 'close') {
        // 用户点击关闭按钮，取消切换
        return
      }
      // 用户选择放弃，直接切换到阅读模式
      hasUnsavedChanges.value = false
      viewMode.value = 'read'
    }
  } else {
    // 没有未保存的更改，直接切换
    viewMode.value = 'read'
  }
}

// 保存笔记
async function handleSave() {
  if (!currentNoteId.value) return

  isSaving.value = true
  try {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value

    // 【关键】从编辑器实例获取最新的明文标题和内容
    // 这是用户编辑后的明文内容，而不是数据库中已加密的密文
    let contentToSave = ''
    let titleToSave = ''
    let plainTextTitle = ''  // 【新增】保存明文标题，用于后续列表更新

    // 【修复】优先从编辑器获取标题（必须是编辑器中的明文，避免 double encryption）
    if (noteEditorRef.value && noteEditorRef.value.getCurrentTitle) {
      titleToSave = noteEditorRef.value.getCurrentTitle()
      plainTextTitle = titleToSave  // 【新增】保存明文标题
    } else {
      // 备选：使用当前笔记数据中的标题
      titleToSave = currentNoteData.value.title
      plainTextTitle = titleToSave  // 【新增】保存明文标题
    }

    // 优先从编辑器获取内容（必须是编辑器中的明文）
    if (noteEditorRef.value && noteEditorRef.value.getContent) {
      contentToSave = noteEditorRef.value.getContent()
    } else {
      // 备选：使用状态中的内容
      contentToSave = currentNoteData.value.content
    }

    // 如果是加密笔记，在前端进行加密
    if (currentNoteData.value.is_secret) {
      try {
        // 【关键修复】检查 isKeyValid 而不仅仅是 dek.value
        // 因为 keyExpireTime 可能已过期，即使 dek.value 还有值

        if (!isKeyValid.value) {
          // 尝试从 session 恢复 DEK
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

        // 【重要】确认 contentToSave 是编辑器中的明文，而不是数据库中的密文
        // 判断方法：编辑器内容长度通常与原明文长度相同，如果与原密文长度相同则可能是错误

        // 前端加密：使用 crypto-js 在浏览器中加密解密后的内容

        // 【重要】加密标题 - 检查是否已经是加密数据
        if (titleToSave) {
          try {
            // 【防护】检查标题是否已经看起来像加密数据
            if (looksLikeEncrypted(titleToSave)) {
              // Skip
            } else {
              titleToSave = encryptContent(titleToSave, dek.value)
            }
          } catch (e) {
            // Error encrypting title
          }
        }

        // 【重要】加密内容 - 检查是否已经是加密数据，防止 double encryption
        if (looksLikeEncrypted(contentToSave)) {
          // Skip
        } else {
          contentToSave = encryptContent(contentToSave, dek.value)
        }
      } catch (e) {
        ElMessage.error('加密失败: ' + e.message)
        isSaving.value = false
        return
      }
    }

    // 发送笔记到后端
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

    // 更新最后修改时间
    if (data.updated_at) {
      currentNoteData.value.updated_at = data.updated_at
    }

    // 【关键】更新列表中的标题
    const note = sidebarStore.currentNotes.find(n => n.id === currentNoteId.value)
    if (note) {
      // 【修复】使用保存前的明文标题更新列表，而不是已加密的 currentNoteData.value.title
      // plainTextTitle 是从编辑器获取的明文，不会被加密污染
      note.title = plainTextTitle
    }

    // 【新增】同时更新解密标题状态，这样工具栏也会显示最新的标题
    decryptedTitle.value = plainTextTitle

    // 更新 TOC (如果后端返回了新的 TOC)
    if (data.toc) {
      currentNoteData.value.toc = data.toc
    }

    // 【新增】触发事件：笔记标题已更新（用于其他组件同步）
    window.dispatchEvent(new CustomEvent('note-title-updated', {
      detail: {
        noteId: currentNoteId.value,
        newTitle: plainTextTitle
      }
    }))

    // 保存成功后切换到阅读模式
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
    // 如果设为公开，更新公开链接
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
      // 回退方案：使用传统方法
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

function handleBreadcrumbNavigate(folderId) {
  // Breadcrumb 组件已处理导航
}

function handleFolderSwitch(folderId) {
  // Breadcrumb 组件已处理切换
}

// 自动保存功能已在 handleEditorChange 中通过 NoteEditor 的事件处理
// 不再使用 watch 监听 currentNoteData，避免在数据加载时误触发 hasUnsavedChanges

// 原始标题，用于检测标题是否被修改
let originalTitle = ''

// 监听标题变化，用于标记未保存状态和同步解密标题
watch(() => currentNoteData.value.title, (newTitle, oldTitle) => {
  // 只在编辑模式下且有当前笔记时检测
  if (viewMode.value !== 'edit' || !currentNoteId.value) return

  // 如果是保密柜笔记，编辑器中显示的是明文标题
  // 需要同时更新 decryptedTitle 以确保工具栏标题即时更新
  if (currentNoteData.value.is_secret) {
    decryptedTitle.value = newTitle
  }

  // 如果标题确实被用户修改了（与原始标题不同）
  if (newTitle !== oldTitle && originalTitle !== '' && newTitle !== originalTitle) {
    hasUnsavedChanges.value = true
  }
})

// 监听保险柜解锁状态：当 DEK 恢复或验证成功时，自动解密标题
watch(() => isKeyValid.value, async (valid) => {
  if (valid && currentNoteData.value.is_secret && currentNoteData.value.title && !decryptedTitle.value) {
    // 密钥刚刚变有效，解密当前笔记的标题
    await decryptNoteTitle()
  } else if (!valid && currentNoteData.value.is_secret) {
    // 密钥失效，清除解密的标题
    decryptedTitle.value = ''
  }
})

// 当笔记加载完成后，记录原始标题
watch(() => currentNoteId.value, () => {
  // 使用 nextTick 确保数据已更新
  nextTick(() => {
    originalTitle = currentNoteData.value.title || ''
  })
})

// 初始化
onMounted(async () => {
  // 懒加载初始化保密柜（如果未初始化的话）
  await vaultStore.checkAndInitVault()

  // 添加页面离开前的防呆提醒
  window.addEventListener('beforeunload', handleBeforeUnload)

  // 监听笔记保密状态变化事件
  window.addEventListener('note-secret-toggled', handleNoteSecretToggled)

  // 【新增】监听笔记权限变更事件 - 移入保密柜
  window.addEventListener('note-moved-to-vault', async (event) => {
    const { noteId } = event.detail
    // P0: 如果当前笔记被移入保密柜，立即清空内容（安全风险）
    if (currentNoteId.value === noteId) {
      currentNoteId.value = null
      currentNoteData.value = { id: null, title: '', content: '', toc: [] }
      ElMessage.warning('笔记已移入保密柜，预览已清空')
    }
  })

  // 【新增】监听笔记从保密柜移出事件
  window.addEventListener('note-moved-from-vault', async (event) => {
    const { noteId } = event.detail
    // P0: 如果当前笔记从保密柜移出，重新加载并解密
    if (currentNoteId.value === noteId) {
      try {
        await fetchNoteDetail(noteId)
        ElMessage.success('笔记已从保密柜移出')
      } catch (e) {
        ElMessage.error('重新加载笔记失败')
      }
    }
  })

  // 【新增】监听笔记移入回收站事件
  window.addEventListener('note-moved-to-trash', (event) => {
    const { noteId } = event.detail
    // P1: 如果当前笔记被移入回收站，立即清空内容
    if (currentNoteId.value === noteId) {
      currentNoteId.value = null
      currentNoteData.value = { id: null, title: '', content: '', toc: [] }
      ElMessage.info('笔记已移入回收站')
    }
  })

  // 【新增】监听文件夹变更事件
  window.addEventListener('note-folder-changed', async (event) => {
    const { noteId, oldFolderId, newFolderId } = event.detail
    // P1: 如果当前笔记被移动到其他文件夹
    if (currentNoteId.value === noteId) {
      // 如果当前只显示原文件夹内容，需要清空预览并更新面包屑
      if (sidebarStore.secondaryView === 'notes' && sidebarStore.currentFolderId === oldFolderId) {
        // 当前显示的是原文件夹内容，但笔记已被移出
        currentNoteId.value = null
        currentNoteData.value = { id: null, title: '', content: '', toc: [] }
        ElMessage.info('笔记已移动到其他文件夹')
      } else {
        // 重新加载笔记以更新其文件夹信息
        try {
          await fetchNoteDetail(noteId)
        } catch (e) {
        }
      }
    }
  })

  // 【新增】监听笔记重命名事件
  window.addEventListener('note-renamed', (event) => {
    const { noteId, newTitle } = event.detail
    // P2: 更新预览区的大标题
    if (currentNoteId.value === noteId) {
      currentNoteData.value.title = newTitle
    }
  })

  // 【新增】监听搜索结果点击事件
  window.addEventListener('search-result-clicked', async (event) => {
    const { noteId, highlightKeyword } = event.detail
    // P3: 加载笔记并高亮搜索词
    try {
      await handleNoteSelect(noteId)
      // 触发高亮显示
      if (highlightKeyword) {
        window.dispatchEvent(new CustomEvent('highlight-search-text', {
          detail: { keyword: highlightKeyword }
        }))
      }
    } catch (e) {
      ElMessage.error('加载笔记失败')
    }
  })

  // 【新增】全局监听 vault-verification-success 事件
  // 确保任何时候 DEK 都被正确保存到 vaultStore
  const handleVaultVerificationSuccess = (event) => {
    try {
      const { dek: dekFromEvent, expireTime } = event.detail || {}
      if (dekFromEvent && expireTime) {
        vaultStore.setDEK(dekFromEvent, expireTime)
      }
    } catch (e) {
      // Error handling vault verification success
    }
  }
  window.addEventListener('vault-verification-success', handleVaultVerificationSuccess)
  // 保存句柄以便卸载时移除
  window.__vaultVerificationHandler = handleVaultVerificationSuccess

  // 【新增】监听来自回收站的保密柜解锁请求
  const handleVaultUnlockDialog = (event) => {
    const { fromTrash, noteId } = event.detail || {}
    console.log('[KnowledgeList] Received vault unlock dialog request:', { fromTrash, noteId })
    // 打开保密柜验证对话框
    sidebarStore.vaultVerifyDialogVisible = true
  }
  window.addEventListener('open-vault-unlock-dialog', handleVaultUnlockDialog)
  // 保存句柄以便卸载时移除
  window.__vaultUnlockDialogHandler = handleVaultUnlockDialog

  // 尝试从 Redis 恢复加密密钥（如果用户已验证过）
  const keyRecovered = await tryRecoverKeyFromSession()
  if (keyRecovered) {
  }

  // 从 URL 恢复状态
  // initFromUrl 会在 my-space 的收件箱/文件夹视图时自动加载笔记数据
  const { noteId } = await sidebarStore.initFromUrl()

  // 根据当前状态决定是否需要额外加载数据
  const needsModuleData =
    // 非 my-space 模块需要加载笔记列表
    sidebarStore.activeModule !== 'my-space' ||
    // my-space 的文件夹列表视图需要加载文件夹树
    (sidebarStore.activeModule === 'my-space' && sidebarStore.secondaryView === 'folders')

  if (needsModuleData) {
    await sidebarStore.loadModuleData()
  }

  // 如果 URL 中有笔记 ID，自动选中该笔记
  if (noteId) {
    isLoadingNote.value = true
    currentNoteId.value = noteId
    await fetchNoteDetail(noteId)
    viewMode.value = 'read'

    // 【修复】加载笔记后，如果是加密笔记且密钥已恢复，自动解密标题
    if (currentNoteData.value.is_secret && isKeyValid.value) {
      await decryptNoteTitle()
    }

    isLoadingNote.value = false
  }
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('note-secret-toggled', handleNoteSecretToggled)
  // 移除全局 vault 验证成功监听器
  if (window.__vaultVerificationHandler) {
    window.removeEventListener('vault-verification-success', window.__vaultVerificationHandler)
    delete window.__vaultVerificationHandler
  }
  // 移除保密柜解锁对话框监听器
  if (window.__vaultUnlockDialogHandler) {
    window.removeEventListener('open-vault-unlock-dialog', window.__vaultUnlockDialogHandler)
    delete window.__vaultUnlockDialogHandler
  }
})

// 页面离开前的防呆提醒
function handleBeforeUnload(e) {
  if (hasUnsavedChanges.value && viewMode.value === 'edit') {
    // 标准方式：设置 returnValue 和返回字符串
    const message = '您有未保存的更改，确定要离开吗？'
    e.preventDefault()
    e.returnValue = message
    return message
  }
}

// 处理笔记保密状态变化事件
function handleNoteSecretToggled(event) {
  try {
    // 检查组件是否仍然存在
    if (!event || !event.detail) {
      return
    }

    const { noteId, isSecret, isPublic } = event.detail

    // 安全检查：确保当前笔记 ID 存在
    if (!currentNoteId.value || currentNoteId.value !== noteId) {
      return
    }

    // 安全检查：确保 currentNoteData 存在
    if (!currentNoteData.value) {
      return
    }

    // 更新笔记状态
    currentNoteData.value.is_secret = isSecret
    currentNoteData.value.is_public = isPublic

    // 显示提示信息
    if (isSecret) {
      ElMessage.info('笔记已加入保密柜')
    }
  } catch (e) {
    // 组件卸载时，静默处理错误
  }
}
</script>

<style scoped>
.knowledge-layout {
  display: flex;
  height: calc(100vh - 64px); /* 减去顶部导航栏高度 */
  margin-top: 64px; /* 顶部导航栏高度 */
  width: 100vw;
  overflow: hidden;
  background: var(--bg-primary, #fff);
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg-primary, #fff);
  overflow: hidden; /* 确保主内容区不会出现全局滚动条 */
}

.editor-container {
  flex: 1;
  overflow: hidden; /* 修复：禁止外层滚动，确保工具栏固定 */
  display: flex;
  flex-direction: column;
}

.note-workspace {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0; /* 防止内容撑开 flex 容器 */
}

.workspace-toolbar {
  height: 50px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: var(--bg-primary, #fff);
  flex-shrink: 0;
}

.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.last-modified {
  font-size: 12px;
  color: var(--text-tertiary, #999);
}

.mode-switch {
  display: flex;
  background: var(--bg-secondary, #f5f5f5);
  border-radius: 6px;
  padding: 2px;
}

.toolbar-btn {
  border: none;
  background: transparent;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-secondary, #666);
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  background: var(--hover-bg, rgba(0,0,0,0.05));
  color: var(--text-primary, #333);
}

.toolbar-btn.active {
  background: var(--bg-primary, #fff);
  color: var(--primary-color, #409eff);
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}

.toolbar-btn.primary {
  background: var(--primary-color, #409eff);
  color: white;
}

.toolbar-btn.primary:hover {
  background: var(--primary-color-dark, #337ecc);
}

.toolbar-btn.danger {
  color: #fff;
  background: linear-gradient(135deg, #f56c6c 0%, #e74c3c 100%);
  border: none;
}

.toolbar-btn.danger:hover {
  background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.4);
  transform: translateY(-1px);
}

.divider {
  width: 1px;
  height: 20px;
  background: var(--border-color, #e0e0e0);
  margin: 0 4px;
}

.workspace-content {
  flex: 1 1 0; /* 强制 flex basis 为 0，确保正确计算剩余空间 */
  height: 0; /* 配合 flex: 1 使用，确保在某些浏览器中正确滚动 */
  overflow-y: auto;
  overflow-x: hidden; /* 防止横向抖动 */
  position: relative;
  scroll-behavior: smooth;
  background: var(--bg-primary, #fff);
}

.viewer-wrapper {
  max-width: 900px;
  width: 100%;
  min-width: 0; /* 防止 flex 子元素溢出 */
  box-sizing: border-box;
  margin: 0 auto;
  padding: 30px 40px;
  padding-bottom: 100px; /* 增加底部留白，提升阅读舒适度 */
  overflow-x: hidden; /* 防止内容溢出 */
  /* 阅读模式让内容自然撑开，利用父容器滚动 */
}

.editor-wrapper {
  max-width: 900px;
  width: 100%;
  min-width: 0; /* 防止 flex 子元素溢出 */
  box-sizing: border-box;
  margin: 0 auto;
  padding: 30px 40px;
  height: 100%; /* 编辑模式需要固定高度 */
  overflow-x: hidden; /* 防止内容溢出 */
}

.note-title-display {
  font-size: 2.25em;
  font-weight: 700;
  margin-bottom: 1em;
  color: var(--text-primary, #1a1a1a);
  line-height: 1.3;
}

.empty-editor-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #999);
}

.empty-editor-state i {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-editor-state p {
  margin: 0 0 24px;
  font-size: 16px;
}

.primary-btn {
  padding: 10px 24px;
  border: none;
  background: var(--primary-color, #409eff);
  color: white;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: background 0.2s;
}

.primary-btn:hover {
  background: var(--primary-color-dark, #337ecc);
}

/* 新增样式 */
.icon-btn {
  border: none;
  background: transparent;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-secondary, #666);
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  margin-right: 8px;
}

.icon-btn:hover {
  background: var(--hover-bg, rgba(0,0,0,0.05));
  color: var(--primary-color, #409eff);
}

.note-info {
  display: flex;
  align-items: center;
  font-size: 14px; /* 增大字体 */
  color: var(--text-secondary, #666);
}

.info-item {
  font-weight: 500;
}

.info-item.title {
  color: var(--text-primary, #333);
  font-weight: 600;
  max-width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.unsaved-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 8px;
  padding: 2px 8px;
  background: rgba(245, 108, 108, 0.1);
  color: #f56c6c;
  font-size: 12px;
  font-weight: 500;
  border-radius: 4px;
  animation: pulse-unsaved 2s ease-in-out infinite;
}

.unsaved-indicator i {
  font-size: 6px;
}

@keyframes pulse-unsaved {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.separator {
  margin: 0 8px;
  color: var(--border-color, #e0e0e0);
}

.info-item.time {
  font-size: 12px;
  color: var(--text-tertiary, #999);
}

/* 响应式优化 */
@media (max-width: 1100px) {
  .viewer-wrapper {
    max-width: 100%;
    padding: 20px 24px;
  }

  .editor-wrapper {
    max-width: 100%;
    padding: 20px 24px;
  }
}

/* 小屏幕适配：当二级侧边栏变成浮动时 */
@media (max-width: 900px) {
  .knowledge-layout {
    /* 小屏幕下只需要考虑一级侧边栏的宽度 */
    width: 100vw;
  }

  .main-content {
    /* 确保主内容区域占据除一级侧边栏外的全部宽度 */
    flex: 1;
    min-width: 0;
    width: calc(100vw - 64px);
  }

  .viewer-wrapper {
    padding: 20px 16px;
  }

  .editor-wrapper {
    padding: 20px 16px;
  }
}

@media (max-width: 768px) {
  .viewer-wrapper {
    padding: 16px;
  }

  .editor-wrapper {
    padding: 16px;
  }

  .workspace-toolbar {
    padding: 0 12px;
  }

  .note-info .separator,
  .note-info .info-item.time {
    display: none;
  }

  .info-item.title {
    max-width: 150px;
  }
}

/* 加载状态样式 */
.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(2px);
  z-index: 100;
  animation: fadeIn 0.15s ease-out;
}

.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--text-secondary, #666);
}

.loading-spinner i {
  font-size: 32px;
  color: var(--primary-color, #409eff);
}

.loading-spinner span {
  font-size: 14px;
  font-weight: 500;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* 在 isLoading 状态下，使用 v-show 来保持 DOM，只控制透明度 */
.note-workspace.is-loading .viewer-wrapper,
.note-workspace.is-loading .editor-wrapper {
  opacity: 0.5;
  pointer-events: none; /* 防止用户交互 */
}
</style>
 