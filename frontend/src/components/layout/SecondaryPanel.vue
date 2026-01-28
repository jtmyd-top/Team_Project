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

          <!-- 正常笔记列表（非保密柜或已验证） -->
          <template v-else>
            <!-- 子文件夹列表（如果有） -->
            <div v-if="sidebarStore.currentSubfolders.length > 0" class="subfolders-section">
              <div class="section-header">
                <i class="fas fa-folder"></i>
                <span>子分类</span>
              </div>
              <div
                v-for="subfolder in sidebarStore.currentSubfolders"
                :key="subfolder.id"
                class="subfolder-item"
                @click="handleSubfolderClick(subfolder)"
              >
                <i class="fas fa-folder folder-icon"></i>
                <span class="subfolder-name">{{ subfolder.name }}</span>
                <span v-if="subfolder.notes_count > 0" class="subfolder-count">
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
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSidebarStore } from '@/stores/sidebar'
import { useVaultStore } from '@/stores/vault'
import { useVaultEncryption } from '@/composables/useVaultEncryption'
import { useClientCrypto } from '@/composables/useClientCrypto'
import FolderTreeItem from '@/components/common/FolderTreeItem.vue'
import NoteListItem from '@/components/common/NoteListItem.vue'
import NoteContextMenu from '@/components/common/NoteContextMenu.vue'
import MoveToDialog from '@/components/common/MoveToDialog.vue'

// ==================== Stores & Composables ====================
const sidebarStore = useSidebarStore()
const vaultStore = useVaultStore()

// 【关键】在组件顶部统一调用一次，确保整个组件使用同一个实例
const { dek, isKeyValid, verify2FAAndGetKey, tryRecoverKeyFromSession } = useVaultEncryption()
const { encryptContent, decryptContent } = useClientCrypto()

const props = defineProps({
  activeNoteId: {
    type: [Number, String],
    default: null
  }
})

const emit = defineEmits(['note-select', 'note-create'])

// 响应式检测
const isMobile = ref(false)
const MOBILE_BREAKPOINT = 900  // 小于此宽度视为移动端/小屏

// 拖拽相关状态
const isInboxDragOver = ref(false)

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
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

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

// 计算属性
const showBackButton = computed(() => {
  return sidebarStore.activeModule === 'my-space' && sidebarStore.secondaryView === 'notes'
})

const panelTitle = computed(() => {
  if (sidebarStore.activeModule === 'my-space') {
    if (sidebarStore.secondaryView === 'notes') {
      return sidebarStore.currentFolder?.name || '未分类笔记'
    }
    return '笔记分类'
  }
  return sidebarStore.moduleTitle
})

const showNewNoteBtn = computed(() => {
  return ['all-notes', 'my-space', 'vault'].includes(sidebarStore.activeModule)
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
  return !['trash'].includes(sidebarStore.activeModule)
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

const filteredNotes = computed(() => {
  if (!searchQuery.value) {
    return sidebarStore.currentNotes
  }
  const query = searchQuery.value.toLowerCase()
  return sidebarStore.currentNotes.filter(note => 
    note.title.toLowerCase().includes(query)
  )
})

// 方法
function handleBack() {
  sidebarStore.backToFolders()
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
  sidebarStore.enterFolder(subfolder.id)
}

function handleFolderRename(folder, newName) {
  sidebarStore.renameFolder(folder.id, newName)
}

async function handleFolderDelete(folder) {
  try {
    await ElMessageBox.confirm(
      `文件夹内的笔记将移动到未分类笔记。`,
      `确定删除"${folder.name}"？`,
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
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

/**
 * 加密笔记内容并保存
 * @param {Object} note - 笔记对象
 * @param {string} dekValue - DEK（数据加密密钥，Base64编码）
 */
async function performEncryption(note, dekValue) {
  if (!note || !note.id) {
    throw new Error('笔记对象无效')
  }

  if (!dekValue || typeof dekValue !== 'string' || dekValue.trim() === '') {
    throw new Error('DEK 不可用或格式无效: ' + (dekValue ? '格式错误' : '为空'))
  }

  try {
    // 【关键】始终从数据库加载最新的笔记数据，确保获取的是最新内容
    console.log(`[Vault] Loading latest note data for ID: ${note.id}`)
    const fetchResp = await fetch(`/api/notes/${note.id}/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    if (!fetchResp.ok) {
      throw new Error('加载笔记数据失败')
    }

    const noteData = await fetchResp.json()
    let plainTitle = noteData.title || ''
    let plainContent = noteData.content || ''

    // 验证内容
    if (!plainContent || plainContent.trim() === '') {
      throw new Error('笔记内容为空，无法加密')
    }

    if (!plainTitle || plainTitle.trim() === '') {
      throw new Error('笔记标题为空，无法加密')
    }

    console.log('[Vault] performEncryption: Ready to encrypt', {
      noteId: note.id,
      plainTitleLength: plainTitle.length,
      plainContentLength: plainContent.length,
      dekLength: dekValue.length
    })

    // 【关键】同时加密 title 和 content
    const encryptedTitle = encryptContent(plainTitle, dekValue)
    const encryptedContent = encryptContent(plainContent, dekValue)

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value

    console.log('[Vault] performEncryption: Saving encrypted data...', {
      encryptedTitleLength: encryptedTitle.length,
      encryptedContentLength: encryptedContent.length
    })

    // 【关键】保存加密后的 title 和 content 到数据库
    const updateResponse = await fetch(`/api/notes/${note.id}/`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({
        title: encryptedTitle,
        content: encryptedContent
      })
    })

    if (!updateResponse.ok) {
      const errorData = await updateResponse.json()
      throw new Error('保存加密内容失败: ' + (errorData.message || '后端错误'))
    }

    const updateResult = await updateResponse.json()
    console.log('[Vault] performEncryption: Encrypted data saved successfully', {
      plainTitleLength: plainTitle.length,
      encryptedTitleLength: encryptedTitle.length,
      plainContentLength: plainContent.length,
      encryptedContentLength: encryptedContent.length,
      serverResponse: updateResult
    })
  } catch (e) {
    console.error('[Vault] performEncryption error:', e)
    throw e
  }
}

/**
 * 获取可用的 DEK
 * 优先从 vaultStore 获取，然后从 useVaultEncryption 获取
 */
function getAvailableDEK() {
  // 优先使用 vaultStore 中的 DEK（因为验证成功后会更新这里）
  if (vaultStore.dek && vaultStore.keyExpireTime && vaultStore.keyExpireTime > Date.now()) {
    console.log('[Vault] Using DEK from vaultStore')
    return vaultStore.dek
  }

  // 其次使用 composable 中的 DEK
  if (dek.value && isKeyValid.value) {
    console.log('[Vault] Using DEK from useVaultEncryption')
    return dek.value
  }

  return null
}

/**
 * 等待 DEK 被更新
 * 验证成功后，DEK 会被更新，这个函数会等待其更新
 * @returns {Promise<string>} DEK 值或 null
 */
async function waitForDEK(timeout = 5000) {
  return new Promise((resolve) => {
    // 检查 vaultStore 中的 DEK（优先）
    if (vaultStore.dek && vaultStore.keyExpireTime && vaultStore.keyExpireTime > Date.now()) {
      resolve(vaultStore.dek)
      return
    }

    // 检查 useVaultEncryption 中的 DEK
    if (dek.value && isKeyValid.value) {
      resolve(dek.value)
      return
    }

    // 定期检查，直到 DEK 被更新
    const checkInterval = setInterval(() => {
      const availableDEK = getAvailableDEK()
      if (availableDEK) {
        clearInterval(checkInterval)
        clearTimeout(timeoutHandle)
        resolve(availableDEK)
      }
    }, 100)

    // 超时保护
    const timeoutHandle = setTimeout(() => {
      clearInterval(checkInterval)
      resolve(null) // 超时，返回 null
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
async function executeEncryptAndSave(note) {
  const availableDEK = getAvailableDEK()

  if (availableDEK) {
    // ========== 分支 A: Smart Pass（已解锁）==========
    // DEK 已有效，直接加密，无需弹窗
    console.log('[Vault] Branch A: Smart Pass - Using existing key')
    try {
      await performEncryption(note, availableDEK)
      ElMessage.success('加入保密柜成功！内容已加密')
      // 刷新数据显示
      await refreshVaultData(note)
    } catch (e) {
      console.error('[Vault] Smart Pass encryption failed:', e)
      ElMessage.error('加密失败: ' + e.message)
      // 撤销 is_secret 标志
      await revertSecretFlag(note)
    }
  } else {
    // ========== 分支 B: Require Auth（未解锁）==========
    // 没有有效 DEK，需要弹窗验证
    console.log('[Vault] Branch B: Require Auth - Need 2FA verification')

    // 撤销 is_secret 标志，因为加密还未完成
    await revertSecretFlag(note)

    // 定义待处理的加密操作
    const encryptOperation = async () => {
      // 等待 vaultStore 或 useVaultEncryption 中的 DEK 被更新
      // （验证成功后会触发 'vault-verification-success' 事件）
      const dekForEncryption = await waitForDEK()

      if (!dekForEncryption) {
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

      // 执行加密
      await performEncryption(note, dekForEncryption)
    }

    // 保存待处理操作到 vaultStore
    vaultStore.setPendingOperation(note.id, note.content, encryptOperation)

    // 弹出 2FA 验证对话框
    sidebarStore.vaultVerifyDialogVisible = true

    // 监听验证成功事件
    const handleVerifySuccess = async (event) => {
      try {
        // 【关键修复】从事件中提取 DEK 和 expireTime
        const { dek: dekFromEvent, expireTime } = event.detail || {}

        if (dekFromEvent && expireTime) {
          console.log('[Vault] Received DEK from verification event, saving to store...', {
            dekLength: dekFromEvent.length,
            expireTime
          })
          // 保存 DEK 到 vaultStore（这样后续的解密和加密都能使用）
          vaultStore.setDEK(dekFromEvent, expireTime)
        } else {
          console.warn('[Vault] Event missing DEK or expireTime:', { dek: !!dekFromEvent, expireTime })
        }

        await vaultStore.executePendingOperation()
        ElMessage.success('加入保密柜成功！内容已加密')
        // 刷新数据
        await refreshVaultData(note)
      } catch (e) {
        console.error('[Vault] Failed to execute pending operation:', e)
        ElMessage.error('加密失败: ' + e.message)
        vaultStore.clearPendingOperation()
        // 尝试撤销 is_secret 标志
        await revertSecretFlag(note)
      }
      // 移除监听
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
    const currentNoteResp = await fetch(`/api/notes/${note.id}/`, {
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

        // 确保 DEK 可用
        let dekToUse = dek.value
        if (!dekToUse || !isKeyValid.value) {
          console.log('[Vault] DEK not available, attempting to recover...')
          const recovered = await tryRecoverKeyFromSession()
          dekToUse = dek.value

          if (!dekToUse || !isKeyValid.value) {
            console.error('[Vault] Cannot get DEK for decryption')
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
          contentLength: decryptedContent.length,
          dekLength: dekToUse.length
        })

        try {
          // 尝试解密 title
          if (decryptedTitle) {
            try {
              const result = await decryptContent(decryptedTitle, dekToUse)
              console.log('[Vault] Title decrypted successfully, length:', result.length)
              decryptedTitle = result
            } catch (e) {
              console.warn('[Vault] Title decryption failed, treating as plaintext:', e.message)
              // title 可能本身就是明文（加入保密柜时没有加密成功）
              decryptedTitle = currentNote.title || ''
            }
          }

          // 尝试解密 content
          if (decryptedContent) {
            try {
              const result = await decryptContent(decryptedContent, dekToUse)
              console.log('[Vault] Content decrypted successfully, length:', result.length)
              decryptedContent = result
            } catch (e) {
              console.warn('[Vault] Content decryption failed, treating as plaintext:', e.message)
              // content 可能本身就是明文（加入保密柜时没有加密成功）
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
      await executeEncryptAndSave(note)

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

async function handleNoteTrash(note) {
  try {
    await ElMessageBox.confirm(
      '笔记将被移入回收站，可以随时恢复。',
      `移入回收站？`,
      {
        confirmButtonText: '移入回收站',
        cancelButtonText: '取消',
        type: 'warning'
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
        confirmButtonText: '永久删除',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger'
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
</script>

<style scoped>
/* 移动端遮罩层 */
.mobile-overlay {
  position: fixed;
  top: 64px; /* 与侧边栏对齐，避免覆盖顶部导航 */
  left: 64px; /* 从一级侧边栏右侧开始 */
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 150;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.secondary-panel {
  width: 240px;
  height: 100%;
  background: var(--bg-secondary, #f5f5f5);
  border-right: 1px solid var(--border-color, #e0e0e0);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease, transform 0.3s ease;
  overflow: hidden;
  flex-shrink: 0;
}

/* 移动端侧边栏 - 浮动在内容上方 */
.secondary-panel.is-mobile {
  position: fixed;
  left: 64px;
  top: 64px; /* 顶部导航栏高度 */
  bottom: 0;
  z-index: 160;
  box-shadow: 4px 0 16px rgba(0, 0, 0, 0.15);
}

.secondary-panel.is-collapsed {
  width: 0;
  transform: translateX(-100%);
}

/* 过渡动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  width: 0;
  opacity: 0;
  transform: translateX(-100%);
}

/* 头部 */
.panel-header {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  min-height: 48px;
}

.back-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 8px;
  color: var(--text-secondary, #666);
  transition: all 0.2s;
}

.back-btn:hover {
  background: var(--hover-bg, rgba(0,0,0,0.05));
  color: var(--text-primary, #333);
}

.panel-title {
  flex: 1;
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.panel-actions {
  display: flex;
  gap: 4px;
}

.action-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #666);
  transition: all 0.2s;
}

.action-btn:hover {
  background: var(--hover-bg, rgba(0,0,0,0.05));
  color: var(--primary-color, #409eff);
}

/* 搜索框 */
.search-box {
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-primary, #fff);
  margin: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #e0e0e0);
}

.search-icon {
  color: var(--text-secondary, #999);
  font-size: 12px;
}

.search-box input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 13px;
  color: var(--text-primary, #333);
}

.search-box input::placeholder {
  color: var(--text-secondary, #999);
}

.clear-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--text-secondary, #999);
  padding: 2px;
}

/* 内容区域 */
.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

/* 收件箱 */
.inbox-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.2s, border 0.2s;
  gap: 10px;
  border: 2px solid transparent;
  border-radius: 6px;
  margin: 0 8px;
}

.inbox-item:hover {
  background: var(--hover-bg, rgba(0,0,0,0.05));
}

/* 收件箱拖拽放置目标高亮 */
.inbox-item.is-drop-target {
  background: var(--primary-bg, rgba(64, 158, 255, 0.15));
  border: 2px dashed var(--primary-color, #409eff);
}

.inbox-item.is-drop-target i {
  color: var(--primary-color, #409eff);
  transform: scale(1.1);
}

.inbox-item.is-drop-target .inbox-label {
  color: var(--primary-color, #409eff);
  font-weight: 600;
}

.inbox-item i {
  color: var(--primary-color, #409eff);
  font-size: 14px;
}

.inbox-label {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary, #333);
}

.inbox-count {
  background: var(--primary-color, #409eff);
  color: white;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

/* 分割线 */
.divider {
  height: 1px;
  background: var(--border-color, #e0e0e0);
  margin: 8px 16px;
}

/* 子文件夹区域 */
.subfolders-section {
  margin-bottom: 4px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, #999);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-header i {
  font-size: 11px;
}

.subfolder-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.2s;
  gap: 10px;
}

.subfolder-item:hover {
  background: var(--hover-bg, rgba(0,0,0,0.05));
}

.subfolder-item .folder-icon {
  color: var(--primary-color, #409eff);
  font-size: 14px;
}

.subfolder-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.subfolder-count {
  background: var(--bg-tertiary, #eee);
  color: var(--text-secondary, #666);
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

.subfolder-arrow {
  color: var(--text-secondary, #999);
  font-size: 10px;
}

.notes-section {
  margin-top: 4px;
}

/* 文件夹树 */
.folder-tree {
  padding: 0 8px;
}

/* 加载和错误状态 */
.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  color: var(--text-secondary, #999);
  gap: 12px;
}

.error-state {
  color: var(--error-color, #f56c6c);
}

.error-state button {
  padding: 6px 16px;
  border: 1px solid var(--primary-color, #409eff);
  background: transparent;
  color: var(--primary-color, #409eff);
  border-radius: 4px;
  cursor: pointer;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  color: var(--text-secondary, #999);
  text-align: center;
}

.empty-state i {
  font-size: 32px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-state p {
  margin: 0 0 16px;
  font-size: 13px;
}

.create-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  background: var(--primary-color, #409eff);
  color: white;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.2s;
}

.create-btn:hover {
  background: var(--primary-color-dark, #337ecc);
}

.empty-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 200px;
}

.create-btn.secondary {
  background: transparent;
  border: 1px solid var(--primary-color, #409eff);
  color: var(--primary-color, #409eff);
}

.create-btn.secondary:hover {
  background: rgba(64, 158, 255, 0.1);
}

/* 对话框 */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: var(--bg-primary, #fff);
  padding: 20px;
  border-radius: 8px;
  width: 300px;
  max-width: 90%;
}

.dialog h4 {
  margin: 0 0 16px;
  font-size: 16px;
  color: var(--text-primary, #333);
}

.dialog input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
}

.dialog input:focus {
  border-color: var(--primary-color, #409eff);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.cancel-btn {
  padding: 8px 16px;
  border: 1px solid var(--border-color, #e0e0e0);
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary, #666);
}

.confirm-btn {
  padding: 8px 16px;
  border: none;
  background: var(--primary-color, #409eff);
  color: white;
  border-radius: 6px;
  cursor: pointer;
}

.confirm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 保密柜相关样式 */
.vault-lock-btn {
  color: var(--warning-color, #e6a23c) !important;
}

.vault-lock-btn:hover {
  background: rgba(230, 162, 60, 0.1) !important;
}

.vault-timer-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--bg-tertiary, rgba(0, 0, 0, 0.02));
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  font-size: 12px;
  color: var(--text-secondary, #909399);
}

.vault-timer-bar i {
  color: var(--primary-color, #409eff);
}

/* 保密柜锁定状态 */
.vault-locked-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.vault-locked-state .lock-icon-large {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.vault-locked-state .lock-icon-large i {
  font-size: 32px;
  color: white;
}

.vault-locked-state h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  margin: 0 0 8px;
}

.vault-locked-state p {
  font-size: 13px;
  color: var(--text-secondary, #909399);
  margin: 0 0 24px;
}

.vault-locked-state .unlock-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.vault-locked-state .unlock-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}
</style>
