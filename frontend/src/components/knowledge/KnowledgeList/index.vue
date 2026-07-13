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
        <NotificationCenter v-if="sidebarStore.activeModule === 'notifications'" />
        <ShareCenter v-else-if="sidebarStore.activeModule === 'shares'" />
        <AssetCenter v-else-if="sidebarStore.activeModule === 'files'" />
        <!-- 保密柜未验证时显示空白 -->
        <div v-else-if="sidebarStore.activeModule === 'vault' && !sidebarStore.vaultStatus.isVerified" class="vault-empty-state">
          <!-- 空白状态，等待验证 -->
        </div>

        <!-- 正常笔记显示 -->
        <div v-else-if="currentNoteId" class="note-workspace">
          <!-- 回收站只读模式 Banner - 仅在回收站中显示 -->
          <div v-if="currentNoteData.is_trashed && sidebarStore.activeModule === 'trash'" class="trash-readonly-banner-wrapper">
            <div class="trash-readonly-banner">
              <i class="fas fa-info-circle"></i>
              <div class="banner-content">
                <span class="banner-title">此笔记位于回收站中</span>
                <span class="banner-message">只能查看，无法编辑。恢复后可正常编辑。</span>
              </div>
            </div>
          </div>

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

              <!-- 公开分享按钮 - 回收站和保密笔记中隐藏 -->
              <button
                v-if="!currentNoteData.is_trashed && !currentNoteData.is_secret && sidebarStore.activeModule !== 'vault'"
                class="toolbar-btn"
                :class="{ active: currentNoteData.is_public }"
                @click="handleTogglePublic"
                :title="currentNoteData.is_public ? '取消公开' : '设为公开'"
              >
                <i :class="currentNoteData.is_public ? 'fas fa-globe' : 'fas fa-lock'"></i>
              </button>

              <button
                v-if="currentNoteData.is_public && !currentNoteData.is_trashed && !currentNoteData.is_secret && sidebarStore.activeModule !== 'vault'"
                class="toolbar-btn"
                @click="handleCopyPublicLink"
                title="复制公开链接"
              >
                <i class="fas fa-link"></i>
              </button>

              <button
                v-if="canSendCurrentNote"
                class="toolbar-btn"
                :disabled="isSendingNote"
                @click="openNoteSendDialog"
                title="发送笔记"
              >
                <i :class="isSendingNote ? 'fas fa-spinner fa-spin' : 'fas fa-share'"></i>
              </button>

              <button
                v-if="canManageCurrentNote"
                class="toolbar-btn"
                @click="showCollaboratorsDialog = true"
                title="管理协作成员"
              >
                <i class="fas fa-user-group"></i>
              </button>

              <button
                v-if="canCommentCurrentNote"
                class="toolbar-btn"
                @click="showAnnotationsDialog = true"
                title="批注与评论"
              >
                <i class="fas fa-comment-dots"></i>
              </button>

              <button
                v-if="canViewVersionHistory"
                class="toolbar-btn"
                @click="showVersionHistory = true"
                title="版本历史"
              >
                <i class="fas fa-clock-rotate-left"></i>
              </button>

              <div class="divider"></div>

              <!-- 删除按钮 -->
              <button
                class="toolbar-btn danger"
                @click="handleDelete"
                title="删除笔记"
              >
                <i class="fas fa-trash-alt"></i>
              </button>
            </div>
          </div>

          <!-- 工作区内容 -->
          <div class="workspace-content">
            <!-- 阅读模式 -->
            <div v-if="viewMode === 'read'" class="viewer-wrapper">
              <!-- 回收站中的保密笔记：显示提示而不解密 -->
              <div v-if="currentNoteData.is_secret && currentNoteData.is_trashed" class="trash-secret-notice">
                <div class="notice-icon">
                  <i class="fas fa-lock"></i>
                </div>
                <h3 class="notice-title">保密笔记</h3>
                <p class="notice-message">此笔记为保密笔记，在回收站中无法查看内容</p>
                <p class="notice-hint">如需查看内容，请先恢复笔记到保密柜</p>
              </div>
              <!-- 正常保密笔记（非回收站） -->
              <NoteShadowViewer
                v-else-if="currentNoteData.is_secret"
                :key="currentNoteId"
                :content="currentNoteData.content"
                :toc="currentNoteData.toc"
                :is-dark="isDarkMode"
                :is-secret="currentNoteData.is_secret"
                :is-trashed="currentNoteData.is_trashed"
                :note-id="currentNoteId"
                @selection="handleNoteSelection"
              />
              <!-- 普通笔记 -->
              <NoteShadowViewer
                v-else
                :key="currentNoteId"
                :content="currentNoteData.content"
                :toc="currentNoteData.toc"
                :is-dark="isDarkMode"
                :is-secret="false"
                :is-trashed="currentNoteData.is_trashed"
                :note-id="currentNoteId"
              />
            </div>

            <!-- 编辑模式 -->
            <NoteEditor
              v-else
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

        <!-- 空状态（非保密柜或保密柜已验证时显示） -->
        <div v-else-if="sidebarStore.activeModule !== 'vault' || sidebarStore.vaultStatus.isVerified" class="empty-editor-state">
          <i class="fas fa-book-open"></i>
          <p>选择或创建一篇笔记开始写作</p>
          <button
            v-if="canCreateNoteInCurrentContext"
            class="primary-btn"
            @click="() => handleCreateNote()"
          >
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

    <NewMessageDialog
      v-if="showNoteSendDialog"
      purpose="forward"
      @close="closeNoteSendDialog"
      @select="handleNoteSendTarget"
    />
    <NoteCollaborators
      v-if="currentNoteId && !currentNoteData.is_secret"
      v-model="showCollaboratorsDialog"
      :note-id="currentNoteId"
    />
    <NoteAnnotations
      v-if="currentNoteId && !currentNoteData.is_secret"
      v-model="showAnnotationsDialog"
      :note-id="currentNoteId"
      :selection="noteSelection"
    />
    <NoteVersionHistory
      v-if="currentNoteId"
      v-model="showVersionHistory"
      :note-id="currentNoteId"
      @restored="handleRevisionRestored"
    />
    <GlobalSearchDialog />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import Breadcrumb from '@/components/common/Breadcrumb/index.vue'
import GlobalSearchDialog from '@/components/common/GlobalSearchDialog/index.vue'
import NoteEditor from '@/components/knowledge/NoteEditor/index.vue'
import NoteShadowViewer from '@/components/knowledge/NoteShadowViewer/index.vue'
import NotificationCenter from '@/components/notifications/NotificationCenter/index.vue'
import ShareCenter from '@/components/knowledge/ShareCenter/index.vue'
import AssetCenter from '@/components/knowledge/AssetCenter/index.vue'
import NoteCollaborators from '@/components/knowledge/NoteCollaborators/index.vue'
import NoteAnnotations from '@/components/knowledge/NoteAnnotations/index.vue'
import NoteVersionHistory from '@/components/knowledge/NoteVersionHistory/index.vue'
import DragDropOverlay from '@/components/common/DragDropOverlay/index.vue'
import VaultVerifyDialog from '@/components/common/VaultVerifyDialog/index.vue'
import VaultSetupDialog from '@/components/common/VaultSetupDialog/index.vue'
import PrimarySidebar from '@/components/layout/PrimarySidebar/index.vue'
import SecondaryPanel from '@/components/layout/SecondaryPanel/index.vue'
import NewMessageDialog from '@/components/messages/NewMessageDialog/index.vue'
import { useKnowledgeList } from '@/composables/useKnowledgeList'
import { useGlobalVaultAutoLock } from '@/composables/useGlobalVaultAutoLock'
import '@/assets/styles/components/knowledge-list.css'

// 全局保密柜自动锁定：活动重置 + 节流 + visibilitychange 60s
useGlobalVaultAutoLock()

const {
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
  canCreateNoteInCurrentContext,

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
} = useKnowledgeList()

const showNoteSendDialog = ref(false)
const isSendingNote = ref(false)
const showCollaboratorsDialog = ref(false)
const showAnnotationsDialog = ref(false)
const showVersionHistory = ref(false)
const noteSelection = ref(null)

const canSendCurrentNote = computed(() => (
  !!currentNoteId.value &&
  !currentNoteData.value.is_trashed &&
  !currentNoteData.value.is_secret &&
  sidebarStore.activeModule !== 'vault'
))

const canManageCurrentNote = computed(() => (
  !!currentNoteId.value &&
  !currentNoteData.value.is_secret &&
  !currentNoteData.value.is_trashed &&
  currentNoteData.value.permissions?.can_manage
))

const canCommentCurrentNote = computed(() => (
  !!currentNoteId.value &&
  !currentNoteData.value.is_secret &&
  !currentNoteData.value.is_trashed &&
  currentNoteData.value.permissions?.can_comment
))

const canViewVersionHistory = computed(() => (
  !!currentNoteId.value &&
  !currentNoteData.value.is_trashed &&
  currentNoteData.value.permissions?.can_edit
))

watch(
  () => [currentNoteId.value, currentNoteData.value.is_secret],
  ([, isSecret]) => {
    if (isSecret) {
      showCollaboratorsDialog.value = false
    }
  },
)

function handleNoteSelection(selection) {
  noteSelection.value = selection
}

function handleRevisionRestored(note) {
  currentNoteData.value = {
    ...currentNoteData.value,
    ...note,
  }
  viewMode.value = 'read'
  hasUnsavedChanges.value = false
}

function getCSRFToken() {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

async function openNoteSendDialog() {
  if (!canSendCurrentNote.value) {
    ElMessage.warning('保密笔记或回收站笔记不能通过普通消息发送')
    return
  }
  if (hasUnsavedChanges.value && viewMode.value === 'edit') {
    await handleSave()
    if (hasUnsavedChanges.value) {
      ElMessage.warning('请先保存当前笔记后再发送')
      return
    }
  }
  showNoteSendDialog.value = true
}

function closeNoteSendDialog() {
  if (isSendingNote.value) return
  showNoteSendDialog.value = false
}

async function handleNoteSendTarget(target) {
  if (!target || !currentNoteId.value || isSendingNote.value) return
  isSendingNote.value = true
  try {
    const isGroupTarget = target.type === 'group'
    const url = isGroupTarget
      ? `/api/messages/groups/${target.id}/notes/share/`
      : '/api/messages/notes/share/'
    const body = isGroupTarget
      ? { note_id: currentNoteId.value }
      : { note_id: currentNoteId.value, recipient_id: target.id }
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken(),
      },
      body: JSON.stringify(body),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.error || data.message || '发送笔记失败')
    ElMessage.success(isGroupTarget ? '已发送到群聊' : '已发送到私信')
    showNoteSendDialog.value = false
  } catch (error) {
    ElMessage.error(error?.message || '发送笔记失败')
  } finally {
    isSendingNote.value = false
  }
}
</script>
