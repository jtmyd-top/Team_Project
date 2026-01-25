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
                <span class="info-item title">{{ currentNoteData.title || '无标题' }}</span>
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
              <!-- 模式切换 -->
              <div class="mode-switch">
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

              <!-- 公开分享按钮 -->
              <button
                class="toolbar-btn"
                @click="handleTogglePublic"
                :title="currentNoteData.is_public ? '设为私密' : '公开分享'"
              >
                <i :class="currentNoteData.is_public ? 'fas fa-globe' : 'fas fa-lock'"></i>
              </button>

              <!-- 复制公开链接按钮 -->
              <button
                v-if="currentNoteData.is_public"
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
            <div v-show="!isLoadingNote && viewMode === 'read'" class="viewer-wrapper">

              <NoteShadowViewer
                :content="currentNoteData.content"
                :toc="currentNoteData.toc"
                :is-dark="isDarkMode"
              />
            </div>

            <!-- 编辑模式 -->
            <div v-show="!isLoadingNote && viewMode === 'edit'" class="editor-wrapper">
              <NoteEditor
                :key="currentNoteId"
                ref="noteEditorRef"
                v-model="currentNoteData"
                :is-light-theme="!isDarkMode"
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

// 状态
const currentNoteId = ref(null)
const viewMode = ref('read') // 'read' | 'edit'
const isSaving = ref(false)
const hasUnsavedChanges = ref(false)
const isLoadingNote = ref(false) // 笔记加载中标志，用于显示骨架屏
const noteEditorRef = ref(null)

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
      public_url: data.public_url || ''
    }
    
    hasUnsavedChanges.value = false
  } catch (e) {
    console.error('获取笔记详情失败:', e)
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
    console.error('创建笔记失败:', e)
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
    console.log('忽略空内容更新，保持现有数据')
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

    // 从编辑器实例获取最新内容
    let contentToSave = currentNoteData.value.content
    if (noteEditorRef.value && noteEditorRef.value.getContent) {
      contentToSave = noteEditorRef.value.getContent()
    }

    const response = await fetch(`/api/notes/${currentNoteId.value}/`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({
        title: currentNoteData.value.title,
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

    // 更新列表中的标题
    const note = sidebarStore.currentNotes.find(n => n.id === currentNoteId.value)
    if (note) {
      note.title = currentNoteData.value.title
    }

    // 更新 TOC (如果后端返回了新的 TOC)
    if (data.toc) {
      currentNoteData.value.toc = data.toc
    }

    // 保存成功后切换到阅读模式
    viewMode.value = 'read'
  } catch (e) {
    console.error('保存失败:', e)
    ElMessage.error('保存失败，请重试')
  } finally {
    isSaving.value = false
  }
}

// 删除笔记
async function handleDelete() {
  if (!currentNoteId.value) return
  
  try {
    await ElMessageBox.confirm('确定要删除这篇笔记吗？它将被移动到回收站。', '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
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
      console.error('删除失败:', e)
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
    console.error(`${actionText}失败:`, e)
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
    console.error('复制失败:', e)
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

// 监听标题变化，用于标记未保存状态
watch(() => currentNoteData.value.title, (newTitle, oldTitle) => {
  // 只在编辑模式下且有当前笔记时检测
  if (viewMode.value !== 'edit' || !currentNoteId.value) return

  // 如果标题确实被用户修改了（与原始标题不同）
  if (newTitle !== oldTitle && originalTitle !== '' && newTitle !== originalTitle) {
    hasUnsavedChanges.value = true
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
  // 添加页面离开前的防呆提醒
  window.addEventListener('beforeunload', handleBeforeUnload)

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
    isLoadingNote.value = false
  }
  }
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
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

.toolbar-btn.danger:hover {
  color: #f56c6c;
  background: rgba(245, 108, 108, 0.1);
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
 