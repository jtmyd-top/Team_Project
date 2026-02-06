<template>
  <!-- 移动端遮罩层 -->
  <div
    v-if="isMobile && sidebarStore.showSecondary && !sidebarStore.isCollapsed"
    class="mobile-overlay"
    @click="sidebarStore.setCollapsed(true)"
  ></div>

  <transition name="slide">
    <aside
      v-if="sidebarStore.showSecondary"
      class="secondary-panel"
      :class="{ 'is-collapsed': sidebarStore.isCollapsed, 'is-mobile': isMobile }"
    >
      <!-- 头部区域 -->
      <div class="panel-header">
        <!-- 返回按钮（文件夹内的笔记列表视图时显示） -->
        <button
          v-if="showBackButton"
          class="back-btn"
          @click="handleBack"
          title="返回文件夹列表"
        >
          <i class="fas fa-arrow-left"></i>
        </button>

        <!-- 标题 -->
        <h3 class="panel-title">
          {{ panelTitle }}
        </h3>

        <!-- 操作按钮 -->
        <div class="panel-actions">
          <!-- 保密柜锁定按钮 -->
          <button
            v-if="sidebarStore.activeModule === 'vault' && sidebarStore.vaultStatus.isVerified"
            class="action-btn vault-lock-btn"
            @click="handleLockVault"
            title="锁定保密柜"
          >
            <i class="fas fa-lock"></i>
          </button>

          <!-- 新建笔记按钮 -->
          <button
            v-if="showNewNoteBtn"
            class="action-btn"
            @click="handleCreateNote"
            title="新建笔记"
          >
            <i class="fas fa-plus"></i>
          </button>

          <!-- 新建文件夹按钮（仅在我的空间显示） -->
          <button
            v-if="showNewFolderBtn"
            class="action-btn"
            @click="handleNewFolderClick"
            title="新建文件夹"
          >
            <i class="fas fa-folder-plus"></i>
          </button>

          <!-- 收起按钮 -->
          <button
            class="action-btn collapse-btn"
            @click="sidebarStore.toggleCollapse()"
            title="收起侧边栏"
          >
            <i class="fas fa-chevron-left"></i>
          </button>
        </div>
      </div>

      <!-- 保密柜剩余时间提示 -->
      <div v-if="sidebarStore.activeModule === 'vault' && sidebarStore.vaultStatus.isVerified" class="vault-timer-bar">
        <i class="fas fa-clock"></i>
        <span>{{ formatVaultTime(sidebarStore.vaultStatus.remainingSeconds) }} 后自动锁定</span>
      </div>

      <!-- 搜索框（全部笔记时显示） -->
      <div v-if="showSearch" class="search-box">
        <i class="fas fa-search search-icon"></i>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索笔记..."
          @input="handleSearch"
        />
        <button
          v-if="searchQuery"
          class="clear-btn"
          @click="clearSearch"
        >
          <i class="fas fa-times"></i>
        </button>
      </div>

      <!-- 内容区域 -->
      <div class="panel-content">
        <!-- 加载状态 -->
        <div v-if="sidebarStore.isLoading" class="loading-state">
          <i class="fas fa-spinner fa-spin"></i>
          <span>加载中...</span>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="sidebarStore.error" class="error-state">
          <i class="fas fa-exclamation-circle"></i>
          <span>{{ sidebarStore.error }}</span>
          <button @click="sidebarStore.loadModuleData()">重试</button>
        </div>

        <!-- 文件夹树视图（我的空间 - 文件夹列表） -->
        <template v-else-if="sidebarStore.activeModule === 'my-space' && sidebarStore.secondaryView === 'folders'">
          <!-- 未分类笔记（也是放置目标） -->
          <div
            class="inbox-item"
            :class="{ 'is-drop-target': isInboxDragOver }"
            @click="sidebarStore.enterInbox()"
            @dragover.prevent="handleInboxDragOver"
            @dragleave="handleInboxDragLeave"
            @drop="handleInboxDrop"
          >
            <i class="fas fa-inbox"></i>
            <span class="inbox-label">未分类笔记</span>
            <span v-if="sidebarStore.inboxCount > 0" class="inbox-count">
              {{ sidebarStore.inboxCount }}
            </span>
          </div>

          <div class="divider"></div>

          <!-- 文件夹树 -->
          <div v-if="sidebarStore.folders.length > 0" class="folder-tree">
            <FolderTreeItem
              v-for="folder in sidebarStore.folders"
              :key="folder.id"
              :folder="folder"
              @click="handleFolderClick"
              @rename="handleFolderRename"
              @delete="handleFolderDelete"
              @create-subfolder="handleCreateSubfolder"
              @note-drop="handleNoteDrop"
            />
          </div>

          <!-- 空状态 -->
          <div v-else class="empty-state">
            <i class="fas fa-folder-open"></i>
            <p>尚未创建分类</p>
            <div class="empty-actions">
              <button class="create-btn" @click="showCreateFolderDialog = true">
                <i class="fas fa-folder-plus"></i>
                新建文件夹
              </button>
              <button class="create-btn secondary" @click="handleCreateNote">
                <i class="fas fa-plus"></i>
                新建笔记
              </button>
            </div>
          </div>
        </template>

        <!-- 笔记列表视图 -->
        <template v-else>
          <!-- 保密柜锁定状态 -->
          <div v-if="sidebarStore.activeModule === 'vault' && !sidebarStore.vaultStatus.isVerified" class="vault-locked-state">
            <div class="lock-icon-large">
              <i class="fas fa-lock"></i>
            </div>
            <h3>保密柜已锁定</h3>
            <p>请完成两因素认证以访问保密笔记</p>
            <button class="unlock-btn" @click="handleUnlockVault">
              <i class="fas fa-unlock"></i>
              验证解锁
            </button>
          </div>

          <!-- 【新增】回收站只读 Banner -->
          <div v-if="isInTrashView && sidebarStore.currentFolder" class="trash-readonly-banner">
            <i class="fas fa-info-circle"></i>
            <span>此文件夹位于回收站，无法编辑</span>
          </div>

          <!-- 正常笔记列表（非保密柜或已验证） -->
          <template v-else>
            <!-- 【修改】回收站中的子文件夹列表 -->
            <div v-if="sidebarStore.currentSubfolders.length > 0" class="subfolders-section">
              <div class="section-header">
                <i class="fas fa-folder"></i>
                <span>子分类</span>
              </div>
              <div
                v-for="subfolder in sidebarStore.currentSubfolders"
                :key="subfolder.id"
                class="subfolder-item"
                :class="{ 'is-trashed': isInTrashView }"
                @click="handleSubfolderClick(subfolder)"
              >
                <i class="fas fa-folder folder-icon"></i>
                <span class="subfolder-name">{{ subfolder.name }}</span>
                <!-- 【修改】回收站显示项目数量 -->
                <span v-if="isInTrashView && subfolder.children_count !== undefined" class="subfolder-count">
                  包含 {{ subfolder.children_count }} 个项目
                </span>
                <span v-else-if="subfolder.notes_count > 0" class="subfolder-count">
                  {{ subfolder.notes_count }}
                </span>
                <i v-if="subfolder.has_children" class="fas fa-chevron-right subfolder-arrow"></i>
              </div>
              <div v-if="sidebarStore.currentNotes.length > 0" class="divider"></div>
            </div>

            <!-- 笔记列表 -->
            <div v-if="sidebarStore.currentNotes.length > 0" class="notes-section">
              <div v-if="sidebarStore.currentSubfolders.length > 0" class="section-header">
                <i class="fas fa-file-alt"></i>
                <span>笔记</span>
              </div>
              <!-- 【修改】回收站中显示混合列表（笔记 + 文件夹） -->
              <template v-if="isInTrashView && !sidebarStore.currentFolder">
                <!-- 回收站根目录：显示混合列表 -->
                <div
                  v-for="item in filteredNotes"
                  :key="item.id"
                  class="trash-item"
                  :class="{ 'is-folder': item.type === 'folder' }"
                  @click="handleTrashItemClick(item)"
                >
                  <i :class="item.type === 'folder' ? 'fas fa-folder' : 'fas fa-file-alt'" class="item-icon"></i>
                  <!-- 【新增】保密笔记锁图标 -->
                  <i v-if="item.type === 'note' && item.is_secret" class="fas fa-lock secret-lock-icon"></i>
                  <div class="item-info">
                    <span class="item-name">{{ item.type === 'folder' ? item.name : displayTitle(item) }}</span>
                    <span class="item-time">{{ item.trashed_at || item.updated_at }}</span>
                    <!-- 文件夹显示项目数 -->
                    <span v-if="item.type === 'folder' && item.children_count" class="item-count">
                      包含 {{ item.children_count }} 个项目
                    </span>
                  </div>
                  <div class="item-actions" @click.stop>
                    <button class="action-btn restore-btn" @click="handleItemRestore(item)">
                      <i class="fas fa-undo"></i>
                    </button>
                    <button class="action-btn delete-btn" @click="handleItemDelete(item)">
                      <i class="fas fa-trash-alt"></i>
                    </button>
                  </div>
                </div>
              </template>
              <template v-else>
                <!-- 正常笔记列表 -->
                <NoteListItem
                  v-for="note in filteredNotes"
                  :key="note.id"
                  :note="note"
                  :active="note.id === activeNoteId"
                  :show-folder="showFolderInfo"
                  :show-trash-actions="sidebarStore.activeModule === 'trash'"
                  :editing-note-id="editingNoteId"
                  @click="handleNoteClick(note)"
                  @favorite="handleNoteFavorite(note)"
                  @trash="handleNoteTrash(note)"
                  @restore="handleNoteRestore(note)"
                  @delete="handleNoteDelete(note)"
                  @contextmenu="handleNoteContextMenu"
                  @rename="handleNoteRename"
                />
              </template>
            </div>

            <!-- 空笔记状态 -->
            <div v-if="filteredNotes.length === 0 && sidebarStore.currentSubfolders.length === 0" class="empty-state">
              <i :class="sidebarStore.activeModule === 'vault' ? 'fas fa-shield-halved' : 'fas fa-file-alt'"></i>
              <p>{{ emptyStateText }}</p>
              <button
                v-if="showCreateNoteInEmpty"
                class="create-btn"
                @click="handleCreateNote"
              >
                <i class="fas fa-plus"></i>
                {{ sidebarStore.activeModule === 'vault' ? '新建保密笔记' : '新建笔记' }}
              </button>
            </div>
          </template>
        </template>
      </div>

      <!-- 新建文件夹对话框 -->
      <div v-if="showCreateFolderDialog" class="dialog-overlay" @click.self="showCreateFolderDialog = false">
        <div class="dialog">
          <h4>{{ parentFolderIdForNew ? '新建子文件夹' : '新建文件夹' }}</h4>
          <input
            v-model="newFolderName"
            type="text"
            placeholder="文件夹名称"
            @keyup.enter="createFolder"
            ref="folderNameInput"
          />
          <div class="dialog-actions">
            <button class="cancel-btn" @click="showCreateFolderDialog = false">取消</button>
            <button class="confirm-btn" @click="createFolder" :disabled="!newFolderName.trim()">创建</button>
          </div>
        </div>
      </div>
    </aside>
  </transition>

  <!-- 右键菜单 -->
  <NoteContextMenu
    :visible="contextMenuVisible"
    :x="contextMenuX"
    :y="contextMenuY"
    :note="contextMenuNote"
    @close="contextMenuVisible = false"
    @action="handleContextMenuAction"
  />

  <!-- 移动到对话框 -->
  <MoveToDialog
    :visible="moveDialogVisible"
    :note="moveDialogNote"
    :mode="moveDialogMode"
    @close="moveDialogVisible = false"
    @confirm="handleMoveConfirm"
  />
</template>

<script setup>
import FolderTreeItem from '@/components/common/FolderTreeItem.vue'
import NoteListItem from '@/components/common/NoteListItem/index.vue'
import NoteContextMenu from '@/components/common/NoteContextMenu.vue'
import MoveToDialog from '@/components/common/MoveToDialog.vue'
import { useSecondaryPanel } from '@/composables/useSecondaryPanel'
import '@/assets/styles/components/secondary-panel.css'

const props = defineProps({
  activeNoteId: {
    type: [Number, String],
    default: null
  }
})

const emit = defineEmits(['note-select', 'note-create'])

const {
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
} = useSecondaryPanel(props, emit)
</script>
