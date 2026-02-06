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

              <!-- 公开分享按钮 - 回收站中隐藏 -->
              <button
                v-if="!currentNoteData.is_trashed"
                class="toolbar-btn"
                :class="{ active: currentNoteData.is_public }"
                @click="handleTogglePublic"
                :title="currentNoteData.is_public ? '取消公开' : '设为公开'"
              >
                <i :class="currentNoteData.is_public ? 'fas fa-globe' : 'fas fa-lock'"></i>
              </button>

              <button
                v-if="currentNoteData.is_public && !currentNoteData.is_trashed"
                class="toolbar-btn"
                @click="handleCopyPublicLink"
                title="复制公开链接"
              >
                <i class="fas fa-link"></i>
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
              <NoteShadowViewer
                v-if="currentNoteData.is_secret"
                :key="currentNoteId"
                :content="currentNoteData.content"
                :title="displayTitle"
              />
              <div v-else class="note-content" v-html="currentNoteData.content"></div>
            </div>

            <!-- 编辑模式 -->
            <div v-else class="editor-wrapper">
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
import Breadcrumb from '@/components/common/Breadcrumb.vue'
import NoteEditor from '@/components/knowledge/NoteEditor/index.vue'
import NoteShadowViewer from '@/components/knowledge/NoteShadowViewer/index.vue'
import DragDropOverlay from '@/components/common/DragDropOverlay.vue'
import VaultVerifyDialog from '@/components/common/VaultVerifyDialog/index.vue'
import VaultSetupDialog from '@/components/common/VaultSetupDialog.vue'
import PrimarySidebar from '@/components/layout/PrimarySidebar/index.vue'
import SecondaryPanel from '@/components/layout/SecondaryPanel/index.vue'
import { useKnowledgeList } from '@/composables/useKnowledgeList'
import '@/assets/styles/components/knowledge-list.css'

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
</script>
