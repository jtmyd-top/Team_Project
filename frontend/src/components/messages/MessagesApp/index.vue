<template>
  <div class="messages-container" :class="{ 'mobile-chat-open': mobileChatOpen }">
    <!-- Group Invite Preview (full screen overlay) -->
    <GroupInvitePreview
      v-if="showGroupInvitePreview"
      :token="groupInviteToken"
      @close="closeGroupInvitePreview"
      @joined="handleGroupJoined"
    />

    <!-- 无法定位公告的提示对话框 -->
    <div v-if="showAnnouncementJumpFailedDialog" class="announcement-dialog-overlay" @click.self="closeAnnouncementDialog">
      <div class="announcement-dialog">
        <div class="announcement-dialog-header">
          <i class="fas fa-exclamation-triangle"></i>
          <h3>无法定位公告消息</h3>
        </div>
        <div class="announcement-dialog-body">
          <p>此公告对应的消息已被删除或撤回，无法定位。</p>
          <p>您可以前往群设置页面查看完整公告内容。</p>
          <p class="hint-text">注：普通成员仅有查看权限，管理员可编辑群公告。</p>
        </div>
        <div class="announcement-dialog-footer">
          <button class="btn-cancel" @click="closeAnnouncementDialog">取消</button>
          <button class="btn-confirm" @click="openGroupInfoFromDialog">打开群设置</button>
        </div>
      </div>
    </div>

    <!-- 左侧：对话列表 -->
    <aside v-show="!showGroupInvitePreview" class="conversations-sidebar">
      <div class="sidebar-header">
        <h2>私信</h2>
        <button class="new-message-btn" @click="openNewMessageDialog" title="新建私信">
          <i class="fas fa-pen-to-square"></i>
        </button>
      </div>

      <div class="search-box">
        <i class="fas fa-search"></i>
        <input
          v-model="globalSearch"
          type="text"
          placeholder="搜索用户或消息内容..."
          @input="onGlobalSearchInput"
        />
        <button v-if="globalSearch" class="clear-btn" @click="clearGlobalSearch">
          <i class="fas fa-times-circle"></i>
        </button>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button
          v-for="t in tabs"
          :key="t.value"
          class="tab"
          :class="{ active: scope === t.value }"
          @click="switchScope(t.value)"
        >
          <i :class="t.icon"></i>
          <span>{{ t.label }}</span>
          <span v-if="t.value === 'unread' && totalUnread > 0" class="tab-badge">
            {{ totalUnread > 99 ? '99+' : totalUnread }}
          </span>
        </button>
      </div>

      <!-- 搜索结果 -->
      <div v-if="globalSearchResults !== null" class="search-results">
        <div class="search-results-header">
          <span>搜索结果</span>
          <button class="small-link" @click="clearGlobalSearch">
            <i class="fas fa-arrow-left"></i> 返回
          </button>
        </div>
        <div v-if="globalSearchResults.length === 0" class="empty-state">
          <i class="fas fa-search-minus"></i>
          <p>未找到相关内容</p>
        </div>
        <div
          v-for="r in globalSearchResults"
          :key="r.id"
          class="result-row"
          @click="jumpToResult(r)"
        >
          <img :src="r.peer_avatar" :alt="r.peer_username" class="result-avatar" />
          <div class="result-info">
            <div class="result-top">
              <h4>{{ r.peer_username }}</h4>
              <span class="time">{{ formatShortTime(r.created_at) }}</span>
            </div>
            <p class="result-snippet">
              <span v-if="r.is_own">我：</span>
              <span v-html="highlightText(searchResultText(r), globalSearch)"></span>
            </p>
          </div>
        </div>
      </div>

      <!-- 已屏蔽面板 -->
      <BlockedUsersPanel
        v-else-if="scope === 'blocked'"
        ref="blockedPanelRef"
        :csrf-token="csrfToken"
        @updated="loadConversations"
      />

      <!-- 对话列表 -->
      <div v-else class="conversations-list">
        <div v-if="scope === 'archived'" class="scope-hint">
          <i class="fas fa-circle-info"></i>
          <span>新消息到达时将自动恢复到全部会话</span>
        </div>
        <div v-if="loadingConversations && filteredConversations.length === 0" class="empty-state">
          <i class="fas fa-spinner fa-spin"></i>
        </div>
        <div v-else-if="filteredConversations.length === 0" class="empty-state">
          <i :class="emptyStateIcon"></i>
          <p>{{ emptyStateText }}</p>
        </div>
        <ConversationItem
          v-for="conv in filteredConversations"
          :key="conversationKey(conv)"
          :conv="conv"
          :active="selectedConversationKey === conversationKey(conv)"
          :current-user-id="currentUserId"
          @select="selectConversation"
          @context-menu="onConversationContextMenu"
        />
      </div>
    </aside>

    <!-- 右侧：聊天区域 -->
    <main class="chat-area">
      <!-- 未选中会话 -->
      <div v-if="!selectedConversationKey || scope === 'blocked'" class="empty-chat-state">
        <i class="fas fa-comments"></i>
        <p v-if="scope === 'blocked'">屏蔽管理模式<br />在左侧管理你已屏蔽的用户</p>
        <p v-else>
          选择一个对话开始聊天
          <br />
          <span class="hint">或点击 <i class="fas fa-pen-to-square"></i> 发起新对话</span>
        </p>
      </div>

      <div v-else class="chat-container">
        <!-- 头部 -->
        <header class="chat-header">
          <button class="mobile-back-btn" @click="closeMobileChat" title="返回">
            <i class="fas fa-arrow-left"></i>
          </button>
          <div class="chat-user-info" @click="isCurrentGroup ? openGroupInfo() : viewPeerProfile()">
            <img :src="selectedConversation?.avatar" :alt="selectedConversation?.username" class="chat-avatar" />
            <div class="chat-user-meta">
              <h2>{{ selectedConversation?.username }}</h2>
              <span v-if="!isCurrentGroup" class="chat-subtitle secure-subtitle">
                <span class="presence-dot" :class="{ offline: !peerOnline }"></span>
                <span>{{ peerOnline ? '在线' : '离线' }}</span>
                <span class="secure-chip">
                  <i class="fas fa-lock"></i>
                  安全连接
                </span>
              </span>
              <span v-else class="chat-subtitle secure-subtitle">
                <span class="secure-chip">
                  <i class="fas fa-users"></i>
                  群组会话
                </span>
              </span>
            </div>
          </div>
          <div class="chat-actions">
            <button
              class="action-btn"
              @click="toggleSelectionMode"
              :title="selectionMode ? '取消多选' : '多选消息'"
            >
              <i class="fas" :class="selectionMode ? 'fa-xmark' : 'fa-check-double'"></i>
            </button>
            <button class="action-btn" @click="showChatSearch = true" title="在对话中搜索">
              <i class="fas fa-search"></i>
            </button>
            <div class="menu-wrap" @click.stop>
              <button class="action-btn" @click="showChatMenu = !showChatMenu" title="更多">
                <i class="fas fa-ellipsis-vertical"></i>
              </button>
              <div v-if="showChatMenu" class="dropdown-menu">
                <button v-if="!isCurrentGroup" class="dm-item" @click="viewPeerProfile">
                  <i class="fas fa-user-circle"></i> 查看资料
                </button>
                <button v-if="isCurrentGroup" class="dm-item" @click="openGroupInfo">
                  <i class="fas fa-users-gear"></i> 群设置
                </button>
                <button v-if="!isCurrentGroup" class="dm-item" @click="toggleMarkRead">
                  <i class="fas" :class="currentSettings.force_unread || hasUnread ? 'fa-check-double' : 'fa-envelope'"></i>
                  <span v-if="currentSettings.force_unread || hasUnread">标记为已读</span><span v-else>标记为未读</span>
                </button>
                <button v-if="isCurrentGroup" class="dm-item" @click="toggleGroupMarkRead">
                  <i class="fas" :class="currentSettings.force_unread || hasUnread ? 'fa-check-double' : 'fa-envelope'"></i>
                  <span v-if="currentSettings.force_unread || hasUnread">标记为已读</span><span v-else>标记为未读</span>
                </button>
                <button v-if="!isCurrentGroup" class="dm-item" @click="togglePin">
                  <i class="fas fa-thumbtack" :class="{ active: currentSettings.is_pinned }"></i>
                  {{ currentSettings.is_pinned ? '取消置顶' : '置顶会话' }}
                </button>
                <button v-if="isCurrentGroup" class="dm-item" @click="toggleGroupPin">
                  <i class="fas fa-thumbtack" :class="{ active: currentSettings.is_pinned }"></i>
                  {{ currentSettings.is_pinned ? '取消置顶' : '置顶会话' }}
                </button>
                <button v-if="!isCurrentGroup" class="dm-item" @click="toggleMute">
                  <i class="fas" :class="currentSettings.is_muted ? 'fa-bell' : 'fa-bell-slash'"></i>
                  {{ currentSettings.is_muted ? '取消免打扰' : '消息免打扰' }}
                </button>
                <button v-if="isCurrentGroup" class="dm-item" @click="toggleGroupMute">
                  <i class="fas" :class="currentSettings.is_muted ? 'fa-bell' : 'fa-bell-slash'"></i>
                  {{ currentSettings.is_muted ? '取消免打扰' : '消息免打扰' }}
                </button>
                <button v-if="!isCurrentGroup" class="dm-item" @click="openDisappearing">
                  <i class="fas fa-fire-alt"></i> 阅后即焚
                </button>
                <button v-if="!isCurrentGroup" class="dm-item" @click="toggleArchive">
                  <i class="fas" :class="currentSettings.is_archived ? 'fa-inbox' : 'fa-box-archive'"></i>
                  {{ currentSettings.is_archived ? '取消归档' : '归档会话' }}
                </button>
                <button v-if="isCurrentGroup" class="dm-item" @click="toggleGroupArchive">
                  <i class="fas" :class="currentSettings.is_archived ? 'fa-inbox' : 'fa-box-archive'"></i>
                  {{ currentSettings.is_archived ? '取消归档' : '归档会话' }}
                </button>
                <button v-if="!isCurrentGroup" class="dm-item" @click="exportChat">
                  <i class="fas fa-download"></i> 导出聊天记录
                </button>
                <div class="dm-sep"></div>
                <button v-if="!isCurrentGroup" class="dm-item danger" @click="clearConversation">
                  <i class="fas fa-eraser"></i> 清空聊天记录
                </button>
                <button v-if="isCurrentGroup" class="dm-item danger" @click="clearGroupConversation">
                  <i class="fas fa-eraser"></i> 清空聊天记录
                </button>
                <button v-if="isCurrentGroup" class="dm-item danger" @click="leaveCurrentGroup">
                  <i class="fas fa-right-from-bracket"></i> 退出群组
                </button>
                <button v-if="!isCurrentGroup" class="dm-item danger" @click="blockPeer">
                  <i class="fas fa-ban"></i> 拉黑用户
                </button>
                <button v-if="!isCurrentGroup" class="dm-item danger" @click="reportPeer">
                  <i class="fas fa-flag"></i> 举报
                </button>
              </div>
            </div>
          </div>
        </header>

        <!-- 阅后即焚提示条 -->
        <div v-if="!isCurrentGroup && currentSettings.disappearing_enabled" class="disappearing-banner">
          <i class="fas fa-fire-alt"></i>
          已开启阅后即焚 · {{ formatTtl(currentSettings.disappearing_ttl_seconds) }}内消息将自动销毁        </div>

        <button
          v-if="activeGroupAnnouncement"
          class="group-announcement-banner"
          type="button"
          @click="jumpToGroupAnnouncement(activeGroupAnnouncement)"
        >
          <span class="announcement-banner-icon"><i class="fas fa-bullhorn"></i></span>
          <span class="announcement-banner-main">
            <strong>
              群公告
              <em v-if="activeGroupAnnouncement.pinned">置顶</em>
            </strong>
            <span>{{ activeGroupAnnouncement.content }}</span>
          </span>
          <i class="fas fa-location-crosshairs"></i>
        </button>

        <div v-if="selectionMode" class="selection-banner">
          <div class="selection-summary">
            <span class="selection-icon"><i class="fas fa-check-double"></i></span>
            <span>已选择 <strong>{{ selectedMessageIds.size }}</strong> 条消息</span>
          </div>
          <div class="selection-actions">
            <button class="link-btn" @click="clearSelectedMessages">
              <i class="fas fa-xmark"></i>
              清空选择
            </button>
            <button class="toolbar-btn primary" :disabled="selectedMessageIds.size === 0" @click="forwardSelectedAsChatlog">
              <i class="fas fa-share"></i>
              <span>合并转发</span>
            </button>
            <button class="toolbar-btn" :disabled="selectedMessageIds.size === 0" @click="saveSelectedAsNote">
              <i class="fas fa-sticky-note"></i>
              <span>存为笔记</span>
            </button>
            <button class="toolbar-btn danger" :disabled="selectedMessageIds.size === 0" @click="deleteSelectedMessages">
              <i class="fas fa-trash-alt"></i>
              <span>删除所选</span>
            </button>
          </div>
        </div>

        <!-- 消息列表 -->
        <div class="messages-list" ref="messagesListRef" @scroll="onMessagesScroll">
          <div v-if="loadingMessages" class="messages-state">
            <i class="fas fa-spinner fa-spin"></i>
          </div>
          <div v-else-if="messages.length === 0" class="messages-state">
            <i class="fas fa-comment-dots"></i>
            <p>暂无对话历史</p>
            <p class="hint">发一条消息开始聊天吧</p>
          </div>

          <template v-else>
            <div class="message-stream">
              <div v-for="(group, i) in groupedMessages" :key="i" class="message-group">
                <div class="date-sep-wrap">
                  <div class="date-sep">{{ group.date }}</div>
                </div>
                <MessageBubble
                  v-for="m in group.messages"
                  :key="m.id"
                  :data-msg-id="m.id"
                  :class="{ 'jump-highlighted': highlightMessageId === m.id && !globalSearch }"
                  :msg="m"
                  :highlight="highlightMessageId === m.id ? globalSearch : ''"
                  :selectable="selectionMode"
                  :selected="selectedMessageIds.has(m.id)"
                  @context-menu="onMessageContextMenu"
                  @toggle-selected="toggleMessageSelected"
                  @open-merged-forward="openMergedForwardDialog"
                  @reaction-toggle="handleReactionToggle"
                />
              </div>
              <div v-if="typingIndicator.visible" class="typing-indicator">
                <span class="typing-dots"><i></i><i></i><i></i></span>
                <span>{{ typingIndicator.username || selectedConversation?.username || '对方' }} 正在输入...</span>
              </div>
            </div>
          </template>
        </div>
        <button
          v-if="showScrollToBottom"
          class="scroll-bottom-btn"
          type="button"
          title="回到底部"
          @click="jumpToLatest"
        >
          <i class="fas fa-arrow-down"></i>
          <span v-if="scrollBottomUnreadCount > 0" class="scroll-bottom-badge">
            {{ scrollBottomUnreadCount > 99 ? '99+' : scrollBottomUnreadCount }}
          </span>
        </button>

        <!-- 输入区 -->
        <div v-if="peerBlockedByMe" class="blocked-tip">
          <i class="fas fa-ban"></i>
          你已屏蔽此用户。          <button class="link-btn" @click="unblockPeer">解除屏蔽</button>
        </div>
        <div v-else-if="isGroupComposerBlocked" class="blocked-tip">
          <i class="fas fa-microphone-slash"></i>
          当前群已开启全员禁言，仅群主或管理员可以发言
        </div>
        <div v-else class="message-input-area">
          <div v-if="replyDraft" class="reply-draft-bar">
            <span class="reply-label">
              <i class="fas fa-reply"></i>
              {{ replyModeLabel }} {{ replyDraft.sender }}
            </span>
            <span class="reply-preview">{{ replyDraft.preview }}</span>
            <button class="reply-cancel-btn" @click="clearReplyDraft" title="取消引用">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div v-if="pendingAttachments.length" class="attachment-tray">
            <div
              v-for="(attachment, index) in pendingAttachments"
              :key="attachment.id"
              class="pending-attachment"
              :class="`type-${attachment.type}`"
            >
              <img
                v-if="attachment.type === 'image'"
                :src="attachment.url"
                :alt="attachment.name"
                class="pending-image"
              />
              <i v-else class="fas fa-file"></i>
              <span class="pending-name">{{ attachment.name }}</span>
              <button class="pending-remove" @click="removePendingAttachment(index)" title="移除附件">
                <i class="fas fa-times"></i>
              </button>
            </div>
          </div>
          <div v-if="showEmojiPicker" class="emoji-picker">
            <button
              v-for="emoji in emojiChoices"
              :key="emoji"
              class="emoji-btn"
              @click="appendEmoji(emoji)"
            >
              {{ emoji }}
            </button>
          </div>
          <div v-if="showCodeInput" class="code-input-panel">
            <textarea
              v-model="codeDraft"
              class="code-input"
              placeholder="粘贴代码或配置..."
              spellcheck="false"
              @keydown.ctrl.enter.prevent="sendCodeBlock"
              @keydown.meta.enter.prevent="sendCodeBlock"
            ></textarea>
            <div class="code-input-actions">
              <button class="code-action-btn ghost" type="button" @click="showCodeInput = false">
                <i class="fas fa-xmark"></i>
                <span>取消</span>
              </button>
              <button class="code-action-btn secondary" type="button" :disabled="!codeDraft.trim()" @click="insertCodeBlock">
                <i class="fas fa-plus"></i>
                <span>插入</span>
              </button>
              <button class="code-action-btn primary" type="button" :disabled="!codeDraft.trim() || isSending" @click="sendCodeBlock">
                <i class="fas fa-paper-plane"></i>
                <span>发送代码</span>
              </button>
            </div>
          </div>
          <div class="composer-shell">
            <button class="tool-btn" @click="showEmojiPicker = !showEmojiPicker" title="表情">
              <i class="fas fa-face-smile"></i>
            </button>
            <button class="tool-btn" @click="toggleCodeInput" title="代码块">
              <i class="fas fa-code"></i>
            </button>
            <button
              class="tool-btn"
              :class="{ recording: isRecordingVoice }"
              :disabled="isUploadingAttachment || pendingAttachments.length >= maxPendingAttachments"
              @click="toggleVoiceRecording"
              :title="isRecordingVoice ? '停止录音' : '语音消息'"
            >
              <i :class="isRecordingVoice ? 'fas fa-stop' : 'fas fa-microphone'"></i>
            </button>
            <button
              class="tool-btn"
              :disabled="isUploadingAttachment || pendingAttachments.length >= maxPendingAttachments"
              @click="openFilePicker"
              title="添加图片或文件"
            >
              <i v-if="!isUploadingAttachment" class="fas fa-paperclip"></i>
              <i v-else class="fas fa-spinner fa-spin"></i>
            </button>
            <input
              ref="fileInputRef"
              class="hidden-file-input"
              type="file"
              multiple
              accept="image/jpeg,image/png,image/gif,image/webp,video/mp4,video/webm,video/quicktime,audio/webm,audio/ogg,audio/mpeg,audio/mp4,audio/wav,.pdf,.txt,.md,.zip,.doc,.docx,.xls,.xlsx,.ppt,.pptx"
              @change="onAttachmentSelected"
            />
            <textarea
              v-model="newMessage"
              class="message-input"
              placeholder="输入消息... Enter 发送，Shift+Enter 换行"
              @keydown.enter="handleComposerEnter"
              @keydown.down="onMentionArrow($event, 1)"
              @keydown.up="onMentionArrow($event, -1)"
              @keydown.esc="closeMentionPicker"
              @input="onComposerInput"
              maxlength="5000"
              ref="inputRef"
            ></textarea>
            <div v-if="mentionPicker.visible" class="mention-picker">
              <button
                v-for="(item, index) in mentionSuggestions"
                :key="item.type === 'all' ? 'mention-all' : item.user_id"
                class="mention-option"
                :class="{ active: index === mentionPicker.activeIndex }"
                type="button"
                @mousedown.prevent="selectMention(item)"
              >
                <span v-if="item.type === 'all'" class="mention-avatar mention-avatar-all">
                  <i class="fas fa-bullhorn"></i>
                </span>
                <img v-else class="mention-avatar" :src="item.avatar" :alt="item.username" />
                <span class="mention-meta">
                  <strong>{{ item.label || item.username }}</strong>
                  <em>{{ item.type === 'all' ? '通知所有群成员' : roleLabel(item.role) }}</em>
                </span>
              </button>
              <div v-if="!mentionSuggestions.length" class="mention-empty">没有匹配的成员</div>
            </div>
            <span class="char-count" :class="{ warn: newMessage.length > 4500 }">
              {{ newMessage.length }}/5000
            </span>
            <button
              class="send-btn"
              @click="sendMessage()"
              :disabled="isSending || isUploadingAttachment || (!newMessage.trim() && pendingAttachments.length === 0)"
            >
              <i v-if="!isSending" class="fas fa-paper-plane"></i>
              <i v-else class="fas fa-spinner fa-spin"></i>
              <span class="send-text">发送</span>
            </button>
          </div>
          <span class="shortcut-hint">
            {{ isRecordingVoice ? '正在录音，点击停止后会加入待发送附件' : 'Enter 发送 / Shift+Enter 换行' }}
          </span>
        </div>
      </div>
    </main>

    <!-- 对话项右键菜单 -->
    <div
      v-if="ctxMenu.visible"
      class="context-menu"
      :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
    >
      <button class="dm-item" @click="ctxAction('mark_read_toggle')">
        <i class="fas" :class="ctxMenu.conv?.unread_count > 0 || ctxMenu.conv?.force_unread ? 'fa-check-double' : 'fa-envelope'"></i>
        {{ ctxMenu.conv?.unread_count > 0 || ctxMenu.conv?.force_unread ? '标记为已读' : '标记为未读' }}
      </button>
      <button class="dm-item" @click="ctxAction('pin')">
        <i class="fas fa-thumbtack"></i>
        {{ ctxMenu.conv?.is_pinned ? '取消置顶' : '置顶会话' }}
      </button>
      <button class="dm-item" @click="ctxAction('mute')">
        <i class="fas" :class="ctxMenu.conv?.is_muted ? 'fa-bell' : 'fa-bell-slash'"></i>
        {{ ctxMenu.conv?.is_muted ? '取消免打扰' : '消息免打扰' }}
      </button>
      <button class="dm-item" @click="ctxAction('archive')">
        <i class="fas" :class="ctxMenu.conv?.is_archived ? 'fa-inbox' : 'fa-box-archive'"></i>
        {{ ctxMenu.conv?.is_archived ? '取消归档' : '归档会话' }}
      </button>
      <div class="dm-sep"></div>
      <button class="dm-item danger" @click="ctxAction('clear')">
        <i class="fas fa-eraser"></i> 清空记录
      </button>
      <button class="dm-item danger" @click="ctxAction('block')">
        <i class="fas fa-ban"></i> 拉黑用户
      </button>
    </div>

    <div
      v-if="messageCtxMenu.visible"
      class="context-menu"
      :style="{ left: messageCtxMenu.x + 'px', top: messageCtxMenu.y + 'px' }"
    >
      <button class="dm-item" @click="messageCtxAction('quote')">
        <i class="fas fa-quote-left"></i> 引用
      </button>
      <button class="dm-item" @click="messageCtxAction('multi_select')">
        <i class="fas fa-check-double"></i> 多选
      </button>
      <button class="dm-item" @click="messageCtxAction('forward')">
        <i class="fas fa-share"></i> 转发
      </button>
      <button class="dm-item" @click="messageCtxAction('copy')">
        <i class="fas fa-copy"></i> 复制
      </button>
      <button
        v-if="isCurrentGroup && canManageCurrentGroup"
        class="dm-item"
        @click="messageCtxAction('pin_group_message')"
      >
        <i class="fas fa-thumbtack"></i>
        {{ messageCtxMenu.msg?.is_pinned ? '取消置顶消息' : '置顶消息' }}
      </button>
      <button
        v-if="isCurrentGroup && messageCtxMenu.msg?.is_own"
        class="dm-item"
        @click="messageCtxAction('edit')"
      >
        <i class="fas fa-pen"></i> 编辑
      </button>
      <button class="dm-item" @click="messageCtxAction('report')">
        <i class="fas fa-flag"></i> 举报
      </button>
      <button class="dm-item danger" @click="messageCtxAction('delete')">
        <i class="fas fa-trash-alt"></i> 删除
      </button>
      <button
        v-if="messageCtxMenu.msg?.is_own && canRecallMessage(messageCtxMenu.msg)"
        class="dm-item danger"
        @click="messageCtxAction('recall')"
      >
        <i class="fas fa-rotate-left"></i> 撤回
      </button>
    </div>

    <!-- 寮圭獥 -->
    <NewMessageDialog
      v-if="showNewMessageDialog"
      @close="closeNewMessageDialog"
      @select="startNewConversation"
      @group-created="startGroupConversation"
    />

    <ChatSearchDrawer
      v-if="showChatSearch && selectedUserId && !isCurrentGroup"
      :peer-id="selectedUserId"
      @close="showChatSearch = false"
      @jump="jumpToMessage"
    />

    <ReportUserDialog
      v-if="reportTarget"
      :target-user-id="reportTarget.userId"
      :target-username="reportTarget.username"
      :message-id="reportTarget.messageId"
      :submit-url="reportTarget.submitUrl || ''"
      :message-snippet="reportTarget.snippet"
      :csrf-token="csrfToken"
      @close="reportTarget = null"
      @submitted="reportTarget = null"
    />

    <MergedForwardDialog
      v-if="mergedForwardDialog.visible"
      :payload="mergedForwardDialog.payload"
      :current-user-name="currentUserName()"
      @close="closeMergedForwardDialog"
    />

    <div v-if="groupPanel.visible" class="group-panel-overlay" @click.self="closeGroupInfo">
      <section class="group-panel">
        <header class="group-panel-header">
          <div class="group-panel-heading">
            <span class="group-panel-mark" aria-hidden="true">
              <i class="fas fa-users-gear"></i>
            </span>
            <div>
              <h3>群设置</h3>
              <p>{{ groupPanel.detail?.member_count || 0 }} 名成员</p>
            </div>
          </div>
          <button class="close-btn" type="button" title="关闭" @click="closeGroupInfo">
            <i class="fas fa-times"></i>
          </button>
        </header>

        <div v-if="groupPanel.loading" class="group-panel-state">
          <i class="fas fa-spinner fa-spin"></i>
          加载中...
        </div>

        <template v-else-if="groupPanel.detail">
          <div class="group-panel-content">
          <div v-if="groupPanel.detail.pinned_message" class="group-pinned-box">
            <div class="group-section-title">
              <span><i class="fas fa-thumbtack"></i> 置顶消息</span>
              <button
                v-if="canManageCurrentGroup"
                class="group-secondary-btn small"
                @click="togglePinnedGroupMessage(groupPanel.detail.pinned_message)"
              >
                取消置顶
              </button>
            </div>
            <button class="group-pinned-message" type="button" @click="closeGroupInfo">
              {{ groupMessagePreview(groupPanel.detail.pinned_message) || '[消息]' }}
            </button>
          </div>

          <div class="group-edit-row">
            <input
              v-model="groupPanel.nameDraft"
              class="group-input"
              type="text"
              maxlength="80"
              :disabled="!canManageCurrentGroup"
            />
            <button class="group-primary-btn" :disabled="!canManageCurrentGroup || !groupPanel.nameDraft.trim()" @click="saveGroupName">
              保存
            </button>
          </div>

          <div class="group-config-box">
            <div class="group-section-title">
              <span><i class="fas fa-bullhorn"></i> 群公告</span>
              <span v-if="groupPanel.detail.announcement_updated_by" class="group-section-meta">
                {{ groupPanel.detail.announcement_updated_by.username }} · {{ formatGroupDate(groupPanel.detail.announcement_pinned_at || groupPanel.detail.updated_at) }}
              </span>
            </div>
            <textarea
              v-model="groupPanel.announcementDraft"
              class="group-textarea"
              maxlength="2000"
              rows="3"
              :disabled="!canManageCurrentGroup"
              placeholder="暂无群公告"
            ></textarea>
            <div class="group-config-actions">
              <label class="group-check">
                <input v-model="groupPanel.announcementPinned" type="checkbox" :disabled="!canManageCurrentGroup" />
                <span>置顶公告</span>
              </label>
              <button
                v-if="canManageCurrentGroup"
                class="group-secondary-btn small"
                :disabled="!hasGroupAnnouncementChanges || groupPanel.savingAnnouncement"
                @click="saveGroupAnnouncement"
              >
                <i v-if="groupPanel.savingAnnouncement" class="fas fa-spinner fa-spin"></i>
                保存公告
              </button>
            </div>
            <div v-if="groupPanel.detail.announcement_history?.length" class="group-history-list">
              <div
                v-for="item in groupPanel.detail.announcement_history"
                :key="item.id"
                class="group-history-row"
                :class="{ pinned: item.pinned }"
              >
                <template v-if="groupPanel.editingAnnouncementId === item.id">
                  <textarea
                    v-model="groupPanel.announcementEditDraft"
                    class="group-textarea small"
                    maxlength="2000"
                    rows="3"
                  ></textarea>
                  <div class="group-history-actions">
                    <label class="group-check">
                      <input v-model="groupPanel.announcementEditPinned" type="checkbox" />
                      <span>置顶公告</span>
                    </label>
                    <span class="group-history-action-spacer"></span>
                    <button class="group-secondary-btn small" type="button" @click="cancelEditGroupAnnouncement">取消</button>
                    <button
                      class="group-primary-btn small"
                      type="button"
                      :disabled="!canSaveEditingAnnouncement(item)"
                      @click="updateGroupAnnouncement(item)"
                    >
                      <i v-if="groupPanel.savingAnnouncement" class="fas fa-spinner fa-spin"></i>
                      保存
                    </button>
                  </div>
                </template>
                <template v-else>
                  <div class="group-history-head">
                    <button class="group-history-jump" type="button" @click="jumpToGroupAnnouncement(item)">
                      <span>
                        {{ item.editor?.username || '系统' }} · {{ formatGroupDate(item.updated_at || item.created_at) }}
                      </span>
                      <strong v-if="item.pinned"><i class="fas fa-thumbtack"></i> 置顶</strong>
                    </button>
                    <div v-if="canManageCurrentGroup" class="group-history-actions compact">
                      <button class="group-icon-btn" type="button" title="编辑公告" @click="startEditGroupAnnouncement(item)">
                        <i class="fas fa-pen"></i>
                      </button>
                      <button
                        class="group-icon-btn"
                        type="button"
                        :title="item.pinned ? '取消置顶' : '置顶公告'"
                        @click="toggleGroupAnnouncementPin(item)"
                      >
                        <i class="fas fa-thumbtack"></i>
                      </button>
                      <button class="group-icon-btn danger" type="button" title="删除公告" @click="deleteGroupAnnouncement(item)">
                        <i class="fas fa-trash-alt"></i>
                      </button>
                    </div>
                  </div>
                  <button class="group-history-content" type="button" @click="jumpToGroupAnnouncement(item)">
                    {{ item.content || '清空公告' }}
                  </button>
                </template>
              </div>
            </div>
          </div>

          <div v-if="canManageCurrentGroup" class="group-config-box compact">
            <div class="group-section-title">
              <span><i class="fas fa-shield-halved"></i> 权限与入群</span>
              <button class="group-secondary-btn small" :disabled="groupPanel.savingPermissions" @click="saveGroupPermissions">
                <i v-if="groupPanel.savingPermissions" class="fas fa-spinner fa-spin"></i>
                保存
              </button>
            </div>
            <div class="group-toggle-grid">
              <label class="group-switch-row">
                <input v-model="groupPanel.detail.require_approval" type="checkbox" />
                <span>
                  <strong>入群审批</strong>
                  <em>邀请链接加入前需管理员同意</em>
                </span>
              </label>
              <label class="group-switch-row">
                <input v-model="groupPanel.detail.allow_member_mention_all" type="checkbox" />
                <span>
                  <strong>成员 @全体</strong>
                  <em>关闭后仅群主/管理员可 @全体</em>
                </span>
              </label>
              <label class="group-switch-row select-row">
                <span>
                  <strong>发言模式</strong>
                  <em>适合公告群或临时管控</em>
                </span>
                <select v-model="groupPanel.detail.mute_mode" class="group-select">
                  <option value="none">所有成员可发言</option>
                  <option value="admins_only">仅管理员可发言</option>
                </select>
              </label>
            </div>
          </div>

          <div v-if="canManageCurrentGroup" class="group-add-box">
            <div class="group-section-title subtle">
              <span><i class="fas fa-user-plus"></i> 添加成员</span>
            </div>
            <div class="group-add-search">
              <input
                v-model="groupPanel.searchInput"
                class="group-input"
                type="text"
                placeholder="搜索完整用户名 / 邮箱 / 搜索码"
                @keydown.enter.prevent="searchGroupInviteUser"
              />
              <button class="group-secondary-btn" :disabled="groupPanel.searchInput.trim().length < 3 || groupPanel.searching" @click="searchGroupInviteUser">
                <i :class="groupPanel.searching ? 'fas fa-spinner fa-spin' : 'fas fa-search'"></i>
              </button>
            </div>
            <button
              v-if="groupPanel.searchResult"
              class="group-member-row invite"
              type="button"
              @click="addGroupMember(groupPanel.searchResult)"
            >
              <img :src="groupPanel.searchResult.avatar" :alt="groupPanel.searchResult.username" />
              <span>{{ groupPanel.searchResult.username }}</span>
              <i class="fas fa-plus"></i>
            </button>
          </div>

          <div v-if="canManageCurrentGroup" class="group-invite-box">
            <div class="group-section-title">
              <span><i class="fas fa-link"></i> 邀请链接</span>
              <button
                class="group-secondary-btn small"
                :disabled="groupPanel.inviteBusy || groupPanel.inviteLoading || groupPanel.inviteLinks.length > 0"
                :title="groupPanel.inviteLinks.length > 0 ? '每个群组仅能创建一个邀请链接' : '新建邀请链接'"
                @click="createGroupInviteLink"
              >
                <i :class="groupPanel.inviteBusy ? 'fas fa-spinner fa-spin' : 'fas fa-link'"></i>
                {{ groupPanel.inviteLinks.length > 0 ? '已创建' : '新建' }}
              </button>
            </div>
            <div v-if="groupPanel.inviteLoading" class="group-inline-state">
              <i class="fas fa-spinner fa-spin"></i>
              加载中...
            </div>
            <div v-else-if="!groupPanel.inviteLinks.length" class="group-inline-state">暂无邀请链接</div>
            <div v-else class="group-invite-list">
              <div
                v-for="invite in groupPanel.inviteLinks"
                :key="invite.id"
                class="group-invite-row"
                :class="{ disabled: !invite.is_active }"
              >
                <div class="group-invite-meta">
                  <strong>{{ invite.is_active ? '可用链接' : '已失效链接' }}</strong>
                  <span>已使用 {{ invite.uses_count || 0 }} 次</span>
                </div>
                <button class="group-icon-btn" title="复制邀请链接" @click="copyGroupInviteLink(invite)">
                  <i class="fas fa-copy"></i>
                </button>
                <button
                  v-if="invite.is_active"
                  class="group-icon-btn danger"
                  title="撤销邀请链接"
                  @click="revokeGroupInviteLink(invite)"
                >
                  <i class="fas fa-ban"></i>
                </button>
              </div>
            </div>
          </div>

          <div class="group-members">
            <div class="group-section-title subtle member-title">
              <span><i class="fas fa-user-group"></i> 成员</span>
            </div>
            <div
              v-for="member in groupPanel.detail.members"
              :key="member.user_id"
              class="group-member-row"
            >
              <img :src="member.avatar" :alt="member.username" />
              <div class="group-member-meta">
                <strong>{{ member.username }}</strong>
                <span>
                  {{ roleLabel(member.role) }}<template v-if="member.is_self"> · 我</template>
                  <template v-if="member.is_group_muted"> · 禁言至 {{ formatMutedUntil(member.muted_until) }}</template>
                </span>
              </div>
              <div v-if="canManageGroupMember(member)" class="group-member-actions">
                <button
                  v-if="canChangeGroupRole(member)"
                  class="group-icon-btn"
                  :title="member.role === 'admin' ? '取消管理员' : '设为管理员'"
                  @click="setGroupMemberRole(member, member.role === 'admin' ? 'member' : 'admin')"
                >
                  <i :class="member.role === 'admin' ? 'fas fa-user' : 'fas fa-user-shield'"></i>
                </button>
                <div class="group-mute-menu-wrap" @click.stop>
                  <button
                    class="group-icon-btn"
                    :class="{ active: activeMuteMenuUserId === member.user_id, muted: member.is_group_muted }"
                    :title="member.is_group_muted ? '禁言设置' : '禁言时长'"
                    @click="toggleMuteMenu(member)"
                  >
                    <i :class="member.is_group_muted ? 'fas fa-microphone' : 'fas fa-microphone-slash'"></i>
                  </button>
                  <div
                    v-if="activeMuteMenuUserId === member.user_id"
                    class="group-mute-menu"
                    role="menu"
                  >
                    <button
                      v-if="member.is_group_muted"
                      class="group-mute-menu-item primary"
                      @click="unmuteGroupMember(member)"
                    >
                      <i class="fas fa-microphone"></i>
                      解除禁言
                    </button>
                    <div v-if="member.is_group_muted" class="group-mute-menu-separator"></div>
                    <div class="group-mute-menu-title">
                      {{ member.is_group_muted ? '延长禁言' : '禁言时长' }}
                    </div>
                    <button
                      v-for="option in muteDurationOptions"
                      :key="option.value"
                      class="group-mute-menu-item"
                      @click="muteGroupMember(member, option.value)"
                    >
                      {{ option.label }}
                    </button>
                  </div>
                </div>
                <button
                  v-if="canRemoveGroupMember(member)"
                  class="group-icon-btn danger"
                  title="移出群组"
                  @click="removeGroupMember(member)"
                >
                  <i class="fas fa-user-minus"></i>
                </button>
              </div>
              <button
                v-else-if="canRemoveGroupMember(member)"
                class="group-icon-btn danger"
                title="移出群组"
                @click="removeGroupMember(member)"
              >
                <i class="fas fa-user-minus"></i>
              </button>
            </div>
          </div>
          </div>

          <footer class="group-panel-footer">
            <button class="group-secondary-btn" @click="toggleGroupMute">
              <i class="fas" :class="currentSettings.is_muted ? 'fa-bell' : 'fa-bell-slash'"></i>
              {{ currentSettings.is_muted ? '取消免打扰' : '消息免打扰' }}
            </button>
            <button v-if="groupPanel.detail.viewer_role !== 'owner'" class="group-danger-btn" @click="leaveCurrentGroup">
              退出群组
            </button>
            <button v-else class="group-danger-btn" @click="dissolveCurrentGroup">
              解散群组
            </button>
          </footer>
        </template>

        <div v-else class="group-panel-state is-error">
          <i class="fas fa-circle-exclamation"></i>
          <strong>群设置加载失败</strong>
          <span>{{ groupPanel.error || '暂时无法获取群设置内容' }}</span>
          <button class="group-secondary-btn small" type="button" @click="openGroupInfo">
            重试
          </button>
        </div>
      </section>
    </div>

    <div v-if="peerProfile.visible" class="profile-card-overlay" @click.self="closePeerProfile">
      <section class="profile-card-modal">
        <button class="profile-card-close" type="button" title="关闭" @click="closePeerProfile">
          <i class="fas fa-times"></i>
        </button>

        <div class="profile-cover-media">
          <img
            v-if="peerProfile.data.banner_url && !peerProfile.data.banner_is_video"
            :src="peerProfile.data.banner_url"
            alt="封面"
            class="cover-img"
          />
          <video
            v-else-if="peerProfile.data.banner_url && peerProfile.data.banner_is_video"
            ref="peerProfileVideoRef"
            :src="peerProfile.data.banner_url"
            class="cover-img"
            autoplay
            loop
            playsinline
            :muted="peerProfile.videoMuted"
          ></video>
          <div v-else class="cover-gradient"></div>

          <div v-if="peerProfile.data.banner_is_video" class="cover-video-controls">
            <button class="cover-ctrl-btn" type="button" :title="peerProfile.videoPaused ? '播放' : '暂停'" @click.stop="togglePeerProfileVideo">
              <i :class="peerProfile.videoPaused ? 'fas fa-play' : 'fas fa-pause'"></i>
            </button>
            <div class="cover-volume-ctrl">
              <button class="cover-ctrl-btn" type="button" :title="peerProfile.videoMuted ? '开启声音' : '静音'" @click.stop="togglePeerProfileMute">
                <i :class="peerProfile.videoMuted ? 'fas fa-volume-mute' : 'fas fa-volume-up'"></i>
              </button>
              <div class="cover-volume-slider">
                <input v-model.number="peerProfile.videoVolume" type="range" min="0" max="1" step="0.01" @input="updatePeerProfileVolume" />
              </div>
            </div>
          </div>
        </div>

        <div class="profile-card-body">
          <img :src="peerProfile.data.avatar || '/static/img/default-avatar.png'" :alt="peerProfile.data.username" class="profile-card-avatar" />
          <h3>{{ peerProfile.data.username }}</h3>
          <p class="profile-card-bio">{{ peerProfile.data.bio || '暂无简介' }}</p>

          <div class="profile-card-stats">
            <a class="profile-stat" :href="peerProfile.data.public_notes_url || '#'">
              <strong>{{ peerProfile.data.notes_count || 0 }}</strong>
              <span>公开笔记</span>
            </a>
            <div class="profile-stat">
              <strong>{{ peerProfile.data.views_count || 0 }}</strong>
              <span>浏览</span>
            </div>
            <div class="profile-stat">
              <strong>{{ peerProfile.data.likes_count || 0 }}</strong>
              <span>点赞</span>
            </div>
          </div>

          <a class="public-notes-link" :href="peerProfile.data.public_notes_url || '#'">
            <i class="fas fa-book-open"></i>
            查看公开笔记
          </a>
        </div>
      </section>
    </div>

    <DisappearingSettingDialog
      v-if="showDisappearingDialog && selectedUserId && !isCurrentGroup"
      :peer-id="selectedUserId"
      :initial-enabled="currentSettings.disappearing_enabled"
      :initial-ttl="currentSettings.disappearing_ttl_seconds"
      :csrf-token="csrfToken"
      @close="showDisappearingDialog = false"
      @saved="onDisappearingSaved"
    />

    <!-- Turnstile 兜底：当日新对话超额时要求人机验证 -->
    <div v-if="turnstileGate.visible" class="turnstile-gate-overlay" @click.self="cancelTurnstileGate">
      <div class="turnstile-gate-card">
        <h3><i class="fas fa-shield-alt"></i> 请完成人机验证</h3>
        <p class="turnstile-gate-desc">
          你今天主动发起的新对话数量已达上限（{{ turnstileGate.quotaLimit || 5 }} 个）。
          请完成下方验证后继续发送。
        </p>
        <div class="turnstile-gate-body">
          <Turnstile
            v-if="turnstileGate.siteKey"
            :site-key="turnstileGate.siteKey"
            @verified="onTurnstileVerified"
            @error="onTurnstileError"
            @expired="onTurnstileExpired"
          />
          <div v-else class="turnstile-gate-loading">
            <i class="fas fa-spinner fa-spin"></i>
            加载验证组件中...
          </div>
        </div>
        <div class="turnstile-gate-actions">
          <button class="btn-ghost" @click="cancelTurnstileGate">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatWebSocket } from '@services/chatWebSocket'
import { getCsrfToken } from '@utils/csrf'
import { formatRelativeListDate } from '@utils/datetime'
import { escapeHtml, sanitizeHtml } from '@utils/sanitize'
import { extractApiErrorMessage } from '@utils/apiError'
import NewMessageDialog from '@components/messages/NewMessageDialog/index.vue'
import ConversationItem from '@components/messages/ConversationItem/index.vue'
import MessageBubble from '@components/messages/MessageBubble/index.vue'
import BlockedUsersPanel from '@components/messages/BlockedUsersPanel/index.vue'
import ChatSearchDrawer from '@components/messages/ChatSearchDrawer/index.vue'
import ReportUserDialog from '@components/messages/ReportUserDialog/index.vue'
import DisappearingSettingDialog from '@components/messages/DisappearingSettingDialog/index.vue'
import MergedForwardDialog from '@components/messages/MergedForwardDialog/index.vue'
import GroupInvitePreview from '@components/messages/GroupInvitePreview/index.vue'
import Turnstile from '@components/common/Turnstile/index.vue'
import {
  encodeMergedForward,
  mergedForwardPlainText,
  mergedForwardPreview,
  MERGED_FORWARD_MAX_ITEMS,
  parseMergedForward,
} from '@/utils/mergedForward'

// ==== 常量 ====
const recallWindowSeconds = 120

// ==== 状态 ====
const currentUserId = ref(0)
const csrfToken = ref('')
const scope = ref('all')
const conversations = ref([])
const loadingConversations = ref(false)
const selectedUserId = ref(null)
const selectedConversationKey = ref(null)
const messages = ref([])
const loadingMessages = ref(false)

// Group invite preview
const showGroupInvitePreview = ref(false)
const showAnnouncementJumpFailedDialog = ref(false)
const groupInviteToken = ref('')
const currentSettings = ref({
  is_pinned: false,
  is_muted: false,
  is_archived: false,
  disappearing_enabled: false,
  disappearing_ttl_seconds: 86400,
  force_unread: false,
})
const newMessage = ref('')
const isSending = ref(false)
const isUploadingAttachment = ref(false)
const isRecordingVoice = ref(false)
const messagesListRef = ref(null)
const inputRef = ref(null)
const fileInputRef = ref(null)
const peerProfileVideoRef = ref(null)
const showNewMessageDialog = ref(false)
const showChatMenu = ref(false)
const showChatSearch = ref(false)
const showDisappearingDialog = ref(false)
const reportTarget = ref(null)
const mergedForwardDialog = ref({ visible: false, payload: null })
const groupPanel = ref({
  visible: false,
  loading: false,
  error: '',
  detail: null,
  nameDraft: '',
  searchInput: '',
  searchResult: null,
  searching: false,
  inviteLoading: false,
  inviteBusy: false,
  inviteLinks: [],
  announcementDraft: '',
  announcementPinned: false,
  announcementOriginal: '',
  announcementPinnedOriginal: false,
  editingAnnouncementId: null,
  announcementEditDraft: '',
  announcementEditPinned: false,
  savingAnnouncement: false,
  memberSearch: '',
  memberRoleFilter: 'all',
  auditLoading: false,
  auditLogs: [],
  joinRequestsLoading: false,
  joinRequests: [],
  sharedLoading: false,
  sharedLinks: [],
  savingPermissions: false,
})
const activeMuteMenuUserId = ref(null)
const muteDurationOptions = [
  { label: '10 分钟', value: 10 },
  { label: '30 分钟', value: 30 },
  { label: '1 小时', value: 60 },
  { label: '3 小时', value: 180 },
  { label: '6 小时', value: 360 },
  { label: '24 小时', value: 1440 },
  { label: '永久禁言', value: 'permanent' },
]
const ctxMenu = ref({ visible: false, x: 0, y: 0, conv: null })
const messageCtxMenu = ref({ visible: false, x: 0, y: 0, msg: null })
const selectionMode = ref(false)
const selectedMessageIds = ref(new Set())
const typingIndicator = ref({ visible: false, username: '' })
const conversationDrafts = ref({})
const showScrollToBottom = ref(false)
const scrollBottomUnreadCount = ref(0)
const globalSearch = ref('')
const globalSearchResults = ref(null)
const highlightMessageId = ref(null)
const mobileChatOpen = ref(false)
const blockedPanelRef = ref(null)
const replyDraft = ref(null)
const forwardDraft = ref(null)
const browserNotificationsEnabled = ref(false)
let suppressConversationRefreshUntil = 0
const pendingAttachments = ref([])
const showEmojiPicker = ref(false)
const showCodeInput = ref(false)
const codeDraft = ref('')
const mentionPicker = ref({
  visible: false,
  query: '',
  start: -1,
  end: -1,
  activeIndex: 0,
})
const peerProfile = ref({
  visible: false,
  loading: false,
  videoMuted: true,
  videoPaused: false,
  videoVolume: 0.6,
  data: {},
})
const maxPendingAttachments = 6
const realtimeState = ref('disabled')
let voiceRecorder = null
let voiceStream = null
let voiceChunks = []
let chatSocket = null
// 客户端节流定时器：同一会话内 1.4s 最多发一次 typing
let typingThrottleTimer = null
// 接收端 hide 定时器：2s 收不到新的 typing 事件则隐藏指示器
let typingHideTimer = null
// 输入框上一次是否非空，用于检测"有内容 → 空"的跳变以发送 typing_stop
let composerWasNotEmpty = false

// Turnstile 兜底：当日新对话超额
const turnstileGate = ref({
  visible: false,
  siteKey: '',
  pendingContent: '',
  pendingAttachmentIds: [],
  pendingRecipientId: null,
  pendingForwardMessageId: null,
  pendingAutoSendChatlog: false,
  quotaLimit: 5,
})

const tabs = [
  { value: 'all', label: '全部', icon: 'fas fa-comments' },
  { value: 'unread', label: '未读', icon: 'fas fa-envelope' },
  { value: 'archived', label: '归档', icon: 'fas fa-box-archive' },
  { value: 'blocked', label: '屏蔽', icon: 'fas fa-ban' },
]

const emojiChoices = [
  '😀', '😄', '😂', '😊', '😍', '😘', '😎', '😭',
  '😡', '👍', '👏', '🙏', '🎉', '❤️', '🔥', '✨',
  '😅', '🤔', '👌', '💪', '🌹', '🍻', '💯', '😴',
]

// ==== 璁＄畻灞炴€?====
const selectedConversation = computed(() => {
  return findConversationByKey(selectedConversationKey.value)
})
// 后端可选增强字段：
// 1) selectedConversation.peer_online: Boolean 对方在线状态（无该字段时前端默认展示在线）
// 2) message.reply_to_id / reply_preview: 若要持久化引用关系，后端需返回并保存这些字段
// 3) message.is_read / message.read_at: 渲染消息底部已读状态（双勾）与已读时间
const peerOnline = computed(() => selectedConversation.value?.peer_online ?? true)

const isCurrentGroup = computed(() => selectedConversation.value?.conversation_type === 'group')

const canManageCurrentGroup = computed(() =>
  ['owner', 'admin'].includes(groupPanel.value.detail?.viewer_role || currentSettings.value.group_role || '')
)

const activeGroupAnnouncement = computed(() => {
  if (!isCurrentGroup.value) return null
  const groupId = selectedGroupId()
  const detail = groupPanel.value.detail?.id === groupId ? groupPanel.value.detail : null
  const detailAnnouncement = detail?.announcement_history?.find((item) => item.pinned) || detail?.announcement_history?.[0]
  if (detailAnnouncement?.content) {
    return {
      id: detailAnnouncement.id,
      content: detailAnnouncement.content,
      pinned: !!detailAnnouncement.pinned,
      message_id: detailAnnouncement.message_id,
      updated_at: detailAnnouncement.updated_at || detailAnnouncement.created_at,
    }
  }
  const conv = selectedConversation.value
  if (!conv?.announcement) return null
  return {
    id: null,
    content: conv.announcement,
    pinned: !!conv.announcement_pinned,
    message_id: conv.announcement_message_id,
    updated_at: conv.announcement_updated_at,
  }
})

const hasGroupAnnouncementChanges = computed(() => {
  if (!canManageCurrentGroup.value) return false
  return (
    groupPanel.value.announcementDraft !== groupPanel.value.announcementOriginal ||
    !!groupPanel.value.announcementPinned !== !!groupPanel.value.announcementPinnedOriginal
  )
})

const isCurrentGroupOwner = computed(() =>
  (groupPanel.value.detail?.viewer_role || currentSettings.value.group_role || '') === 'owner'
)

const filteredGroupMembers = computed(() => {
  const detail = groupPanel.value.detail
  if (!detail?.members) return []
  const q = groupPanel.value.memberSearch.trim().toLowerCase()
  const role = groupPanel.value.memberRoleFilter
  return detail.members.filter((member) => {
    const matchesRole = role === 'all' || member.role === role || (role === 'muted' && member.is_group_muted)
    const matchesText = !q || String(member.username || '').toLowerCase().includes(q)
    return matchesRole && matchesText
  })
})

const isGroupComposerBlocked = computed(() => {
  if (!isCurrentGroup.value) return false
  const conv = selectedConversation.value
  const muteMode = conv?.mute_mode || groupPanel.value.detail?.mute_mode
  if (muteMode !== 'admins_only') return false
  const role = groupPanel.value.detail?.viewer_role || currentSettings.value.group_role || ''
  return !['owner', 'admin'].includes(role)
})

const mentionMembers = computed(() => {
  if (!isCurrentGroup.value) return []
  const detail = groupPanel.value.detail
  if (!detail || normalizeUserId(detail.id) !== selectedGroupId()) return []
  const members = detail.members || []
  return members.filter((member) => !member.is_self)
})

const mentionSuggestions = computed(() => {
  if (!mentionPicker.value.visible) return []
  const query = mentionPicker.value.query.trim().toLowerCase()
  const suggestions = []
  if (!query || '全体成员'.includes(query) || 'all'.startsWith(query)) {
    suggestions.push({ type: 'all', label: '@全体成员', username: '全体成员' })
  }
  for (const member of mentionMembers.value) {
    const username = String(member.username || '')
    if (!query || username.toLowerCase().includes(query)) {
      suggestions.push({ ...member, type: 'member', label: `@${username}` })
    }
  }
  return suggestions.slice(0, 8)
})

const peerBlockedByMe = computed(() => !!selectedConversation.value?.is_blocked)

const totalUnread = computed(() =>
  conversations.value.reduce((s, c) => s + (c.unread_count || 0), 0)
)

const filteredConversations = computed(() => conversations.value)

const hasUnread = computed(
  () => (selectedConversation.value?.unread_count || 0) > 0
)

const replyModeLabel = computed(() => '引用')

const emptyStateIcon = computed(() => {
  if (scope.value === 'unread') return 'fas fa-envelope-open'
  if (scope.value === 'archived') return 'fas fa-box-archive'
  return 'fas fa-inbox'
})

const emptyStateText = computed(() => {
  if (scope.value === 'unread') return '没有未读消息'
  if (scope.value === 'archived') return '暂无归档会话'
  return '还没有私信'
})

const groupedMessages = computed(() => {
  const groups = []
  let lastDate = null
  for (const m of messages.value) {
    const d = new Date(m.created_at)
    const today = new Date()
    const dateKey = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
    let label
    const diff = Math.floor(
      (new Date(today.getFullYear(), today.getMonth(), today.getDate()) -
        new Date(d.getFullYear(), d.getMonth(), d.getDate())) /
        86400000
    )
    const timeText = `${String(d.getHours()).padStart(2, '0')}:${String(
      d.getMinutes()
    ).padStart(2, '0')}`
    if (diff === 0) label = `今天 ${timeText}`
    else if (diff === 1) label = `昨天 ${timeText}`
    else if (diff < 7) {
      const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
      label = `${weekdays[d.getDay()]} ${timeText}`
    } else label = `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()} ${timeText}`

    if (dateKey !== lastDate) {
      groups.push({ date: label, messages: [] })
      lastDate = dateKey
    }
    groups[groups.length - 1].messages.push(m)
  }
  return groups
})

function getUserId() {
  return (
    window.currentUserId ||
    parseInt(document.querySelector('meta[name="user-id"]')?.content || '0')
  )
}

function draftStorageKey() {
  return `message_drafts:${currentUserId.value || getUserId()}`
}

function loadDraftsFromStorage() {
  try {
    conversationDrafts.value = JSON.parse(localStorage.getItem(draftStorageKey()) || '{}') || {}
  } catch {
    conversationDrafts.value = {}
  }
}

function persistDrafts() {
  localStorage.setItem(draftStorageKey(), JSON.stringify(conversationDrafts.value))
}

function currentDraftKey() {
  return selectedConversationKey.value || ''
}

function saveCurrentDraft() {
  const key = currentDraftKey()
  if (!key) return
  const next = { ...conversationDrafts.value }
  const draft = newMessage.value.trim() ? newMessage.value : ''
  if (draft) next[key] = draft
  else delete next[key]
  conversationDrafts.value = next
  persistDrafts()
}

function applyDraftForConversation(peerId) {
  const key = typeof peerId === 'string' ? peerId : String(normalizeUserId(peerId) || '')
  newMessage.value = key ? (conversationDrafts.value[key] || '') : ''
  nextTick(autoGrowComposer)
}

function clearDraftForConversation(peerId) {
  const key = typeof peerId === 'string' ? peerId : String(normalizeUserId(peerId) || '')
  if (!key || !(key in conversationDrafts.value)) return
  const next = { ...conversationDrafts.value }
  delete next[key]
  conversationDrafts.value = next
  persistDrafts()
}

function normalizeUserId(value) {
  const normalized = Number(value)
  return Number.isFinite(normalized) && normalized > 0 ? normalized : null
}

function conversationKey(conv) {
  if (!conv) return ''
  if (conv.conversation_type === 'group') return `group:${conv.group_id}`
  const userId = normalizeUserId(conv.user_id)
  return userId ? `user:${userId}` : ''
}

function groupIdFromKey(key) {
  const match = String(key || '').match(/^group:(\d+)$/)
  return match ? Number(match[1]) : null
}

function selectedGroupId() {
  return groupIdFromKey(selectedConversationKey.value)
}

function findConversationByUserId(userId) {
  const normalizedUserId = normalizeUserId(userId)
  return conversations.value.find((c) => normalizeUserId(c.user_id) === normalizedUserId)
}

function findConversationByKey(key) {
  if (!key) return null
  return conversations.value.find((c) => conversationKey(c) === key) || null
}

function patchConversationByKey(key, patch) {
  const conv = findConversationByKey(key)
  if (!conv) return null
  Object.assign(conv, patch)
  conversations.value = [...conversations.value]
  return conv
}

function suppressNextConversationRefresh(ms = 4000) {
  suppressConversationRefreshUntil = Date.now() + ms
}

function conversationVersion(conv) {
  if (!conv) return ''
  return [
    conversationTimestamp(conv),
    conv.last_message || '',
    conv.last_sender_id || '',
    conv.unread_count || 0,
  ].join('|')
}

function applyDraftPreviews() {
  for (const conv of conversations.value) {
    const draft = conversationDrafts.value[conversationKey(conv)]
    conv.draft_preview = draft || ''
  }
}

function resolveRealtimePeerId(event, message) {
  const currentId = normalizeUserId(currentUserId.value || getUserId())
  const explicitPeerId = normalizeUserId(event?.peer_id)
  if (explicitPeerId) return explicitPeerId

  const senderId = normalizeUserId(message?.sender_id)
  const recipientId = normalizeUserId(message?.recipient_id)
  if (senderId && senderId !== currentId) return senderId
  if (recipientId && recipientId !== currentId) return recipientId
  return senderId || recipientId
}

function eventBelongsToSelectedConversation(event, message) {
  if (selectedConversationKey.value?.startsWith('group:')) {
    return normalizeUserId(event?.group_id || message?.group_id) === selectedGroupId()
  }
  const selectedId = normalizeUserId(selectedUserId.value)
  if (!selectedId) return false
  return [
    event?.peer_id,
    message?.peer_id,
    message?.sender_id,
    message?.recipient_id,
  ].some((value) => normalizeUserId(value) === selectedId)
}

async function apiPost(url, body) {
  return apiRequest(url, { method: 'POST', body })
}

async function apiRequest(url, { method = 'GET', body = null } = {}) {
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken.value,
    },
  }
  if (body !== null && body !== undefined) options.body = JSON.stringify(body || {})
  const r = await fetch(url, options)
  const d = await r.json().catch(() => ({}))
  if (!r.ok) {
    const err = new Error(extractApiErrorMessage(d, '请求失败'))
    err.status = r.status
    err.data = d
    throw err
  }
  return d
}

function isRealtimeEnabled() {
  return !!window.MESSAGE_REALTIME?.enabled
}

function normalizeIncomingMessage(message) {
  const mergedForward = message?.merged_forward || parseMergedForward(message?.content)
  const contentPreview = message?.content_preview || mergedForwardPreview(message?.content, '')
  return {
    ...message,
    attachments: Array.isArray(message?.attachments) ? message.attachments : [],
    merged_forward: mergedForward,
    content_preview: contentPreview,
  }
}

function upsertConversationPreviewFromMessage(message, peerId, { preserveOrder = false } = {}) {
  const normalizedPeerId = normalizeUserId(peerId)
  if (!normalizedPeerId) return
  const existing = findConversationByUserId(normalizedPeerId)
  const isActiveConversation =
    normalizeUserId(selectedUserId.value) === normalizedPeerId && !document.hidden
  const preview =
    mergedForwardPreview(message.content, '') ||
    String(message.content || '').trim() ||
    message.attachments?.[0]?.name ||
    '[附件]'
  const nextUnreadCount = message.is_own || isActiveConversation
    ? 0
    : ((existing?.unread_count || 0) + 1)
  const patch = {
    user_id: normalizedPeerId,
    username: existing?.username || selectedConversation.value?.username || '',
    avatar: existing?.avatar || selectedConversation.value?.avatar || '/static/img/default-avatar.png',
    last_message: preview,
    draft_preview: existing?.draft_preview || '',
    last_message_time: message.created_at,
    last_sender_id: message.sender_id,
    unread_count: nextUnreadCount,
    is_pinned: existing?.is_pinned || false,
    pinned_at: existing?.pinned_at || null,
    is_muted: existing?.is_muted || false,
    is_archived: false,
    disappearing_enabled: existing?.disappearing_enabled || false,
    force_unread: existing?.force_unread || false,
    is_blocked: existing?.is_blocked || false,
  }

  if (existing) {
    Object.assign(existing, patch)
  } else {
    conversations.value.unshift(patch)
  }

  if (preserveOrder) {
    conversations.value = [...conversations.value]
    return
  }

  conversations.value = [...conversations.value].sort((a, b) => {
    const aPinned = a.is_pinned ? 1 : 0
    const bPinned = b.is_pinned ? 1 : 0
    if (aPinned !== bPinned) return bPinned - aPinned
    const aPinnedAt = a.pinned_at ? new Date(a.pinned_at).getTime() : 0
    const bPinnedAt = b.pinned_at ? new Date(b.pinned_at).getTime() : 0
    if (aPinnedAt !== bPinnedAt) return bPinnedAt - aPinnedAt
    return conversationTimestamp(b) - conversationTimestamp(a)
  })
}

function handleRealtimeEvent(event) {
  if (!event?.type) return

  if (event.type === 'new_message' && event.message) {
    const incomingMessage = normalizeIncomingMessage(event.message)
    const peerId = resolveRealtimePeerId(event, incomingMessage)
    const isCurrentConversation = eventBelongsToSelectedConversation(event, incomingMessage)
    const exists = messages.value.some((message) => message.id === incomingMessage.id)

    if (isCurrentConversation && !exists) {
      messages.value.push(incomingMessage)
      const currentConv = findConversationByUserId(selectedUserId.value)
      if (currentConv) currentConv.unread_count = 0
      currentSettings.value.force_unread = false
      if (showScrollToBottom.value) scrollBottomUnreadCount.value += 1
      else scrollToBottomSoon()
    }

    if (isCurrentConversation) {
      loadMessages({ silent: true })
    }

    upsertConversationPreviewFromMessage(incomingMessage, peerId, {
      preserveOrder: !!incomingMessage.is_own,
    })
    return
  }

  if (event.type === 'message_read') {
    const ids = new Set(event.message_ids || [])
    if (ids.size > 0) {
      messages.value = messages.value.map((message) =>
        ids.has(message.id)
          ? { ...message, is_read: true, read_at: new Date().toISOString() }
          : message
      )
    }
    const peerId = normalizeUserId(event.peer_id)
    if (peerId) {
      const conv = conversations.value.find((item) => normalizeUserId(item.user_id) === peerId)
      if (conv) conv.unread_count = 0
    }
    return
  }

  if (event.type === 'message_recalled' && event.message_id) {
    messages.value = messages.value.filter((message) => message.id !== event.message_id)
    loadConversations({ silent: true })
    return
  }

  if (event.type === 'typing') {
    const peerId = normalizeUserId(event.peer_id)
    if (peerId !== normalizeUserId(selectedUserId.value) || document.hidden) return
    typingIndicator.value = {
      visible: true,
      username: event.username || selectedConversation.value?.username || '',
    }
    clearTimeout(typingHideTimer)
    typingHideTimer = window.setTimeout(() => {
      typingIndicator.value = { visible: false, username: '' }
    }, 2000)
    scrollToBottomSoon()
    return
  }

  if (event.type === 'typing_stop') {
    const peerId = normalizeUserId(event.peer_id)
    if (peerId !== normalizeUserId(selectedUserId.value)) return
    // 对方停止输入或发送了消息，立即隐藏指示器，不再等 2 秒 timeout
    hideTypingIndicator()
  }
}

function initRealtimeMessages() {
  if (!isRealtimeEnabled()) {
    realtimeState.value = 'disabled'
    return
  }
  chatSocket = new ChatWebSocket({
    path: window.MESSAGE_REALTIME?.wsPath || '/ws/messages/',
    onStatusChange: (status) => {
      realtimeState.value = status
    },
    onEvent: handleRealtimeEvent,
    onMaxReconnectReached: () => {
      ElMessage.warning('实时消息连接失败，已切换为轮询刷新')
    },
  })
  chatSocket.connect()
}

function syncConversations(nextConversations, { preserveOrder = false } = {}) {
  const existingByUserId = new Map(
    conversations.value.map((conversation) => [conversationKey(conversation), conversation])
  )
  if (preserveOrder) {
    const nextByUserId = new Map(
      nextConversations.map((conversation) => [conversationKey(conversation), conversation])
    )
    const merged = conversations.value
      .map((existing) => {
        const nextConversation = nextByUserId.get(conversationKey(existing))
        if (!nextConversation) return existing
        for (const key of Object.keys(existing)) {
          if (!(key in nextConversation)) delete existing[key]
        }
        Object.assign(existing, nextConversation)
        return existing
      })
      .filter((conversation) => nextByUserId.has(conversationKey(conversation)))

    for (const nextConversation of nextConversations) {
      if (!existingByUserId.has(conversationKey(nextConversation))) {
        merged.push(nextConversation)
      }
    }

    conversations.value = merged
    return
  }

  const merged = nextConversations.map((nextConversation) => {
    const existing = existingByUserId.get(conversationKey(nextConversation))
    if (!existing) return nextConversation
    for (const key of Object.keys(existing)) {
      if (!(key in nextConversation)) delete existing[key]
    }
    Object.assign(existing, nextConversation)
    return existing
  })
  conversations.value = merged
}

function conversationTimestamp(conv) {
  const ts = new Date(conv?.last_message_time || '').getTime()
  return Number.isFinite(ts) ? ts : 0
}

let notificationSnapshotReady = false
let notificationSnapshot = new Map()

function updateBrowserNotificationSnapshot(nextConversations) {
  const nextSnapshot = new Map()
  for (const conv of nextConversations) {
    nextSnapshot.set(conversationKey(conv), conversationTimestamp(conv))
  }

  if (!notificationSnapshotReady) {
    notificationSnapshot = nextSnapshot
    notificationSnapshotReady = true
    return
  }

  const canNotify =
    browserNotificationsEnabled.value &&
    typeof window !== 'undefined' &&
    'Notification' in window &&
    Notification.permission === 'granted'

  if (canNotify) {
    for (const conv of nextConversations) {
      const key = conversationKey(conv)
      const latestTs = nextSnapshot.get(key) || 0
      const previousTs = notificationSnapshot.get(key) || 0
      const isIncoming = conv.last_sender_id && conv.last_sender_id !== currentUserId.value
      const hasUnread = (conv.unread_count || 0) > 0
      const isCurrentVisibleConversation = selectedConversationKey.value === key && !document.hidden

      if (
        latestTs > previousTs &&
        isIncoming &&
        hasUnread &&
        !conv.is_muted &&
        !isCurrentVisibleConversation
      ) {
        showBrowserMessageNotification(conv)
      }
    }
  }

  notificationSnapshot = nextSnapshot
}

function showBrowserMessageNotification(conv) {
  const preview = String(conv.last_message || '').replace(/\s+/g, ' ').slice(0, 120)
  const key = conversationKey(conv)
  try {
    const notification = new Notification(`来自 ${conv.username} 的新私信`, {
      body: preview || '你收到了一条新消息',
      icon: conv.avatar || '/static/img/default-avatar.png',
      tag: `dm-${key}`,
      renotify: true,
    })
    notification.onclick = () => {
      window.focus()
      scope.value = 'all'
      selectedConversationKey.value = key
      selectedUserId.value = conv.conversation_type === 'group' ? null : conv.user_id
      mobileChatOpen.value = true
      loadMessages()
      loadConversations()
      notification.close()
    }
  } catch (e) {
    console.warn('浏览器通知显示失败:', e)
  }
}

async function loadNotificationPreferences() {
  try {
    const r = await fetch('/api/notification-preferences/')
    if (!r.ok) return
    const data = await r.json()
    browserNotificationsEnabled.value = !!data.preferences?.browser_enabled
  } catch (e) {
    console.warn('加载通知偏好失败:', e)
  }
}

// ==== 加载 ====
async function loadConversations({ silent = false, preserveOrder = false } = {}) {
  if (scope.value === 'blocked') {
    blockedPanelRef.value?.reload?.()
    conversations.value = []
    return
  }
  if (silent && Date.now() < suppressConversationRefreshUntil) return
  if (!silent) loadingConversations.value = true
  try {
    const selectedId = normalizeUserId(selectedUserId.value)
    const selectedKey = selectedConversationKey.value
    const previousSelectedVersion = selectedKey
      ? conversationVersion(findConversationByKey(selectedKey))
      : ''
    const r = await fetch(`/api/messages/conversations/?scope=${scope.value}`)
    if (r.ok) {
      const d = await r.json()
      const nextConversations = d.conversations || []
      updateBrowserNotificationSnapshot(nextConversations)
      syncConversations(nextConversations, { preserveOrder })
      applyDraftPreviews()
      const currentSelected = selectedKey ? findConversationByKey(selectedKey) : null
      const nextSelectedVersion = conversationVersion(currentSelected)
      if (
        selectedKey &&
        currentSelected &&
        previousSelectedVersion &&
        nextSelectedVersion &&
        previousSelectedVersion !== nextSelectedVersion
      ) {
        currentSelected.unread_count = 0
        currentSettings.value.force_unread = false
        loadMessages({ silent: true })
      }
    }
  } catch (e) {
    console.error(e)
  } finally {
    if (!silent) loadingConversations.value = false
  }
}

async function loadMessages({ silent = false } = {}) {
  if (!selectedConversationKey.value) return
  if (!silent) loadingMessages.value = true
  try {
    const groupId = selectedGroupId()
    const url = groupId
      ? `/api/messages/groups/${groupId}/messages/`
      : `/api/messages/get/?user_id=${selectedUserId.value}`
    const r = await fetch(url)
    if (r.ok) {
      const d = await r.json()
      messages.value = (d.messages || []).map(normalizeIncomingMessage)
      if (d.settings) {
        currentSettings.value = { ...currentSettings.value, ...d.settings }
      }
      if (d.group) {
        const conv = findConversationByKey(selectedConversationKey.value)
        if (conv) {
          conv.mute_mode = d.group.mute_mode
          conv.description = d.group.description
          conv.announcement = d.group.announcement
          syncConversationAnnouncementFromGroup(d.group)
        }
      }
      scrollToBottomSoon()
    }
  } catch (e) {
    console.error(e)
  } finally {
    if (!silent) loadingMessages.value = false
  }
}

// ==== 选择与发送 ====
function selectConversation(conv) {
  if (conv.is_blocked) {
    // 在“屏蔽”Tab下点击仅展示提示
    ElMessage.info('此用户已被你屏蔽')
    return
  }
  saveCurrentDraft()
  selectedConversationKey.value = conversationKey(conv)
  selectedUserId.value = conv.conversation_type === 'group' ? null : conv.user_id
  hideTypingIndicator()
  selectionMode.value = false
  clearSelectedMessages()
  applyDraftForConversation(selectedConversationKey.value)
  pendingAttachments.value = []
  showEmojiPicker.value = false
  closeMentionPicker()
  forwardDraft.value = null
  replyDraft.value = null
  highlightMessageId.value = null
  showChatMenu.value = false
  closeMessageCtxMenu()
  mobileChatOpen.value = true
  loadMessages()
}

async function sendMessage(turnstileToken = '') {
  if ((!newMessage.value.trim() && pendingAttachments.value.length === 0) || !selectedConversationKey.value) return
  // 用户提交消息后，立即让对方屏幕清除"正在输入"提示，不必等 2s timeout
  sendTypingStop()
  composerWasNotEmpty = false
  isSending.value = true
  const normalizedTurnstileToken = typeof turnstileToken === 'string' ? turnstileToken : ''
  const attachmentIds = pendingAttachments.value.map((attachment) => attachment.id)
  const finalContent = replyDraft.value
    ? buildQuotedMessage(replyDraft.value, newMessage.value.trim())
    : newMessage.value.trim()
  try {
    const groupId = selectedGroupId()
    if (groupId) {
      await ensureGroupMembersForMention()
      const mentionPayload = buildMentionPayload(finalContent)
      const d = await apiPost(`/api/messages/groups/${groupId}/send/`, {
        content: finalContent,
        attachment_ids: attachmentIds,
        ...mentionPayload,
      })
      const sentMessage = normalizeIncomingMessage(d.message)
      if (!messages.value.some((message) => message.id === sentMessage.id)) {
        messages.value.push(sentMessage)
      }
      clearDraftForConversation(selectedConversationKey.value)
      newMessage.value = ''
      applyDraftPreviews()
      pendingAttachments.value = []
      showEmojiPicker.value = false
      closeMentionPicker()
      replyDraft.value = null
      forwardDraft.value = null
      resetComposerHeight()
      await nextTick()
      scrollToBottomSoon()
      loadConversations({ silent: true, preserveOrder: true })
      return
    }
    if (forwardDraft.value?.sourceMessageId && attachmentIds.length === 0) {
      const forwardedMessage = await sendForwardedMessage(
        forwardDraft.value.sourceMessageId,
        selectedUserId.value,
        finalContent,
        normalizedTurnstileToken
      )
      clearDraftForConversation(selectedUserId.value)
      newMessage.value = ''
      applyDraftPreviews()
      pendingAttachments.value = []
      showEmojiPicker.value = false
      replyDraft.value = null
      forwardDraft.value = null
      resetComposerHeight()
      await nextTick()
      scrollToBottomSoon()
      upsertConversationPreviewFromMessage(forwardedMessage, selectedUserId.value, { preserveOrder: true })
      return
    }
    const payload = {
      recipient_id: selectedUserId.value,
      content: finalContent,
      attachment_ids: attachmentIds,
    }
    if (normalizedTurnstileToken) payload.turnstile_token = normalizedTurnstileToken
    const d = await apiPost('/api/messages/send/', payload)
    const sentMessage = normalizeIncomingMessage(d.message)
    if (!messages.value.some((message) => message.id === sentMessage.id)) {
      messages.value.push(sentMessage)
    }
    clearDraftForConversation(selectedUserId.value)
    newMessage.value = ''
    applyDraftPreviews()
    pendingAttachments.value = []
    showEmojiPicker.value = false
    replyDraft.value = null
    resetComposerHeight()
    await nextTick()
    scrollToBottomSoon()
    upsertConversationPreviewFromMessage(sentMessage, selectedUserId.value, { preserveOrder: true })
    loadConversations({ silent: true, preserveOrder: true })
  } catch (e) {
    if (e?.data?.need_turnstile) {
      await openTurnstileGate(finalContent, selectedUserId.value, e.data.quota_limit, attachmentIds)
      return
    }
    ElMessage.error(e.message)
  } finally {
    isSending.value = false
  }
}

async function sendForwardedMessage(sourceMessageId, recipientId, content, turnstileToken = '') {
  const payload = {
    message_id: sourceMessageId,
    recipient_id: recipientId,
    content,
  }
  if (turnstileToken) payload.turnstile_token = turnstileToken
  const d = await apiPost('/api/messages/forward/', payload)
  const forwardedMessage = normalizeIncomingMessage(d.message)
  if (normalizeUserId(selectedUserId.value) === normalizeUserId(recipientId)) {
    if (!messages.value.some((message) => message.id === forwardedMessage.id)) {
      messages.value.push(forwardedMessage)
    }
    scrollToBottomSoon()
  }
  upsertConversationPreviewFromMessage(forwardedMessage, recipientId, { preserveOrder: true })
  loadConversations({ silent: true, preserveOrder: true })
  return forwardedMessage
}

async function openTurnstileGate(pendingContent, recipientId, quotaLimit, pendingAttachmentIds = [], options = {}) {
  turnstileGate.value = {
    visible: true,
    siteKey: turnstileGate.value.siteKey || '',
    pendingContent,
    pendingAttachmentIds,
    pendingRecipientId: recipientId,
    pendingForwardMessageId: options.forwardMessageId ?? forwardDraft.value?.sourceMessageId ?? null,
    pendingAutoSendChatlog: Boolean(options.autoSendChatlog),
    quotaLimit: quotaLimit || 5,
  }
  if (!turnstileGate.value.siteKey) {
    try {
      const r = await fetch('/api/turnstile/config/')
      if (r.ok) {
        const d = await r.json()
        turnstileGate.value.siteKey = d.site_key || d.siteKey || ''
      }
    } catch (err) {
      console.error('加载 Turnstile 配置失败:', err)
    }
  }
}

function cancelTurnstileGate() {
  const wasAutoSendChatlog = turnstileGate.value.pendingAutoSendChatlog
  turnstileGate.value.visible = false
  turnstileGate.value.pendingContent = ''
  turnstileGate.value.pendingAttachmentIds = []
  turnstileGate.value.pendingRecipientId = null
  turnstileGate.value.pendingForwardMessageId = null
  turnstileGate.value.pendingAutoSendChatlog = false
  if (wasAutoSendChatlog) forwardDraft.value = null
  ElMessage.info('已取消人机验证，消息未发送')
}

async function onTurnstileVerified(token) {
  const pending = turnstileGate.value.pendingContent
  const pendingAttachmentIds = [...(turnstileGate.value.pendingAttachmentIds || [])]
  const pendingRecipient = turnstileGate.value.pendingRecipientId
  const pendingForwardMessageId = turnstileGate.value.pendingForwardMessageId
  const pendingAutoSendChatlog = turnstileGate.value.pendingAutoSendChatlog
  const normalizedTurnstileToken = typeof token === 'string' ? token : ''
  turnstileGate.value.visible = false
  if (!normalizedTurnstileToken || (!pending && pendingAttachmentIds.length === 0) || !pendingRecipient) return
  // 保持现有输入不动，直接用暂存内容 + token 重新投递
  isSending.value = true
  try {
    if (pendingAutoSendChatlog && pendingAttachmentIds.length === 0) {
      await sendChatlogForwardToUser(pendingRecipient, pending, normalizedTurnstileToken)
      return
    }
    if (pendingForwardMessageId && pendingAttachmentIds.length === 0) {
      const forwardedMessage = await sendForwardedMessage(
        pendingForwardMessageId,
        pendingRecipient,
        pending,
        normalizedTurnstileToken
      )
      clearDraftForConversation(pendingRecipient)
      newMessage.value = ''
      applyDraftPreviews()
      pendingAttachments.value = []
      replyDraft.value = null
      forwardDraft.value = null
      resetComposerHeight()
      scrollToBottomSoon()
      upsertConversationPreviewFromMessage(forwardedMessage, pendingRecipient, { preserveOrder: true })
      return
    }
    const d = await apiPost('/api/messages/send/', {
      recipient_id: pendingRecipient,
      content: pending,
      attachment_ids: pendingAttachmentIds,
      turnstile_token: normalizedTurnstileToken,
    })
    const sentMessage = normalizeIncomingMessage(d.message)
    if (!messages.value.some((message) => message.id === sentMessage.id)) {
      messages.value.push(sentMessage)
    }
    clearDraftForConversation(pendingRecipient)
    newMessage.value = ''
    applyDraftPreviews()
    pendingAttachments.value = []
    replyDraft.value = null
    resetComposerHeight()
    scrollToBottomSoon()
    upsertConversationPreviewFromMessage(sentMessage, pendingRecipient, { preserveOrder: true })
    loadConversations({ silent: true, preserveOrder: true })
  } catch (e) {
    ElMessage.error(e.message || '验证通过但发送失败，请稍后重试')
  } finally {
    isSending.value = false
    turnstileGate.value.pendingContent = ''
    turnstileGate.value.pendingAttachmentIds = []
    turnstileGate.value.pendingRecipientId = null
    turnstileGate.value.pendingForwardMessageId = null
    turnstileGate.value.pendingAutoSendChatlog = false
  }
}

function onTurnstileError() {
  ElMessage.error('人机验证出错，请重试')
}

function onTurnstileExpired() {
  ElMessage.warning('验证已过期，请重新验证')
}

function createReplyDraft(m, mode = 'quote') {
  const previewText = getReadableMessageText(m)
  return {
    id: m.id,
    mode,
    sender: m.sender || '对方',
    preview: singleLine(previewText).slice(0, 60),
  }
}

function buildQuotedMessage(draft, messageText) {
  return `> 引用 @${draft.sender}: ${draft.preview}\n\n${messageText}`
}

function buildForwardMessage(m) {
  const senderLabel = m?.is_own ? '我' : m?.sender || '对方'
  const timeLabel = formatForwardTime(m?.created_at)
  return `【转发自 ${senderLabel}${timeLabel ? ` ${timeLabel}` : ''}】\n${getReadableMessageText(m)}`
}

function buildChatlogForward(messagesToForward) {
  if (messagesToForward.length > MERGED_FORWARD_MAX_ITEMS) {
    throw new Error(`每次最多只能合并转发 ${MERGED_FORWARD_MAX_ITEMS} 条消息`)
  }
  const peerName = selectedConversation.value?.username || '对方'
  const items = [...messagesToForward]
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    .map((message) => {
      const senderLabel = message.is_own ? currentUserName() : (message.sender || peerName || '对方')
      const mergedForward = parseMergedForward(message.content)
      const text = mergedForward
        ? mergedForwardPlainText(message.content, mergedForwardPreview(message.content, ''))
        : (String(message.content || '').trim() || attachmentSummary(message))
      const preview = singleLine(text).slice(0, 220)
      return {
        id: message.id,
        sender: senderLabel,
        avatar: message.sender_avatar || '/static/img/default-avatar.png',
        is_own: !!message.is_own,
        content: text || '[附件]',
        preview: preview || '[附件]',
        time: message.created_at,
        attachments: Array.isArray(message.attachments) ? message.attachments : [],
      }
    })
  return encodeMergedForward({
    type: 'merged_forward',
    title: `${currentUserName()}与${peerName}的聊天记录`,
    source: `共 ${items.length} 条聊天记录`,
    count: items.length,
    items,
  })
}

function attachmentSummary(message) {
  const attachments = Array.isArray(message?.attachments) ? message.attachments : []
  if (!attachments.length) return ''
  return attachments
    .map((attachment) => `[附件] ${attachment.name || '未命名文件'}`)
    .join('\n')
}

function singleLine(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function getReadableMessageText(message) {
  return (
    mergedForwardPreview(message?.content, '') ||
    String(message?.content || '').trim() ||
    attachmentSummary(message) ||
    '[附件]'
  )
}

function currentUserName() {
  return (
    window.currentUsername ||
    document.querySelector('meta[name="username"]')?.content ||
    '我'
  )
}

function formatForwardTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function openFilePicker() {
  if (isUploadingAttachment.value || pendingAttachments.value.length >= maxPendingAttachments) return
  fileInputRef.value?.click()
}

async function uploadAttachmentFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch('/api/messages/attachments/upload/', {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken.value },
    body: formData,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(extractApiErrorMessage(data, `${file.name} 上传失败`))
  pendingAttachments.value.push(data.attachment)
}

async function onAttachmentSelected(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (!files.length) return
  const remaining = maxPendingAttachments - pendingAttachments.value.length
  if (remaining <= 0) {
    ElMessage.warning(`一次最多发送 ${maxPendingAttachments} 个附件`)
    return
  }
  if (files.length > remaining) {
    ElMessage.warning(`最多还能添加 ${remaining} 个附件`)
  }
  isUploadingAttachment.value = true
  try {
    for (const file of files.slice(0, remaining)) {
      await uploadAttachmentFile(file)
    }
  } catch (e) {
    ElMessage.error(e.message || '附件上传失败')
  } finally {
    isUploadingAttachment.value = false
  }
}

function removePendingAttachment(index) {
  pendingAttachments.value.splice(index, 1)
}

function appendEmoji(emoji) {
  newMessage.value += emoji
  showEmojiPicker.value = false
  nextTick(() => inputRef.value?.focus())
}

function toggleCodeInput() {
  showCodeInput.value = !showCodeInput.value
  showEmojiPicker.value = false
  if (showCodeInput.value) nextTick(() => document.querySelector('.code-input')?.focus())
}

function buildCodeBlock() {
  const code = codeDraft.value.trim()
  return code ? `[code]${code}[/code]` : ''
}

function insertCodeBlock() {
  const block = buildCodeBlock()
  if (!block) return
  const prefix = newMessage.value.trim() ? '\n\n' : ''
  newMessage.value += `${prefix}${block}`
  codeDraft.value = ''
  showCodeInput.value = false
  saveCurrentDraft()
  applyDraftPreviews()
  nextTick(() => {
    inputRef.value?.focus()
    autoGrowComposer()
  })
}

async function sendCodeBlock() {
  const block = buildCodeBlock()
  if (!block) return
  const previous = newMessage.value
  newMessage.value = previous.trim() ? `${previous.trim()}\n\n${block}` : block
  codeDraft.value = ''
  showCodeInput.value = false
  await sendMessage()
}

function getSupportedVoiceMimeType() {
  if (typeof MediaRecorder === 'undefined') return ''
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg']
  return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || ''
}

async function toggleVoiceRecording() {
  if (isRecordingVoice.value) {
    stopVoiceRecording()
    return
  }
  if (pendingAttachments.value.length >= maxPendingAttachments) {
    ElMessage.warning(`一次最多发送 ${maxPendingAttachments} 个附件`)
    return
  }
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    ElMessage.error('当前浏览器不支持录音')
    return
  }
  try {
    const mimeType = getSupportedVoiceMimeType()
    voiceStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    voiceChunks = []
    voiceRecorder = new MediaRecorder(voiceStream, mimeType ? { mimeType } : undefined)
    voiceRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) voiceChunks.push(event.data)
    }
    voiceRecorder.onstop = handleVoiceRecordingStop
    voiceRecorder.start()
    isRecordingVoice.value = true
  } catch (e) {
    cleanupVoiceRecording()
    ElMessage.error('无法使用麦克风，请检查浏览器权限')
  }
}

function stopVoiceRecording() {
  if (voiceRecorder && voiceRecorder.state !== 'inactive') {
    voiceRecorder.stop()
  }
}

async function handleVoiceRecordingStop() {
  const mimeType = voiceRecorder?.mimeType || 'audio/webm'
  const chunks = [...voiceChunks]
  cleanupVoiceRecording()
  if (!chunks.length) return
  const ext = mimeType.includes('ogg') ? 'ogg' : 'webm'
  const blob = new Blob(chunks, { type: mimeType })
  const file = new File([blob], `voice-${Date.now()}.${ext}`, { type: mimeType })
  isUploadingAttachment.value = true
  try {
    await uploadAttachmentFile(file)
    ElMessage.success('语音已加入待发送')
  } catch (e) {
    ElMessage.error(e.message || '语音上传失败')
  } finally {
    isUploadingAttachment.value = false
  }
}

function cleanupVoiceRecording() {
  isRecordingVoice.value = false
  voiceRecorder = null
  voiceChunks = []
  if (voiceStream) {
    voiceStream.getTracks().forEach((track) => track.stop())
    voiceStream = null
  }
}

function canRecallMessage(m) {
  if (!m?.is_own || !m?.created_at) return false
  const ts = new Date(m.created_at).getTime()
  return Number.isFinite(ts) && (Date.now() - ts) / 1000 < recallWindowSeconds
}

function clearReplyDraft() {
  replyDraft.value = null
}

function openNewMessageDialog() {
  forwardDraft.value = null
  showNewMessageDialog.value = true
}

function closeNewMessageDialog() {
  showNewMessageDialog.value = false
  if (forwardDraft.value?.autoSendChatlog || !selectedConversationKey.value || !newMessage.value) {
    forwardDraft.value = null
  }
}

function onQuoteMessage(m) {
  replyDraft.value = createReplyDraft(m, 'quote')
  nextTick(() => inputRef.value?.focus())
}

async function copyMessageContent(m) {
  try {
    const text = parseMergedForward(m?.content)
      ? mergedForwardPreview(m?.content, '')
      : String(m?.content || '')
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制消息内容')
  } catch (e) {
    ElMessage.error('复制失败，请检查浏览器权限')
  }
}

function onForwardMessage(m) {
  forwardDraft.value = {
    sourceMessageId: m.id,
    content: parseMergedForward(m?.content) ? mergedForwardPreview(m.content, '') : buildForwardMessage(m),
  }
  showNewMessageDialog.value = true
}

function openMergedForwardDialog({ payload }) {
  if (!payload) return
  mergedForwardDialog.value = {
    visible: true,
    payload,
  }
}

function closeMergedForwardDialog() {
  mergedForwardDialog.value = { visible: false, payload: null }
}

function handleComposerEnter(e) {
  if (mentionPicker.value.visible && mentionSuggestions.value.length) {
    e.preventDefault()
    selectMention(mentionSuggestions.value[mentionPicker.value.activeIndex] || mentionSuggestions.value[0])
    return
  }
  if (e.shiftKey) return
  e.preventDefault()
  sendMessage()
}

function onComposerInput() {
  autoGrowComposer()
  updateMentionPicker()
  saveCurrentDraft()
  applyDraftPreviews()
  const isEmpty = !newMessage.value.trim()
  // "有内容 → 空" 跳变：用户清空了输入框，让对方立即停止"正在输入"提示
  if (isEmpty && composerWasNotEmpty) {
    sendTypingStop()
  }
  composerWasNotEmpty = !isEmpty
  scheduleTypingNotice()
}

function closeMentionPicker() {
  mentionPicker.value = {
    visible: false,
    query: '',
    start: -1,
    end: -1,
    activeIndex: 0,
  }
}

async function ensureGroupMembersForMention() {
  if (!isCurrentGroup.value) return
  const groupId = selectedGroupId()
  if (!groupId) return
  const detail = groupPanel.value.detail
  if (normalizeUserId(detail?.id) === groupId && mentionMembers.value.length) return
  try {
    const r = await fetch(`/api/messages/groups/${groupId}/`, { cache: 'no-store' })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) return
    if (d.group) groupPanel.value.detail = d.group
    if (d.settings) currentSettings.value = { ...currentSettings.value, ...d.settings }
  } catch {
    // @候选只是辅助输入，失败时不打断用户继续发消息。
  }
}

function updateMentionPicker() {
  if (!isCurrentGroup.value) {
    closeMentionPicker()
    return
  }
  const el = inputRef.value
  if (!el) return
  const cursor = el.selectionStart ?? newMessage.value.length
  const before = newMessage.value.slice(0, cursor)
  const match = before.match(/(?:^|\s)@([^\s@]{0,24})$/)
  if (!match) {
    closeMentionPicker()
    return
  }
  const query = match[1] || ''
  const atIndex = before.lastIndexOf('@')
  mentionPicker.value = {
    visible: true,
    query,
    start: atIndex,
    end: cursor,
    activeIndex: Math.min(mentionPicker.value.activeIndex, Math.max(mentionSuggestions.value.length - 1, 0)),
  }
  ensureGroupMembersForMention()
}

function moveMentionSelection(delta) {
  if (!mentionPicker.value.visible) return
  const total = mentionSuggestions.value.length
  if (!total) return
  mentionPicker.value.activeIndex = (mentionPicker.value.activeIndex + delta + total) % total
}

function onMentionArrow(event, delta) {
  if (!mentionPicker.value.visible) return
  event.preventDefault()
  moveMentionSelection(delta)
}

function selectMention(item) {
  if (!item || mentionPicker.value.start < 0) return
  const label = item.type === 'all' ? '@全体成员' : `@${item.username}`
  const before = newMessage.value.slice(0, mentionPicker.value.start)
  const after = newMessage.value.slice(mentionPicker.value.end)
  const needsLeadingSpace = before && !/\s$/.test(before) ? ' ' : ''
  const needsTrailingSpace = after && !/^\s/.test(after) ? ' ' : ''
  const insert = `${needsLeadingSpace}${label} `
  newMessage.value = `${before}${insert}${needsTrailingSpace}${after}`
  closeMentionPicker()
  nextTick(() => {
    const el = inputRef.value
    if (!el) return
    const pos = before.length + insert.length
    el.focus()
    el.setSelectionRange(pos, pos)
    autoGrowComposer()
    saveCurrentDraft()
  })
}

function buildMentionPayload(content) {
  const memberNames = new Set(mentionMembers.value.map((member) => member.username).filter(Boolean))
  const mentions = []
  const mentionRegex = /@([^\s@]{1,80})/g
  let match
  while ((match = mentionRegex.exec(content || '')) !== null) {
    const username = match[1]
    if (memberNames.has(username) && !mentions.includes(username)) {
      mentions.push(username)
    }
  }
  const mentionAll = /@(全体成员|全体)(?=\s|$)|@all\b/i.test(content || '')
  return {
    mentions,
    mention_all: mentionAll,
  }
}

function scheduleTypingNotice() {
  if (isCurrentGroup.value || !selectedUserId.value || !newMessage.value.trim()) return
  // 节流：同一会话内 1.4s 最多向后端发一次 typing 事件
  if (typingThrottleTimer) return
  typingThrottleTimer = window.setTimeout(() => {
    typingThrottleTimer = null
  }, 1400)
  chatSocket?.send?.({
    type: 'typing',
    peer_id: selectedUserId.value,
  })
}

function sendTypingStop() {
  if (isCurrentGroup.value || !selectedUserId.value) return
  // 立即清除节流定时器，确保下一次 typing 事件不会被吞
  if (typingThrottleTimer) {
    clearTimeout(typingThrottleTimer)
    typingThrottleTimer = null
  }
  chatSocket?.send?.({
    type: 'typing_stop',
    peer_id: selectedUserId.value,
  })
}

function autoGrowComposer() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 180)}px`
}

function resetComposerHeight() {
  const el = inputRef.value
  if (!el) return
  el.style.height = ''
}

async function startNewConversation(userId) {
  showNewMessageDialog.value = false
  scope.value = 'all'
  const pendingForward = forwardDraft.value
  if (pendingForward?.autoSendChatlog && pendingForward.content) {
    await sendChatlogForwardToUser(userId, pendingForward.content)
    return
  }
  saveCurrentDraft()
  selectedUserId.value = userId
  selectedConversationKey.value = `user:${userId}`
  hideTypingIndicator()
  selectionMode.value = false
  clearSelectedMessages()
  applyDraftForConversation(userId)
  if (!newMessage.value && pendingForward?.content) {
    newMessage.value = pendingForward.content
  }
  pendingAttachments.value = []
  showEmojiPicker.value = false
  replyDraft.value = null
  forwardDraft.value = pendingForward?.sourceMessageId ? pendingForward : null
  mobileChatOpen.value = true
  loadMessages()
  loadConversations()
  nextTick(() => {
    inputRef.value?.focus()
    autoGrowComposer()
  })
}

async function startGroupConversation(group) {
  showNewMessageDialog.value = false
  scope.value = 'all'
  saveCurrentDraft()
  const groupId = normalizeUserId(group?.id || group?.group_id)
  if (!groupId) return
  selectedUserId.value = null
  selectedConversationKey.value = `group:${groupId}`
  hideTypingIndicator()
  selectionMode.value = false
  clearSelectedMessages()
  applyDraftForConversation(selectedConversationKey.value)
  pendingAttachments.value = []
  showEmojiPicker.value = false
  replyDraft.value = null
  forwardDraft.value = null
  mobileChatOpen.value = true
  await loadConversations()
  loadMessages()
  nextTick(() => {
    inputRef.value?.focus()
    autoGrowComposer()
  })
}

// ==== 滚动 / 时间 ====
function scrollToBottom() {
  if (messagesListRef.value) {
    messagesListRef.value.scrollTop = messagesListRef.value.scrollHeight
  }
}

function updateScrollBottomState() {
  const el = messagesListRef.value
  if (!el) {
    showScrollToBottom.value = false
    return
  }
  const distance = el.scrollHeight - el.scrollTop - el.clientHeight
  showScrollToBottom.value = distance > 180
  if (!showScrollToBottom.value) scrollBottomUnreadCount.value = 0
}

function onMessagesScroll() {
  updateScrollBottomState()
}

function jumpToLatest() {
  scrollBottomUnreadCount.value = 0
  scrollToBottomSoon()
}

function scrollToBottomSoon() {
  nextTick(() => {
    scrollToBottom()
    requestAnimationFrame(scrollToBottom)
    window.setTimeout(scrollToBottom, 80)
    window.setTimeout(scrollToBottom, 240)
    window.setTimeout(updateScrollBottomState, 260)
  })
}

function formatShortTime(iso) {
  return formatRelativeListDate(iso)
}

function formatTtl(sec) {
  if (!sec || sec === 0) return '立即'
  if (sec < 3600) return `${sec / 60} 分钟`
  if (sec < 86400) return `${sec / 3600} 小时`
  if (sec < 604800) return `${sec / 86400} 天`
  return `${sec / 604800} 周`
}

function highlightText(text, q) {
  if (!text) return ''
  const safe = escapeHtml(text)
  if (!q) return safe
  const safeQ = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return sanitizeHtml(safe.replace(new RegExp(`(${safeQ})`, 'gi'), '<mark>$1</mark>'))
}

// ==== Tab / 搜索 ====
function switchScope(s) {
  scope.value = s
  selectedUserId.value = null
  selectedConversationKey.value = null
  closeMessageCtxMenu()
  mobileChatOpen.value = false
  loadConversations()
}

let globalSearchTimer = null
function onGlobalSearchInput() {
  clearTimeout(globalSearchTimer)
  globalSearchTimer = setTimeout(runGlobalSearch, 260)
}

async function runGlobalSearch() {
  const q = globalSearch.value.trim()
  if (!q || q.length < 2) {
    globalSearchResults.value = null
    return
  }
  try {
    const r = await fetch(`/api/messages/search/?q=${encodeURIComponent(q)}`)
    if (r.ok) {
      const d = await r.json()
      globalSearchResults.value = d.results || []
    }
  } catch (e) {
    console.error(e)
  }
}

function clearGlobalSearch() {
  globalSearch.value = ''
  globalSearchResults.value = null
}

function searchResultText(result) {
  if (result?.search_snippet) return result.search_snippet
  return result?.content_preview || mergedForwardPreview(result?.content, '') || result?.content || ''
}

async function jumpToResult(r) {
  clearGlobalSearch()
  selectedUserId.value = r.peer_id
  selectedConversationKey.value = `user:${r.peer_id}`
  highlightMessageId.value = r.id
  mobileChatOpen.value = true
  await loadMessages()
  scrollToMessage(r.id)
}

async function jumpToMessage(m) {
  showChatSearch.value = false
  highlightMessageId.value = m.id
  scrollToMessage(m.id)
  setTimeout(() => (highlightMessageId.value = null), 2500)
}

function scrollToMessage(messageId) {
  nextTick(() => {
    const el = document.querySelector(`.messages-list [data-msg-id="${messageId}"]`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    else scrollToBottomSoon()
  })
}

async function jumpToGroupAnnouncement(announcement) {
  closeGroupInfo()
  const messageId = announcement?.message_id
  if (!messageId) {
    ElMessage.info('这条公告暂无可定位的群消息')
    return
  }
  highlightMessageId.value = messageId
  if (!messages.value.some((message) => message.id === messageId)) {
    await loadMessages({ silent: true })
  }

  // 检查消息是否真的存在（可能被用户删除或撤回）
  if (!messages.value.some((message) => message.id === messageId)) {
    showAnnouncementJumpFailedDialog.value = true
    highlightMessageId.value = null
    return
  }

  scrollToMessage(messageId)
  setTimeout(() => {
    if (highlightMessageId.value === messageId) highlightMessageId.value = null
  }, 2500)
}

// ==== 消息操作 ====
function toggleSelectionMode() {
  selectionMode.value = !selectionMode.value
  if (!selectionMode.value) clearSelectedMessages()
  closeMessageCtxMenu()
}

function clearSelectedMessages() {
  selectedMessageIds.value = new Set()
}

function getSelectedMessages() {
  return messages.value.filter((message) => selectedMessageIds.value.has(message.id))
}

function hideTypingIndicator() {
  typingIndicator.value = { visible: false, username: '' }
  clearTimeout(typingHideTimer)
  typingHideTimer = null
}

function toggleMessageSelected(message) {
  const next = new Set(selectedMessageIds.value)
  if (next.has(message.id)) next.delete(message.id)
  else next.add(message.id)
  selectedMessageIds.value = next
}

function enterSelectionModeWithMessage(message) {
  selectionMode.value = true
  selectedMessageIds.value = new Set([message.id])
  closeMessageCtxMenu()
}

async function deleteSingleMessage(message) {
  try {
    await ElMessageBox.confirm(
      '删除后这条消息只会从你的视图中隐藏，确认删除？',
      '删除消息',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  try {
    const groupId = selectedGroupId()
    const url = groupId
      ? `/api/messages/groups/${groupId}/messages/${message.id}/delete/`
      : `/api/messages/${message.id}/delete/`
    await apiPost(url, { scope: 'self' })
    messages.value = messages.value.filter((item) => item.id !== message.id)
    const next = new Set(selectedMessageIds.value)
    next.delete(message.id)
    selectedMessageIds.value = next
    if (selectedMessageIds.value.size === 0) selectionMode.value = false
    loadConversations({ silent: true, preserveOrder: true })
    ElMessage.success('已删除该消息')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function deleteSelectedMessages() {
  const ids = [...selectedMessageIds.value]
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(
      `删除后这些消息只会从你的视图中隐藏，共 ${ids.length} 条。确认删除？`,
      '删除所选消息',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  try {
    const groupId = selectedGroupId()
    if (groupId) {
      await Promise.all(ids.map((id) =>
        apiPost(`/api/messages/groups/${groupId}/messages/${id}/delete/`, { scope: 'self' })
      ))
    } else {
      await apiPost('/api/messages/bulk-delete/', { message_ids: ids })
    }
    messages.value = messages.value.filter((message) => !selectedMessageIds.value.has(message.id))
    clearSelectedMessages()
    selectionMode.value = false
    loadConversations({ silent: true, preserveOrder: true })
    ElMessage.success('已删除所选消息')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function forwardSelectedAsChatlog() {
  const selected = getSelectedMessages()
  if (!selected.length) return
  if (selected.length > MERGED_FORWARD_MAX_ITEMS) {
    ElMessage.warning(`每次最多只能合并转发 ${MERGED_FORWARD_MAX_ITEMS} 条消息`)
    return
  }
  let content = ''
  try {
    content = buildChatlogForward(selected)
  } catch (e) {
    ElMessage.error(e.message || '合并转发内容过长，请减少消息数量后再试')
    return
  }
  forwardDraft.value = {
    sourceMessageId: null,
    content,
    autoSendChatlog: true,
  }
  showNewMessageDialog.value = true
}

async function sendChatlogForwardToUser(userId, content, turnstileToken = '') {
  if (!userId || !content) return
  isSending.value = true
  try {
    const payload = {
      recipient_id: userId,
      content,
      attachment_ids: [],
    }
    if (turnstileToken) payload.turnstile_token = turnstileToken
    const d = await apiPost('/api/messages/send/', payload)
    const sentMessage = normalizeIncomingMessage(d.message)
    const wasCurrentConversation = normalizeUserId(selectedUserId.value) === normalizeUserId(userId)
    selectedUserId.value = userId
    selectedConversationKey.value = `user:${userId}`
    mobileChatOpen.value = true
    scope.value = 'all'
    hideTypingIndicator()
    selectionMode.value = false
    clearSelectedMessages()
    if (wasCurrentConversation) {
      if (!messages.value.some((message) => message.id === sentMessage.id)) {
        messages.value = [...messages.value, sentMessage]
      }
    } else {
      messages.value = []
    }
    forwardDraft.value = null
    newMessage.value = ''
    pendingAttachments.value = []
    showEmojiPicker.value = false
    replyDraft.value = null
    clearDraftForConversation(userId)
    applyDraftPreviews()
    resetComposerHeight()
    upsertConversationPreviewFromMessage(sentMessage, userId, { preserveOrder: true })
    loadMessages({ silent: wasCurrentConversation })
    loadConversations({ silent: true, preserveOrder: true })
    await nextTick()
    scrollToBottomSoon()
    ElMessage.success('已合并转发')
  } catch (e) {
    if (e?.data?.need_turnstile) {
      await openTurnstileGate(content, userId, e.data.quota_limit, [], { autoSendChatlog: true })
      return
    }
    ElMessage.error(e.message)
  } finally {
    isSending.value = false
  }
}

function saveSelectedAsNote() {
  const selected = getSelectedMessages()
  if (!selected.length) return
  const peerName = selectedConversation.value?.username || '对方'
  const payload = {
    title: `${currentUserName()} 与 ${peerName} 的聊天摘录`,
    content: buildKnowledgeNoteFromMessages(selected),
    created_at: new Date().toISOString(),
  }
  sessionStorage.setItem('knowledgeMessageNoteDraft', JSON.stringify(payload))
  window.location.href = '/knowledge/?create=1&from=messages'
}

function buildKnowledgeNoteFromMessages(selected) {
  return selected
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    .map((message) => {
      const senderLabel = message.is_own ? currentUserName() : (message.sender || selectedConversation.value?.username || '对方')
      const timeLabel = formatForwardTime(message.created_at)
      const content = getReadableMessageText(message)
      return `## ${senderLabel} · ${timeLabel}\n\n${content || '[附件]'}`
    })
    .join('\n\n')
}

async function recallMessage(m) {
  try {
    await ElMessageBox.confirm('撤回后双方都将看不到此消息，确认撤回吗？', '撤回消息', {
      confirmButtonText: '撤回',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    const groupId = selectedGroupId()
    const url = groupId
      ? `/api/messages/groups/${groupId}/messages/${m.id}/delete/`
      : `/api/messages/${m.id}/delete/`
    await apiPost(url, { scope: 'both' })
    messages.value = messages.value.filter((x) => x.id !== m.id)
    loadConversations()
    ElMessage.success('已撤回')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function editGroupMessage(message) {
  const groupId = selectedGroupId()
  if (!groupId || !message?.is_own) return
  let result
  try {
    result = await ElMessageBox.prompt('编辑已发送的群消息', '编辑消息', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputValue: message.content || '',
      inputValidator: (value) => {
        const text = String(value || '').trim()
        if (!text) return '消息内容不能为空'
        if (text.length > 5000) return '消息内容不能超过 5000 字'
        return true
      },
    })
  } catch {
    return
  }

  const content = String(result?.value || '').trim()
  if (!content || content === String(message.content || '').trim()) return
  try {
    const d = await apiPost(`/api/messages/groups/${groupId}/messages/${message.id}/edit/`, { content })
    const edited = normalizeIncomingMessage(d.message)
    const index = messages.value.findIndex((item) => item.id === edited.id)
    if (index !== -1) {
      messages.value[index] = edited
      messages.value = [...messages.value]
    }
    loadConversations({ silent: true, preserveOrder: true })
    ElMessage.success('已保存编辑')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

// ==== 对话顶部菜单动作 ====
function viewPeerProfile() {
  if (isCurrentGroup.value || !selectedUserId.value) return
  showChatMenu.value = false
  const url = `/api/users/${selectedUserId.value}/profile/?_=${Date.now()}`
  peerProfile.value.loading = true
  fetch(url, { cache: 'no-store' })
    .then((r) => r.json())
    .then((d) => {
      if (d.status !== 'success') {
        ElMessage.error(d.message || d.error || '加载失败')
        return
      }
      peerProfile.value = {
        visible: true,
        loading: false,
        videoMuted: true,
        videoPaused: false,
        videoVolume: 0.6,
        data: d,
      }
      nextTick(() => updatePeerProfileVolume())
    })
    .catch(() => ElMessage.error('网络错误'))
    .finally(() => {
      peerProfile.value.loading = false
    })
}

function closePeerProfile() {
  peerProfile.value.visible = false
  const video = peerProfileVideoRef.value
  if (video) video.pause()
}

function togglePeerProfileVideo() {
  const video = peerProfileVideoRef.value
  if (!video) return
  if (video.paused) {
    video.play().catch(() => {})
    peerProfile.value.videoPaused = false
  } else {
    video.pause()
    peerProfile.value.videoPaused = true
  }
}

function togglePeerProfileMute() {
  if (peerProfile.value.videoMuted && Number(peerProfile.value.videoVolume || 0) === 0) {
    peerProfile.value.videoVolume = 0.6
  }
  peerProfile.value.videoMuted = !peerProfile.value.videoMuted
  updatePeerProfileVolume()
}

function updatePeerProfileVolume() {
  const video = peerProfileVideoRef.value
  if (!video) return
  video.muted = peerProfile.value.videoMuted
  video.volume = Number(peerProfile.value.videoVolume || 0)
}

async function toggleMarkRead() {
  showChatMenu.value = false
  const shouldMarkRead = hasUnread.value || currentSettings.value.force_unread
  try {
    const url = shouldMarkRead
      ? '/api/messages/conversation/mark-read/'
      : '/api/messages/conversation/mark-unread/'
    await apiPost(url, { user_id: selectedUserId.value })
    currentSettings.value.force_unread = !shouldMarkRead
    loadConversations()
    ElMessage.success(shouldMarkRead ? '已标记为已读' : '已标记为未读')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function togglePin() {
  showChatMenu.value = false
  const v = !currentSettings.value.is_pinned
  try {
    await apiPost('/api/messages/conversation/pin/', {
      user_id: selectedUserId.value,
      value: v,
    })
    currentSettings.value.is_pinned = v
    loadConversations()
    ElMessage.success(v ? '已置顶' : '已取消置顶')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function toggleMute() {
  showChatMenu.value = false
  const v = !currentSettings.value.is_muted
  try {
    await apiPost('/api/messages/conversation/mute/', {
      user_id: selectedUserId.value,
      value: v,
    })
    currentSettings.value.is_muted = v
    patchConversationByKey(selectedConversationKey.value, { is_muted: v })
    suppressNextConversationRefresh()
    ElMessage.success(v ? '已开启免打扰' : '已关闭免打扰')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function toggleArchive() {
  showChatMenu.value = false
  const v = !currentSettings.value.is_archived
  try {
    await apiPost('/api/messages/conversation/archive/', {
      user_id: selectedUserId.value,
      value: v,
    })
    currentSettings.value.is_archived = v
    loadConversations()
    ElMessage.success(v ? '已归档' : '已取消归档')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function openDisappearing() {
  showChatMenu.value = false
  showDisappearingDialog.value = true
}

function onDisappearingSaved(d) {
  currentSettings.value.disappearing_enabled = d.enabled
  currentSettings.value.disappearing_ttl_seconds = d.ttl
}

function exportChat() {
  showChatMenu.value = false
  window.open(
    `/api/messages/conversation/export/?user_id=${selectedUserId.value}`,
    '_blank'
  )
}

async function clearConversation() {
  showChatMenu.value = false
  try {
    await ElMessageBox.confirm(
      '清空后你将看不到此对话的历史消息（对方仍可见），确认清空？',
      '清空聊天记录',
      { confirmButtonText: '清空', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await apiPost('/api/messages/conversation/clear/', {
      user_id: selectedUserId.value,
    })
    messages.value = []
    loadConversations()
    ElMessage.success('已清空')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function postGroupSetting(action, body = {}) {
  const groupId = selectedGroupId()
  if (!groupId) return null
  const d = await apiPost(`/api/messages/groups/${groupId}/settings/${action}/`, body)
  if (d.settings) currentSettings.value = { ...currentSettings.value, ...d.settings }
  return d
}

async function toggleGroupMarkRead() {
  showChatMenu.value = false
  const shouldMarkRead = hasUnread.value || currentSettings.value.force_unread
  try {
    await postGroupSetting(shouldMarkRead ? 'mark-read' : 'mark-unread')
    loadConversations()
    ElMessage.success(shouldMarkRead ? '已标记为已读' : '已标记为未读')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function toggleGroupPin() {
  showChatMenu.value = false
  const v = !currentSettings.value.is_pinned
  try {
    await postGroupSetting('pin', { value: v })
    currentSettings.value.is_pinned = v
    loadConversations()
    ElMessage.success(v ? '已置顶' : '已取消置顶')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function toggleGroupMute() {
  showChatMenu.value = false
  const v = !currentSettings.value.is_muted
  try {
    await postGroupSetting('mute', { value: v })
    currentSettings.value.is_muted = v
    patchConversationByKey(selectedConversationKey.value, { is_muted: v })
    suppressNextConversationRefresh()
    ElMessage.success(v ? '已开启免打扰' : '已关闭免打扰')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function toggleGroupArchive() {
  showChatMenu.value = false
  const v = !currentSettings.value.is_archived
  try {
    await postGroupSetting('archive', { value: v })
    currentSettings.value.is_archived = v
    loadConversations()
    ElMessage.success(v ? '已归档' : '已取消归档')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function clearGroupConversation() {
  showChatMenu.value = false
  try {
    await ElMessageBox.confirm(
      '清空后你将看不到此群组的历史消息（其他成员不受影响），确认清空？',
      '清空群聊记录',
      { confirmButtonText: '清空', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await postGroupSetting('clear')
    messages.value = []
    loadConversations()
    ElMessage.success('已清空')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function openGroupInfo() {
  showChatMenu.value = false
  const groupId = selectedGroupId()
  if (!groupId) return
  groupPanel.value.visible = true
  groupPanel.value.loading = true
  groupPanel.value.error = ''
  groupPanel.value.detail = null
  groupPanel.value.searchResult = null
  try {
    const r = await fetch(`/api/messages/groups/${groupId}/`, { cache: 'no-store' })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(extractApiErrorMessage(d, '加载群设置失败'))
    if (!d.group) throw new Error('群设置数据为空')
    groupPanel.value.detail = d.group
    groupPanel.value.nameDraft = d.group?.name || ''
    groupPanel.value.announcementDraft = d.group?.announcement || ''
    groupPanel.value.announcementPinned = !!d.group?.announcement_pinned_at
    groupPanel.value.announcementOriginal = groupPanel.value.announcementDraft
    groupPanel.value.announcementPinnedOriginal = groupPanel.value.announcementPinned
    cancelEditGroupAnnouncement()
    syncConversationAnnouncementFromGroup(d.group)
    if (d.settings) currentSettings.value = { ...currentSettings.value, ...d.settings }
    loadGroupSharedItems()
    if (canManageCurrentGroup.value) {
      loadGroupInviteLinks()
      loadGroupJoinRequests()
      loadGroupAuditLogs()
    }
  } catch (e) {
    const message = e?.message || '加载群设置失败'
    groupPanel.value.detail = null
    groupPanel.value.error = message
    ElMessage.error(message)
  } finally {
    groupPanel.value.loading = false
  }
}

function closeGroupInfo() {
  groupPanel.value.visible = false
  groupPanel.value.error = ''
  groupPanel.value.searchInput = ''
  groupPanel.value.searchResult = null
  groupPanel.value.inviteLinks = []
  groupPanel.value.auditLogs = []
  groupPanel.value.joinRequests = []
  groupPanel.value.sharedLinks = []
  groupPanel.value.memberSearch = ''
  groupPanel.value.memberRoleFilter = 'all'
  groupPanel.value.savingAnnouncement = false
  cancelEditGroupAnnouncement()
}

function closeAnnouncementDialog() {
  showAnnouncementJumpFailedDialog.value = false
}

function openGroupInfoFromDialog() {
  showAnnouncementJumpFailedDialog.value = false
  openGroupInfo()
}

function currentGroupAnnouncementFromDetail(detail) {
  const item = detail?.announcement_history?.find((entry) => entry.pinned) || detail?.announcement_history?.[0]
  if (item?.content) return item
  if (!detail?.announcement) return null
  return {
    content: detail.announcement,
    pinned: !!detail.announcement_pinned_at,
    message_id: detail.announcement_message_id || null,
    updated_at: detail.announcement_updated_at || detail.updated_at,
  }
}

function syncConversationAnnouncementFromGroup(group) {
  if (!group?.id) return
  const item = currentGroupAnnouncementFromDetail(group)
  patchConversationByKey(`group:${group.id}`, {
    announcement: item?.content || '',
    announcement_pinned: !!item?.pinned,
    announcement_message_id: item?.message_id || null,
    announcement_updated_at: item?.updated_at || null,
  })
}

async function saveGroupName() {
  const groupId = selectedGroupId()
  const name = groupPanel.value.nameDraft.trim()
  if (!groupId || !name) return
  try {
    const d = await apiPost(`/api/messages/groups/${groupId}/`, { name })
    groupPanel.value.detail = d.group
    const conv = findConversationByKey(`group:${groupId}`)
    if (conv) conv.username = name
    loadConversations({ silent: true, preserveOrder: true })
    ElMessage.success('群名称已保存')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function saveGroupAnnouncement() {
  const groupId = selectedGroupId()
  if (!groupId || !canManageCurrentGroup.value || !hasGroupAnnouncementChanges.value || groupPanel.value.savingAnnouncement) return
  groupPanel.value.savingAnnouncement = true
  try {
    const d = await apiPost(`/api/messages/groups/${groupId}/announcement/`, {
      announcement: groupPanel.value.announcementDraft,
      pin: groupPanel.value.announcementPinned,
    })
    if (d.group) {
      groupPanel.value.detail = d.group
      groupPanel.value.announcementDraft = d.group.announcement || ''
      groupPanel.value.announcementPinned = !!d.group.announcement_pinned_at
      syncConversationAnnouncementFromGroup(d.group)
    }
    groupPanel.value.announcementOriginal = groupPanel.value.announcementDraft
    groupPanel.value.announcementPinnedOriginal = groupPanel.value.announcementPinned
    cancelEditGroupAnnouncement()
    loadConversations({ silent: true, preserveOrder: true })
    ElMessage.success('群公告已保存')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    groupPanel.value.savingAnnouncement = false
  }
}

function startEditGroupAnnouncement(item) {
  if (!canManageCurrentGroup.value || !item) return
  groupPanel.value.editingAnnouncementId = item.id
  groupPanel.value.announcementEditDraft = item.content || ''
  groupPanel.value.announcementEditPinned = !!item.pinned
}

function cancelEditGroupAnnouncement() {
  groupPanel.value.editingAnnouncementId = null
  groupPanel.value.announcementEditDraft = ''
  groupPanel.value.announcementEditPinned = false
}

function canSaveEditingAnnouncement(item) {
  if (!canManageCurrentGroup.value || !item || groupPanel.value.savingAnnouncement) return false
  const content = groupPanel.value.announcementEditDraft.trim()
  if (!content) return false
  return content !== (item.content || '') || !!groupPanel.value.announcementEditPinned !== !!item.pinned
}

async function updateGroupAnnouncement(item) {
  const groupId = selectedGroupId()
  const content = groupPanel.value.announcementEditDraft.trim()
  if (!groupId || !item?.id || !canSaveEditingAnnouncement(item)) return
  groupPanel.value.savingAnnouncement = true
  try {
    const d = await apiPost(`/api/messages/groups/${groupId}/announcement/${item.id}/`, {
      announcement: content,
      pin: groupPanel.value.announcementEditPinned,
    })
    if (d.group) {
      groupPanel.value.detail = d.group
      groupPanel.value.announcementDraft = d.group.announcement || ''
      groupPanel.value.announcementPinned = !!d.group.announcement_pinned_at
      groupPanel.value.announcementOriginal = groupPanel.value.announcementDraft
      groupPanel.value.announcementPinnedOriginal = groupPanel.value.announcementPinned
      syncConversationAnnouncementFromGroup(d.group)
    }
    cancelEditGroupAnnouncement()
    loadConversations({ silent: true, preserveOrder: true })
    ElMessage.success('历史公告已更新')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    groupPanel.value.savingAnnouncement = false
  }
}

async function toggleGroupAnnouncementPin(item) {
  if (!item) return
  groupPanel.value.editingAnnouncementId = item.id
  groupPanel.value.announcementEditDraft = item.content || ''
  groupPanel.value.announcementEditPinned = !item.pinned
  await updateGroupAnnouncement(item)
}

async function deleteGroupAnnouncement(item) {
  const groupId = selectedGroupId()
  if (!groupId || !item?.id || !canManageCurrentGroup.value || groupPanel.value.savingAnnouncement) return
  try {
    await ElMessageBox.confirm('删除后对应的公告消息会被撤回，确认删除这条公告？', '删除公告', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  groupPanel.value.savingAnnouncement = true
  try {
    const d = await apiRequest(`/api/messages/groups/${groupId}/announcement/${item.id}/`, { method: 'DELETE' })
    if (d.group) {
      groupPanel.value.detail = d.group
      groupPanel.value.announcementDraft = d.group.announcement || ''
      groupPanel.value.announcementPinned = !!d.group.announcement_pinned_at
      groupPanel.value.announcementOriginal = groupPanel.value.announcementDraft
      groupPanel.value.announcementPinnedOriginal = groupPanel.value.announcementPinned
      syncConversationAnnouncementFromGroup(d.group)
    }
    messages.value = messages.value.filter((message) => message.id !== item.message_id)
    cancelEditGroupAnnouncement()
    loadConversations({ silent: true, preserveOrder: true })
    ElMessage.success('公告已删除')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    groupPanel.value.savingAnnouncement = false
  }
}

async function saveGroupPermissions() {
  const groupId = selectedGroupId()
  if (!groupId || !canManageCurrentGroup.value) return
  groupPanel.value.savingPermissions = true
  try {
    const detail = groupPanel.value.detail || {}
    const profile = await apiPost(`/api/messages/groups/${groupId}/profile/`, {
      require_approval: !!detail.require_approval,
      allow_member_mention_all: !!detail.allow_member_mention_all,
    })
    const mode = await apiPost(`/api/messages/groups/${groupId}/mute-mode/`, {
      mute_mode: detail.mute_mode || 'none',
    })
    groupPanel.value.detail = mode.group || profile.group || detail
    loadConversations({ silent: true, preserveOrder: true })
    ElMessage.success('群权限已保存')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    groupPanel.value.savingPermissions = false
  }
}

async function searchGroupInviteUser() {
  const q = groupPanel.value.searchInput.trim()
  if (q.length < 3) return
  groupPanel.value.searching = true
  groupPanel.value.searchResult = null
  try {
    const r = await fetch(`/api/users/search/?q=${encodeURIComponent(q)}`)
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(extractApiErrorMessage(d, '搜索失败'))
    const users = d.users || []
    const currentIds = new Set((groupPanel.value.detail?.members || []).map((member) => member.user_id))
    groupPanel.value.searchResult = users.find((user) => !currentIds.has(user.id)) || null
    if (!groupPanel.value.searchResult) ElMessage.info('没有可添加的新成员')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    groupPanel.value.searching = false
  }
}

async function addGroupMember(user) {
  const groupId = selectedGroupId()
  if (!groupId || !user?.id) return
  try {
    const d = await apiPost(`/api/messages/groups/${groupId}/members/`, { member_ids: [user.id] })
    groupPanel.value.detail = d.group
    groupPanel.value.searchInput = ''
    groupPanel.value.searchResult = null
    loadConversations({ silent: true, preserveOrder: true })
    ElMessage.success('已添加成员')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function roleLabel(role) {
  if (role === 'owner') return '群主'
  if (role === 'admin') return '管理员'
  return '成员'
}

function auditActionLabel(action) {
  const labels = {
    group_create: '创建群组',
    group_update_profile: '更新资料',
    group_rename: '修改群名',
    group_announcement_update: '更新公告',
    group_mute_change: '修改发言权限',
    member_add: '添加成员',
    member_remove: '移出成员',
    member_role_change: '调整角色',
    member_mute: '禁言成员',
    member_unmute: '解除禁言',
    invite_link_create: '创建邀请链接',
    invite_link_revoke: '撤销邀请链接',
    group_message_pin: '置顶消息',
    group_message_unpin: '取消置顶消息',
    mention_all: '@全体成员',
    group_leave: '退出群组',
    group_dissolve: '解散群组',
  }
  return labels[action] || action || '操作'
}

function formatGroupDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function groupMessagePreview(message) {
  const text = getReadableMessageText(message || {}).replace(/\s+/g, ' ').trim()
  return text.length > 80 ? `${text.slice(0, 80)}...` : text
}

function canManageGroupMember(member) {
  if (!canManageCurrentGroup.value || !member || member.is_self || member.role === 'owner') return false
  const viewerRole = groupPanel.value.detail?.viewer_role || currentSettings.value.group_role
  return viewerRole === 'owner' || member.role === 'member'
}

function canChangeGroupRole(member) {
  return (groupPanel.value.detail?.viewer_role || currentSettings.value.group_role) === 'owner' && member?.role !== 'owner'
}

function canRemoveGroupMember(member) {
  if (!canManageCurrentGroup.value || !member || member.is_self || member.role === 'owner') return false
  const viewerRole = groupPanel.value.detail?.viewer_role || currentSettings.value.group_role
  return viewerRole === 'owner' || member.role !== 'admin'
}

function toggleMuteMenu(member) {
  if (!member?.user_id) return
  activeMuteMenuUserId.value = activeMuteMenuUserId.value === member.user_id ? null : member.user_id
}

function formatMutedUntil(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

async function setGroupMemberRole(member, role) {
  const groupId = selectedGroupId()
  if (!groupId || !member?.user_id || !role) return
  try {
    const d = await apiPost(`/api/messages/groups/${groupId}/members/${member.user_id}/role/`, { role })
    groupPanel.value.detail = d.group
    loadConversations({ silent: true, preserveOrder: true })
    ElMessage.success(role === 'admin' ? '已设为管理员' : '已取消管理员')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function muteGroupMember(member, durationMinutes = 60) {
  const groupId = selectedGroupId()
  if (!groupId || !member?.user_id) return
  try {
    const payload = durationMinutes === 'permanent'
      ? { duration: 'permanent' }
      : { duration_minutes: durationMinutes }
    const d = await apiPost(`/api/messages/groups/${groupId}/members/${member.user_id}/mute/`, {
      ...payload,
    })
    groupPanel.value.detail = d.group
    activeMuteMenuUserId.value = null
    ElMessage.success(durationMinutes === 'permanent' ? '已永久禁言' : '已禁言')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function unmuteGroupMember(member) {
  const groupId = selectedGroupId()
  if (!groupId || !member?.user_id) return
  try {
    const d = await apiPost(`/api/messages/groups/${groupId}/members/${member.user_id}/mute/`, {
      action: 'unmute',
    })
    groupPanel.value.detail = d.group
    activeMuteMenuUserId.value = null
    ElMessage.success('已解除禁言')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function loadGroupInviteLinks() {
  const groupId = selectedGroupId()
  if (!groupId || !canManageCurrentGroup.value) return
  groupPanel.value.inviteLoading = true
  try {
    const r = await fetch(`/api/messages/groups/${groupId}/invites/`, { cache: 'no-store' })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(extractApiErrorMessage(d, '加载邀请链接失败'))
    groupPanel.value.inviteLinks = d.invites || []
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    groupPanel.value.inviteLoading = false
  }
}

async function loadGroupAuditLogs() {
  const groupId = selectedGroupId()
  if (!groupId || !canManageCurrentGroup.value) return
  groupPanel.value.auditLoading = true
  try {
    const r = await fetch(`/api/messages/groups/${groupId}/audit-logs/?page_size=20`, { cache: 'no-store' })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(extractApiErrorMessage(d, '加载管理日志失败'))
    groupPanel.value.auditLogs = d.results || []
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    groupPanel.value.auditLoading = false
  }
}

async function loadGroupJoinRequests() {
  const groupId = selectedGroupId()
  if (!groupId || !canManageCurrentGroup.value) return
  groupPanel.value.joinRequestsLoading = true
  try {
    const r = await fetch(`/api/messages/groups/${groupId}/join-requests/?status=pending`, { cache: 'no-store' })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(extractApiErrorMessage(d, '加载入群申请失败'))
    groupPanel.value.joinRequests = d.requests || []
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    groupPanel.value.joinRequestsLoading = false
  }
}

async function reviewGroupJoinRequest(requestItem, action) {
  const groupId = selectedGroupId()
  if (!groupId || !requestItem?.id) return
  let rejectionReason = ''
  if (action === 'reject') {
    try {
      const result = await ElMessageBox.prompt('请输入拒绝原因', '拒绝入群申请', {
        confirmButtonText: '拒绝',
        cancelButtonText: '取消',
        inputValue: '暂不符合入群要求',
        inputValidator: (value) => String(value || '').trim() ? true : '请填写原因',
      })
      rejectionReason = String(result?.value || '').trim()
    } catch {
      return
    }
  }
  try {
    const d = await apiPost(`/api/messages/groups/${groupId}/join-requests/${requestItem.id}/review/`, {
      action,
      rejection_reason: rejectionReason,
    })
    if (d.group) groupPanel.value.detail = d.group
    groupPanel.value.joinRequests = groupPanel.value.joinRequests.filter((item) => item.id !== requestItem.id)
    loadGroupAuditLogs()
    loadConversations({ silent: true, preserveOrder: true })
    ElMessage.success(action === 'approve' ? '已同意入群' : '已拒绝入群')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function loadGroupSharedItems() {
  const groupId = selectedGroupId()
  if (!groupId) return
  groupPanel.value.sharedLoading = true
  try {
    const r = await fetch(`/api/messages/groups/${groupId}/shared/`, { cache: 'no-store' })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(extractApiErrorMessage(d, '加载群资料失败'))
    groupPanel.value.sharedLinks = d.links || []
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    groupPanel.value.sharedLoading = false
  }
}

async function createGroupInviteLink() {
  const groupId = selectedGroupId()
  if (!groupId) return
  if (groupPanel.value.inviteLinks.length > 0) {
    ElMessage.info('每个群组仅能创建一个邀请链接')
    return
  }
  groupPanel.value.inviteBusy = true
  try {
    const d = await apiPost(`/api/messages/groups/${groupId}/invites/`, {})
    groupPanel.value.inviteLinks = [d.invite, ...groupPanel.value.inviteLinks]
    await copyGroupInviteLink(d.invite, { silent: true })
    ElMessage.success('邀请链接已创建并复制')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    groupPanel.value.inviteBusy = false
  }
}

async function copyGroupInviteLink(invite, options = {}) {
  if (!invite?.url) return
  try {
    await navigator.clipboard.writeText(invite.url)
    if (!options.silent) ElMessage.success('邀请链接已复制')
  } catch {
    ElMessage.error('复制失败，请检查浏览器权限')
  }
}

async function revokeGroupInviteLink(invite) {
  const groupId = selectedGroupId()
  if (!groupId || !invite?.id) return
  try {
    await ElMessageBox.confirm('撤销后该邀请链接将无法再加入群组，确认撤销？', '撤销邀请链接', { type: 'warning' })
  } catch {
    return
  }
  try {
    const d = await apiPost(`/api/messages/groups/${groupId}/invites/${invite.id}/revoke/`, {})
    groupPanel.value.inviteLinks = groupPanel.value.inviteLinks.map((item) =>
      item.id === invite.id ? d.invite : item
    )
    ElMessage.success('已撤销邀请链接')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function removeGroupMember(member) {
  const groupId = selectedGroupId()
  if (!groupId || !member?.user_id) return
  try {
    await ElMessageBox.confirm(`将 ${member.username} 移出群组？`, '移出成员', { type: 'warning' })
  } catch {
    return
  }
  try {
    const d = await apiPost(`/api/messages/groups/${groupId}/members/${member.user_id}/`, {})
    groupPanel.value.detail = d.group
    loadConversations({ silent: true, preserveOrder: true })
    ElMessage.success('已移出成员')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function leaveCurrentGroup() {
  showChatMenu.value = false
  const groupId = selectedGroupId()
  if (!groupId) return
  try {
    await ElMessageBox.confirm('退出后将不再收到该群组消息，确认退出？', '退出群组', { type: 'warning' })
  } catch {
    return
  }
  try {
    await apiPost(`/api/messages/groups/${groupId}/leave/`, {})
    closeGroupInfo()
    selectedConversationKey.value = null
    selectedUserId.value = null
    messages.value = []
    loadConversations()
    ElMessage.success('已退出群组')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function dissolveCurrentGroup() {
  const groupId = selectedGroupId()
  if (!groupId) return
  try {
    await ElMessageBox.confirm('解散后所有成员都无法继续使用该群组，确认解散？', '解散群组', { type: 'warning' })
  } catch {
    return
  }
  try {
    await apiPost(`/api/messages/groups/${groupId}/dissolve/`, {})
    closeGroupInfo()
    selectedConversationKey.value = null
    selectedUserId.value = null
    messages.value = []
    loadConversations()
    ElMessage.success('已解散群组')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function blockPeer() {
  showChatMenu.value = false
  try {
    await ElMessageBox.confirm(
      `拉黑后 ${selectedConversation.value?.username} 将无法向你发送私信，是否继续？`,
      '拉黑用户',
      { confirmButtonText: '拉黑', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await apiPost('/api/users/block/', { user_id: selectedUserId.value })
    ElMessage.success('已拉黑')
    selectedUserId.value = null
    selectedConversationKey.value = null
    mobileChatOpen.value = false
    loadConversations()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function unblockPeer() {
  try {
    await apiPost('/api/users/unblock/', { user_id: selectedUserId.value })
    ElMessage.success('已解除屏蔽')
    loadConversations()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function reportPeer() {
  showChatMenu.value = false
  reportTarget.value = {
    userId: selectedUserId.value,
    username: selectedConversation.value?.username || '',
    messageId: null,
    snippet: '',
  }
}

// ==== 对话项右键菜单 ====
function onConversationContextMenu({ conv, x, y }) {
  closeMessageCtxMenu()
  lastContextMenuOpenedAt = Date.now()
  const maxX = window.innerWidth - 220
  const maxY = window.innerHeight - 320
  ctxMenu.value = {
    visible: true,
    x: Math.min(x, maxX),
    y: Math.min(y, maxY),
    conv,
  }
}

function closeCtxMenu() {
  ctxMenu.value.visible = false
}

function onMessageContextMenu({ msg, x, y }) {
  closeCtxMenu()
  showChatMenu.value = false
  lastContextMenuOpenedAt = Date.now()
  const maxX = window.innerWidth - 220
  const maxY = window.innerHeight - 260
  messageCtxMenu.value = {
    visible: true,
    x: Math.min(x, maxX),
    y: Math.min(y, maxY),
    msg,
  }
}

function closeMessageCtxMenu() {
  messageCtxMenu.value.visible = false
}

// Phase 2: 表情回应处理
async function handleReactionToggle({ msg, emoji }) {
  if (!msg || !emoji) return

  try {
    const conv = selectedConversation.value
    if (!conv || conv.conversation_type !== 'group') {
      ElMessage.warning('仅群组消息支持表情回应')
      return
    }

    const groupId = conv.group_id
    const response = await fetch(
      `/api/messages/groups/${groupId}/messages/${msg.id}/reaction/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ emoji }),
      }
    )

    const data = await response.json()

    if (data.status === 'success') {
      // 更新消息的 reactions 字段
      const messageIndex = messages.value.findIndex(m => m.id === msg.id)
      if (messageIndex !== -1) {
        messages.value[messageIndex].reactions = data.reactions
      }
    } else {
      ElMessage.error(data.error || '操作失败')
    }
  } catch (error) {
    console.error('切换表情回应失败:', error)
    ElMessage.error('操作失败')
  }
}

async function messageCtxAction(action) {
  const msg = messageCtxMenu.value.msg
  closeMessageCtxMenu()
  if (!msg) return
  if (action === 'multi_select') {
    enterSelectionModeWithMessage(msg)
    return
  }
  if (action === 'quote') {
    onQuoteMessage(msg)
    return
  }
  if (action === 'forward') {
    if (selectionMode.value || selectedMessageIds.value.size > 0) {
      if (!selectedMessageIds.value.has(msg.id)) {
        selectedMessageIds.value = new Set([...selectedMessageIds.value, msg.id])
      }
      selectionMode.value = true
      await forwardSelectedAsChatlog()
      return
    }
    onForwardMessage(msg)
    return
  }
  if (action === 'copy') {
    await copyMessageContent(msg)
    return
  }
  if (action === 'pin_group_message') {
    await togglePinnedGroupMessage(msg)
    return
  }
  if (action === 'edit') {
    await editGroupMessage(msg)
    return
  }
  if (action === 'report') {
    reportMessage(msg)
    return
  }
  if (action === 'delete') {
    await deleteSingleMessage(msg)
    return
  }
  if (action === 'recall') {
    await recallMessage(msg)
  }
}

async function togglePinnedGroupMessage(msg) {
  const groupId = selectedGroupId()
  if (!groupId || !msg?.id || !canManageCurrentGroup.value) return
  const detail = groupPanel.value.detail || selectedConversation.value || {}
  const isPinned = detail.pinned_message?.id === msg.id || msg.is_pinned
  try {
    const d = await apiPost(`/api/messages/groups/${groupId}/messages/${msg.id}/pin/`, {
      action: isPinned ? 'unpin' : 'pin',
    })
    if (d.group) groupPanel.value.detail = d.group
    messages.value = messages.value.map((item) => ({
      ...item,
      is_pinned: !isPinned && item.id === msg.id,
    }))
    ElMessage.success(isPinned ? '已取消置顶' : '已置顶消息')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function reportMessage(msg) {
  if (isCurrentGroup.value) {
    reportTarget.value = {
      userId: msg.sender_id,
      username: msg.sender || selectedConversation.value?.username || '',
      messageId: msg.id,
      submitUrl: `/api/messages/groups/${selectedGroupId()}/messages/${msg.id}/report/`,
      snippet: getReadableMessageText(msg).slice(0, 120),
    }
    return
  }
  const targetUserId = msg.is_own ? msg.recipient_id : msg.sender_id
  const targetUsername = msg.is_own
    ? msg.recipient || selectedConversation.value?.username || ''
    : msg.sender || selectedConversation.value?.username || ''
  reportTarget.value = {
    userId: targetUserId,
    username: targetUsername,
    messageId: msg.id,
    snippet: getReadableMessageText(msg).slice(0, 120),
  }
}

async function ctxAction(action) {
  const conv = ctxMenu.value.conv
  closeCtxMenu()
  if (!conv) return
  if (conv.conversation_type === 'group') {
    try {
      const groupId = conv.group_id
      if (action === 'pin') {
        await apiPost(`/api/messages/groups/${groupId}/settings/pin/`, { value: !conv.is_pinned })
      } else if (action === 'mute') {
        const value = !conv.is_muted
        await apiPost(`/api/messages/groups/${groupId}/settings/mute/`, { value })
        conv.is_muted = value
        patchConversationByKey(`group:${groupId}`, { is_muted: value })
        if (selectedConversationKey.value === `group:${groupId}`) currentSettings.value.is_muted = value
        suppressNextConversationRefresh()
        ElMessage.success(value ? '已开启免打扰' : '已关闭免打扰')
        return
      } else if (action === 'archive') {
        await apiPost(`/api/messages/groups/${groupId}/settings/archive/`, { value: !conv.is_archived })
      } else if (action === 'mark_read_toggle') {
        const settingAction = conv.unread_count > 0 || conv.force_unread ? 'mark-read' : 'mark-unread'
        await apiPost(`/api/messages/groups/${groupId}/settings/${settingAction}/`, {})
      } else if (action === 'clear') {
        await ElMessageBox.confirm('清空该群组的聊天记录？', '确认', { type: 'warning' })
        await apiPost(`/api/messages/groups/${groupId}/settings/clear/`, {})
        if (selectedConversationKey.value === `group:${groupId}`) messages.value = []
      } else if (action === 'block') {
        ElMessage.info('群组不能拉黑，会话内可退出群组')
        return
      }
      ElMessage.success('操作成功')
      loadConversations()
    } catch (e) {
      if (e && e.message) ElMessage.error(e.message)
    }
    return
  }
  try {
    if (action === 'pin') {
      await apiPost('/api/messages/conversation/pin/', {
        user_id: conv.user_id,
        value: !conv.is_pinned,
      })
    } else if (action === 'mute') {
      const value = !conv.is_muted
      await apiPost('/api/messages/conversation/mute/', {
        user_id: conv.user_id,
        value,
      })
      conv.is_muted = value
      patchConversationByKey(`user:${normalizeUserId(conv.user_id)}`, { is_muted: value })
      if (selectedConversationKey.value === `user:${normalizeUserId(conv.user_id)}`) {
        currentSettings.value.is_muted = value
      }
      suppressNextConversationRefresh()
      ElMessage.success(value ? '已开启免打扰' : '已关闭免打扰')
      return
    } else if (action === 'archive') {
      await apiPost('/api/messages/conversation/archive/', {
        user_id: conv.user_id,
        value: !conv.is_archived,
      })
    } else if (action === 'mark_read_toggle') {
      const url =
        conv.unread_count > 0 || conv.force_unread
          ? '/api/messages/conversation/mark-read/'
          : '/api/messages/conversation/mark-unread/'
      await apiPost(url, { user_id: conv.user_id })
    } else if (action === 'clear') {
      await ElMessageBox.confirm('清空与该用户的聊天记录？', '确认', {
        type: 'warning',
      })
      await apiPost('/api/messages/conversation/clear/', { user_id: conv.user_id })
      if (selectedUserId.value === conv.user_id) messages.value = []
    } else if (action === 'block') {
      await ElMessageBox.confirm(`拉黑 ${conv.username}？`, '确认', { type: 'warning' })
      await apiPost('/api/users/block/', { user_id: conv.user_id })
      if (selectedUserId.value === conv.user_id) {
        selectedUserId.value = null
        selectedConversationKey.value = null
      }
    }
    ElMessage.success('操作成功')
    loadConversations()
  } catch (e) {
    if (e && e.message) ElMessage.error(e.message)
  }
}

// ==== 全局点击关闭菜单 / 移动端 ====
function onGlobalClick() {
  if (Date.now() - lastContextMenuOpenedAt < 250) return
  closeCtxMenu()
  closeMessageCtxMenu()
  activeMuteMenuUserId.value = null
  showChatMenu.value = false
}

function closeMobileChat() {
  mobileChatOpen.value = false
}

// ==== 轮询 ====
let pollTimer = null
let lastContextMenuOpenedAt = 0
let messagesPageTouchTimer = null
function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(() => {
    if (document.hidden) return
    if (realtimeState.value === 'connected') return
    if (scope.value !== 'blocked') loadConversations({ silent: true })
  }, 15000)
}

async function touchMessagesPagePresence() {
  try {
    await fetch('/api/messages/page-touch/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken.value,
      },
    })
  } catch (e) {
    console.warn('私信页活跃状态上报失败:', e)
  }
}

function startMessagesPageTouch() {
  touchMessagesPagePresence()
  messagesPageTouchTimer = setInterval(() => {
    if (!document.hidden) touchMessagesPagePresence()
  }, 60000)
}

function handleVisibilityChange() {
  if (document.hidden) return
  if (scope.value !== 'blocked') {
    loadConversations({ silent: true })
  }
  if (selectedConversationKey.value) {
    loadMessages({ silent: true })
  }
  touchMessagesPagePresence()
}

async function handleGroupInviteFromUrl() {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('group_invite')
  if (!token) return

  // Show preview instead of auto-joining
  groupInviteToken.value = token
  showGroupInvitePreview.value = true

  // Remove the parameter from URL
  const url = new URL(window.location.href)
  url.searchParams.delete('group_invite')
  window.history.replaceState({}, '', url.toString())
}

function closeGroupInvitePreview() {
  showGroupInvitePreview.value = false
  groupInviteToken.value = ''
}

async function handleGroupJoined(groupId) {
  // 不立即关闭弹窗，让 GroupInvitePreview 自己处理延迟关闭
  // showGroupInvitePreview 将在 GroupInvitePreview emit('close') 时由 closeGroupInvitePreview 处理

  // Reload conversations and select the group
  await loadConversations({ silent: true })
  const key = `group:${groupId}`
  const conv = findConversationByKey(key)
  if (conv) {
    selectConversation(conv)
  }
}

// ==== 生命周期 ====
onMounted(() => {
  currentUserId.value = getUserId()
  csrfToken.value = getCsrfToken()
  loadDraftsFromStorage()
  loadNotificationPreferences()
  loadConversations()
  handleGroupInviteFromUrl()
  initRealtimeMessages()
  startPolling()
  startMessagesPageTouch()
  document.addEventListener('click', onGlobalClick)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (messagesPageTouchTimer) clearInterval(messagesPageTouchTimer)
  clearTimeout(typingThrottleTimer)
  clearTimeout(typingHideTimer)
  if (isRecordingVoice.value) stopVoiceRecording()
  cleanupVoiceRecording()
  chatSocket?.close()
  document.removeEventListener('click', onGlobalClick)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

watch(selectedConversationKey, (v) => {
  if (v) {
    nextTick(() => {
      inputRef.value?.focus()
      resetComposerHeight()
    })
  }
})

watch(
  () => messages.value.length,
  (len, prev) => {
    if (len > prev) scrollToBottomSoon()
  }
)
</script>

<style scoped>
.messages-container {
  display: grid;
  grid-template-columns: 340px 1fr;
  height: calc(100vh - 64px);
  background: var(--bg-primary);
  color: var(--text-primary);
  gap: 0;
  position: relative;
}

/* ========== 左侧对话列表 ========== */
.conversations-sidebar {
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-header h2 {
  font-size: 20px;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary);
}

.new-message-btn {
  background: var(--primary-color);
  color: #fff;
  border: none;
  font-size: 14px;
  cursor: pointer;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s;
}

.new-message-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--primary-color, #2563eb) 35%, transparent);
}

.search-box {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  margin: 12px 14px 0;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  gap: 8px;
}

.search-box:focus-within {
  border-color: var(--primary-color);
}

.search-box i {
  color: var(--text-tertiary);
}

.search-box input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 14px;
  background: none;
  color: var(--text-primary);
}

.search-box input::placeholder {
  color: var(--text-tertiary);
}

.clear-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-tertiary);
  font-size: 14px;
  padding: 0;
  display: flex;
}

.tabs {
  display: flex;
  padding: 10px 12px 0;
  gap: 4px;
  border-bottom: 1px solid var(--border-color);
}

.tab {
  flex: 1;
  padding: 8px 6px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 6px 6px 0 0;
  font-size: 12.5px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
  position: relative;
}

.tab i {
  font-size: 13px;
}

.tab:hover {
  color: var(--text-primary);
}

.tab.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  font-weight: 600;
}

.tab-badge {
  position: absolute;
  top: 4px;
  right: 8px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  background: var(--danger-color, #ef4444);
  color: #fff;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.conversations-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 8px;
}

.scope-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 4px 10px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--bg-tertiary) 72%, transparent);
  border: 1px solid color-mix(in srgb, var(--border-color) 78%, transparent);
}

.scope-hint i {
  color: #64748b;
  font-size: 12px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60%;
  color: var(--text-tertiary);
  gap: 10px;
}

.empty-state i {
  font-size: 44px;
  opacity: 0.3;
}

.empty-state p {
  margin: 0;
  font-size: 13px;
}

/* 搜索结果 */
.search-results {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px 8px;
}

.search-results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 10px 8px;
  font-size: 12.5px;
  color: var(--text-tertiary);
}

.small-link {
  background: none;
  border: none;
  color: var(--primary-color);
  cursor: pointer;
  font-size: 12.5px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.result-row {
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: 10px;
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.result-row:hover {
  background: var(--bg-tertiary);
}

.result-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
}

.result-info {
  min-width: 0;
}

.result-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
}

.result-top h4 {
  margin: 0;
  font-size: 13.5px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-top .time {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.result-snippet {
  margin: 2px 0 0;
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-snippet :deep(mark) {
  background: rgba(250, 204, 21, 0.6);
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
}

/* ========== 右侧聊天区域 ========== */
.chat-area {
  display: flex;
  flex-direction: column;
  position: relative;
  background: var(--bg-primary);
  overflow: hidden;
}

.empty-chat-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
  gap: 10px;
}

.empty-chat-state i {
  font-size: 70px;
  opacity: 0.25;
}

.empty-chat-state p {
  margin: 0;
  text-align: center;
  font-size: 14px;
  line-height: 1.8;
}

.empty-chat-state .hint {
  font-size: 12.5px;
  color: var(--text-tertiary);
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);
  min-height: 64px;
}

.mobile-back-btn {
  display: none;
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}

.chat-user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.chat-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.chat-user-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-user-meta h2 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-subtitle {
  font-size: 12px;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.chat-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.action-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.15s;
}

.action-btn:hover {
  background: var(--bg-secondary);
  color: var(--primary-color);
}

.menu-wrap {
  position: relative;
}

.dropdown-menu {
  position: absolute;
  right: 0;
  top: 100%;
  margin-top: 8px;
  width: 200px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.12);
  padding: 6px;
  z-index: 100;
}

.dm-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-primary);
  font-size: 13px;
  border-radius: 6px;
  text-align: left;
}

.dm-item i {
  width: 16px;
  color: var(--text-secondary);
}

.dm-item:hover {
  background: var(--bg-secondary);
}

.dm-item.danger {
  color: var(--danger-color, #ef4444);
}

.dm-item.danger i {
  color: var(--danger-color, #ef4444);
}

.dm-item i.active {
  color: var(--primary-color);
}

.dm-sep {
  height: 1px;
  background: var(--border-color);
  margin: 4px 0;
}

.profile-card-overlay {
  position: fixed;
  inset: 0;
  z-index: 1300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
  background: rgba(15, 23, 42, 0.48);
}

.profile-card-modal {
  position: relative;
  width: min(440px, 100%);
  overflow: hidden;
  border-radius: 14px;
  background: var(--bg-primary);
  color: var(--text-primary);
  border: 1px solid color-mix(in srgb, var(--border-color) 78%, transparent);
  box-shadow: 0 22px 60px rgba(15, 23, 42, 0.24);
}

.profile-card-close {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 3;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.48);
  color: #fff;
  cursor: pointer;
}

.profile-cover-media {
  position: relative;
  height: 156px;
  overflow: hidden;
  background: #e5e7eb;
}

.profile-cover-media .cover-img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.profile-cover-media .cover-gradient {
  width: 100%;
  height: 100%;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--primary-color, #2563eb) 72%, #0f172a 28%), #14b8a6),
    #2563eb;
}

.cover-video-controls {
  position: absolute;
  left: 12px;
  bottom: 12px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.54);
  backdrop-filter: blur(8px);
}

.cover-ctrl-btn {
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
  cursor: pointer;
}

.cover-ctrl-btn:hover {
  background: rgba(255, 255, 255, 0.26);
}

.cover-volume-ctrl {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.cover-volume-slider {
  width: 76px;
  display: inline-flex;
}

.cover-volume-slider input {
  width: 100%;
  accent-color: #fff;
}

.profile-card-body {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0 22px 22px;
  text-align: center;
}

.profile-card-avatar {
  width: 78px;
  height: 78px;
  margin-top: -39px;
  border-radius: 50%;
  object-fit: cover;
  border: 4px solid var(--bg-primary);
  background: var(--bg-tertiary);
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.18);
}

.profile-card-body h3 {
  margin: 10px 0 6px;
  font-size: 18px;
  font-weight: 700;
}

.profile-card-bio {
  width: 100%;
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.profile-card-stats {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 16px;
}

.profile-stat {
  min-width: 0;
  padding: 10px 8px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--bg-secondary) 82%, transparent);
  color: var(--text-primary);
  text-decoration: none;
}

.profile-stat strong {
  display: block;
  font-size: 17px;
  line-height: 1.2;
}

.profile-stat span {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.public-notes-link {
  width: 100%;
  min-height: 38px;
  margin-top: 14px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--primary-color);
  color: #fff;
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
}

.disappearing-banner {
  padding: 8px 20px;
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
  font-size: 12.5px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--border-color);
}

.selection-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 10px 20px;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--primary-color, #2563eb) 14%, var(--bg-primary)) 0%, var(--bg-primary) 72%),
    var(--bg-primary);
  border-bottom: 1px solid color-mix(in srgb, var(--primary-color, #2563eb) 22%, var(--border-color));
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
  font-size: 13px;
  color: var(--text-secondary);
}

.selection-summary {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  color: var(--text-primary);
  font-weight: 600;
  white-space: nowrap;
}

.selection-summary strong {
  color: var(--primary-color);
  font-size: 15px;
  font-weight: 700;
}

.selection-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--primary-color);
  color: #fff;
  box-shadow: 0 6px 14px color-mix(in srgb, var(--primary-color, #2563eb) 28%, transparent);
}

.selection-icon i {
  font-size: 12px;
}

.selection-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  flex-wrap: wrap;
}

.selection-actions .link-btn,
.selection-actions .toolbar-btn {
  min-height: 32px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s, transform 0.15s, opacity 0.15s;
}

.selection-actions .link-btn {
  padding: 0 10px;
  border: 1px solid transparent;
  color: var(--text-secondary);
  text-decoration: none;
}

.selection-actions .link-btn:hover {
  background: color-mix(in srgb, var(--bg-secondary) 84%, transparent);
  color: var(--text-primary);
}

.selection-actions .toolbar-btn {
  padding: 0 12px;
  border: 1px solid color-mix(in srgb, var(--border-color) 78%, transparent);
  background: color-mix(in srgb, var(--bg-secondary) 58%, var(--bg-primary));
  color: var(--text-primary);
  cursor: pointer;
}

.selection-actions .toolbar-btn:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--primary-color, #2563eb) 36%, var(--border-color));
  background: color-mix(in srgb, var(--primary-color, #2563eb) 8%, var(--bg-primary));
  transform: translateY(-1px);
}

.selection-actions .toolbar-btn.primary {
  border-color: var(--primary-color);
  background: var(--primary-color);
  color: #fff;
  box-shadow: 0 6px 14px color-mix(in srgb, var(--primary-color, #2563eb) 24%, transparent);
}

.selection-actions .toolbar-btn.primary:hover:not(:disabled) {
  background: color-mix(in srgb, var(--primary-color, #2563eb) 88%, #0f172a 12%);
  border-color: color-mix(in srgb, var(--primary-color, #2563eb) 88%, #0f172a 12%);
}

.selection-actions .toolbar-btn.danger {
  border-color: color-mix(in srgb, var(--danger-color, #ef4444) 26%, var(--border-color));
  color: var(--danger-color, #ef4444);
}

.selection-actions .toolbar-btn.danger:hover:not(:disabled) {
  border-color: var(--danger-color, #ef4444);
  background: color-mix(in srgb, var(--danger-color, #ef4444) 9%, var(--bg-primary));
}

.selection-actions .toolbar-btn:disabled {
  opacity: 0.46;
  cursor: not-allowed;
  box-shadow: none;
}

.messages-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: var(--bg-secondary);
}

.messages-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
  gap: 8px;
}

.messages-state i {
  font-size: 40px;
  opacity: 0.3;
}

.messages-state p {
  margin: 0;
  font-size: 13.5px;
}

.messages-state .hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.date-sep {
  text-align: center;
  padding: 10px 0 14px;
  color: var(--text-tertiary);
  font-size: 11.5px;
  position: relative;
}

.date-sep::before,
.date-sep::after {
  content: '';
  display: inline-block;
  width: 60px;
  height: 1px;
  background: var(--border-color);
  vertical-align: middle;
  margin: 0 10px;
}

.date-sep-wrap {
  display: flex;
  justify-content: center;
}

.blocked-tip {
  padding: 20px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 13.5px;
}

.link-btn {
  background: none;
  border: none;
  color: var(--primary-color);
  cursor: pointer;
  font-size: 13.5px;
  padding: 0;
  text-decoration: underline;
}

.message-input-area {
  padding: 14px 20px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-primary);
}

.message-input {
  width: 100%;
  min-height: 72px;
  max-height: 180px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  background: var(--bg-secondary);
  color: var(--text-primary);
  transition: all 0.2s;
}

.message-input:focus {
  outline: none;
  border-color: var(--primary-color);
  background: var(--bg-primary);
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}

.char-count {
  font-size: 11.5px;
  color: var(--text-tertiary);
}

.char-count.warn {
  color: #f59e0b;
}

.shortcut-hint {
  font-size: 11.5px;
  color: var(--text-tertiary);
  align-self: flex-start;
  padding-left: 2px;
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: var(--primary-color);
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 14px color-mix(in srgb, var(--primary-color, #2563eb) 35%, transparent);
}

.send-btn:disabled {
  background: var(--border-color);
  color: var(--text-tertiary);
  cursor: not-allowed;
}

/* ========== 右键菜单 ========== */
.context-menu {
  position: fixed;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  padding: 6px;
  z-index: 1000;
  min-width: 200px;
}

/* ========== 右侧重构样式覆盖（毛玻璃 + 新交互） ========== */
.chat-container {
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--bg-primary) 92%, transparent),
    color-mix(in srgb, var(--bg-secondary) 88%, transparent)
  );
}

.chat-header {
  position: sticky;
  top: 0;
  z-index: 8;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  background: color-mix(in srgb, var(--bg-primary) 76%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--border-color) 70%, transparent);
}

.secure-subtitle {
  gap: 8px;
}

.presence-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 3px color-mix(in srgb, #22c55e 18%, transparent);
}

.presence-dot.offline {
  background: #94a3b8;
  box-shadow: none;
}

.secure-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--bg-secondary) 75%, transparent);
  border: 1px solid color-mix(in srgb, var(--border-color) 75%, transparent);
}

.messages-list {
  display: flex;
  flex-direction: column;
  padding: 14px 22px 10px;
}

.scroll-bottom-btn {
  position: absolute;
  right: 28px;
  bottom: 108px;
  z-index: 18;
  width: 42px;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--border-color) 78%, transparent);
  border-radius: 50%;
  background: color-mix(in srgb, var(--bg-primary) 88%, transparent);
  color: var(--primary-color);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.14);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  cursor: pointer;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    background 0.18s ease,
    border-color 0.18s ease;
}

.scroll-bottom-btn i {
  font-size: 15px;
  line-height: 1;
}

.scroll-bottom-btn:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--primary-color) 34%, var(--border-color));
  background: color-mix(in srgb, var(--primary-color) 10%, var(--bg-primary));
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.18);
}

.scroll-bottom-btn:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--primary-color) 45%, transparent);
  outline-offset: 3px;
}

.scroll-bottom-badge {
  position: absolute;
  top: -7px;
  right: -7px;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--bg-primary);
  border-radius: 999px;
  background: #f56c6c;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  box-shadow: 0 6px 14px rgba(245, 108, 108, 0.28);
}

.message-stream {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-panel-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  background: rgba(15, 23, 42, 0.48);
  backdrop-filter: blur(3px);
  -webkit-backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.group-panel {
  width: min(632px, 100%);
  max-height: min(760px, 88vh);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--bg-primary) 98%, #f8fafc 2%), var(--bg-primary));
  color: var(--text-primary);
  border: 1px solid color-mix(in srgb, var(--border-color) 82%, transparent);
  border-radius: 10px;
  box-shadow: 0 24px 72px rgba(15, 23, 42, 0.28);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.group-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 86px;
  padding: 22px 24px;
  border-bottom: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--bg-primary) 96%, var(--bg-secondary) 4%), var(--bg-primary));
}

.group-panel-heading {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 14px;
}

.group-panel-mark {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  color: color-mix(in srgb, var(--accent-color) 88%, #2563eb 12%);
  background: color-mix(in srgb, var(--accent-color) 12%, var(--bg-primary) 88%);
  border: 1px solid color-mix(in srgb, var(--accent-color) 18%, var(--border-color) 82%);
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.08);
}

.group-panel-mark i {
  font-size: 18px;
}

.group-panel-header h3 {
  margin: 0;
  font-size: 18px;
  line-height: 1.35;
  font-weight: 700;
}

.group-panel-header p {
  margin: 6px 0 0;
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.35;
}

.group-panel-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-gutter: stable;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--bg-secondary) 28%, transparent), transparent 160px);
}

.group-panel .close-btn {
  appearance: none;
  -webkit-appearance: none;
  width: 38px;
  height: 38px;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
  border-radius: 9px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font: inherit;
  line-height: 1;
  transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease, transform 0.16s ease, box-shadow 0.16s ease;
}

.group-panel .close-btn:hover {
  border-color: color-mix(in srgb, var(--danger-color, #ef4444) 32%, var(--border-color));
  background: color-mix(in srgb, var(--danger-color, #ef4444) 8%, var(--bg-primary));
  color: var(--danger-color, #ef4444);
  transform: translateY(-1px);
}

.group-panel .close-btn:focus-visible,
.group-primary-btn:focus-visible,
.group-secondary-btn:focus-visible,
.group-danger-btn:focus-visible,
.group-icon-btn:focus-visible,
.group-mute-menu-item:focus-visible,
.group-member-row.invite:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary-color, #2563eb) 18%, transparent);
}

.group-panel-state {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-tertiary);
}

.group-panel-state.is-error {
  flex-direction: column;
  padding: 28px 24px;
  text-align: center;
  color: var(--text-secondary);
}

.group-panel-state.is-error i {
  color: var(--danger-color, #ef4444);
  font-size: 22px;
}

.group-panel-state.is-error strong {
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.35;
}

.group-panel-state.is-error span {
  max-width: 360px;
  line-height: 1.5;
}

.group-edit-row,
.group-config-box,
.group-pinned-box,
.group-add-box,
.group-invite-box,
.group-members,
.group-panel-footer {
  padding: 16px 20px;
}

.group-edit-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
}

.group-config-box,
.group-add-box {
  border-bottom: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
}

.group-pinned-box,
.group-config-box,
.group-invite-box {
  border-bottom: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.group-config-box.compact {
  gap: 14px;
}

.group-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.group-section-title span {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.group-section-title i {
  color: var(--primary-color, #2563eb);
}

.group-section-title.subtle {
  margin-bottom: 10px;
  color: var(--text-secondary);
}

.group-announcement-banner {
  appearance: none;
  -webkit-appearance: none;
  width: 100%;
  min-height: 54px;
  border: 0;
  border-bottom: 1px solid color-mix(in srgb, var(--primary-color, #2563eb) 18%, var(--border-color));
  padding: 10px 20px;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) 22px;
  align-items: center;
  gap: 11px;
  background:
    linear-gradient(135deg, color-mix(in srgb, #f59e0b 16%, var(--bg-primary)) 0%, var(--bg-primary) 70%),
    var(--bg-primary);
  color: var(--text-primary);
  cursor: pointer;
  text-align: left;
  transition: background 0.16s ease, box-shadow 0.16s ease;
}

.group-announcement-banner:hover {
  background:
    linear-gradient(135deg, color-mix(in srgb, #f59e0b 22%, var(--bg-primary)) 0%, var(--bg-primary) 74%),
    var(--bg-primary);
  box-shadow: inset 0 -1px 0 color-mix(in srgb, #f59e0b 18%, transparent);
}

.announcement-banner-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, #f59e0b 18%, var(--bg-primary));
  color: #b45309;
  flex-shrink: 0;
}

.announcement-banner-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.announcement-banner-main strong {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.2;
}

.announcement-banner-main em {
  padding: 2px 6px;
  border-radius: 999px;
  background: color-mix(in srgb, #f59e0b 18%, var(--bg-primary));
  color: #92400e;
  font-style: normal;
  font-size: 11px;
  font-weight: 700;
}

.announcement-banner-main span {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 12.5px;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-announcement-banner > i {
  color: color-mix(in srgb, var(--text-tertiary) 82%, transparent);
  font-size: 13px;
}

.group-section-meta {
  flex: 0 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 500;
}

.group-pinned-message {
  appearance: none;
  -webkit-appearance: none;
  width: 100%;
  min-height: 42px;
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--primary-color, #2563eb) 18%, var(--border-color));
  border-radius: 10px;
  background: color-mix(in srgb, var(--primary-color, #2563eb) 6%, var(--bg-primary));
  color: var(--text-primary);
  font: inherit;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.group-add-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 52px;
  gap: 10px;
}

.group-input {
  width: 100%;
  min-width: 0;
  height: 42px;
  padding: 0 13px;
  border: 1px solid color-mix(in srgb, var(--border-color) 80%, transparent);
  border-radius: 9px;
  background: color-mix(in srgb, var(--bg-secondary) 72%, var(--bg-primary));
  color: var(--text-primary);
  outline: none;
  transition: border-color 0.16s ease, background 0.16s ease, box-shadow 0.16s ease;
}

.group-input:focus {
  border-color: var(--primary-color, #2563eb);
  background: var(--bg-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary-color, #2563eb) 14%, transparent);
}

.group-textarea {
  width: 100%;
  min-height: 86px;
  max-height: 180px;
  resize: vertical;
  padding: 11px 13px;
  border: 1px solid color-mix(in srgb, var(--border-color) 80%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--bg-secondary) 70%, var(--bg-primary));
  color: var(--text-primary);
  font: inherit;
  font-size: 13px;
  line-height: 1.55;
  outline: none;
  transition: border-color 0.16s ease, background 0.16s ease, box-shadow 0.16s ease;
}

.group-textarea:focus {
  border-color: var(--primary-color, #2563eb);
  background: var(--bg-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary-color, #2563eb) 14%, transparent);
}

.group-textarea.small {
  min-height: 74px;
  max-height: 140px;
  font-size: 12.5px;
}

.group-config-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.group-check {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  user-select: none;
}

.group-check input,
.group-switch-row input[type='checkbox'] {
  appearance: none;
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  margin: 0;
  border: 1px solid color-mix(in srgb, var(--border-color) 82%, transparent);
  border-radius: 5px;
  background: var(--bg-primary);
  display: inline-grid;
  place-content: center;
  cursor: pointer;
  transition: background 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.group-check input::after,
.group-switch-row input[type='checkbox']::after {
  content: '';
  width: 9px;
  height: 5px;
  border-left: 2px solid #fff;
  border-bottom: 2px solid #fff;
  transform: rotate(-45deg) scale(0);
  transform-origin: center;
  transition: transform 0.14s ease;
}

.group-check input:checked,
.group-switch-row input[type='checkbox']:checked {
  border-color: var(--primary-color, #2563eb);
  background: var(--primary-color, #2563eb);
}

.group-check input:checked::after,
.group-switch-row input[type='checkbox']:checked::after {
  transform: rotate(-45deg) scale(1);
}

.group-check input:focus-visible,
.group-switch-row input[type='checkbox']:focus-visible,
.group-select:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary-color, #2563eb) 16%, transparent);
}

.group-history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-history-row {
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--border-color) 76%, transparent);
  border-radius: 9px;
  background: color-mix(in srgb, var(--bg-secondary) 56%, transparent);
  transition: border-color 0.16s ease, background 0.16s ease;
}

.group-history-row.pinned {
  border-color: color-mix(in srgb, #f59e0b 38%, var(--border-color));
  background: color-mix(in srgb, #f59e0b 8%, var(--bg-primary));
}

.group-history-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
}

.group-history-jump,
.group-history-content {
  appearance: none;
  -webkit-appearance: none;
  min-width: 0;
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  font: inherit;
  cursor: pointer;
}

.group-history-jump {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.group-history-jump span {
  margin: 0;
}

.group-history-jump strong {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 999px;
  background: color-mix(in srgb, #f59e0b 16%, var(--bg-primary));
  color: #92400e;
  font-size: 11px;
  line-height: 1.2;
  white-space: nowrap;
}

.group-history-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.group-history-actions.compact {
  justify-content: flex-end;
  gap: 5px;
}

.group-history-action-spacer {
  flex: 1 1 auto;
}

.group-history-content {
  width: 100%;
  margin-top: 7px;
  color: var(--text-secondary);
  font-size: 12.5px;
  line-height: 1.45;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-history-content:hover,
.group-history-jump:hover {
  color: var(--primary-color, #2563eb);
}

.group-history-jump > span {
  display: block;
  margin: 0;
  color: var(--text-tertiary);
  font-size: 11px;
}

.group-history-row p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-toggle-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.group-switch-row {
  min-width: 0;
  min-height: 68px;
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--border-color) 76%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--bg-secondary) 58%, var(--bg-primary));
  cursor: pointer;
}

.group-switch-row:hover {
  border-color: color-mix(in srgb, var(--primary-color, #2563eb) 20%, var(--border-color));
  background: var(--bg-primary);
}

.group-switch-row span {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.group-switch-row strong {
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.25;
}

.group-switch-row em {
  color: var(--text-tertiary);
  font-style: normal;
  font-size: 12px;
  line-height: 1.35;
}

.group-switch-row.select-row {
  grid-column: 1 / -1;
  grid-template-columns: minmax(0, 1fr) minmax(150px, 210px);
}

.group-select {
  width: 100%;
  height: 36px;
  min-width: 0;
  padding: 0 34px 0 11px;
  border: 1px solid color-mix(in srgb, var(--border-color) 80%, transparent);
  border-radius: 9px;
  background:
    linear-gradient(45deg, transparent 50%, var(--text-tertiary) 50%) calc(100% - 17px) 15px / 6px 6px no-repeat,
    linear-gradient(135deg, var(--text-tertiary) 50%, transparent 50%) calc(100% - 12px) 15px / 6px 6px no-repeat,
    color-mix(in srgb, var(--bg-primary) 86%, var(--bg-secondary));
  color: var(--text-primary);
  font: inherit;
  font-size: 13px;
  appearance: none;
  -webkit-appearance: none;
}

.group-primary-btn,
.group-secondary-btn,
.group-danger-btn,
.group-icon-btn {
  appearance: none;
  -webkit-appearance: none;
  height: 38px;
  border-radius: 9px;
  border: 1px solid color-mix(in srgb, var(--border-color) 82%, transparent);
  padding: 0 13px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  white-space: nowrap;
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  line-height: 1;
  text-decoration: none;
  user-select: none;
  transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease, transform 0.16s ease, box-shadow 0.16s ease, opacity 0.16s ease;
}

.group-primary-btn {
  border-color: var(--primary-color, #2563eb);
  background: var(--primary-color, #2563eb);
  color: #fff;
  box-shadow: 0 8px 18px color-mix(in srgb, var(--primary-color, #2563eb) 24%, transparent);
}

.group-primary-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px color-mix(in srgb, var(--primary-color, #2563eb) 28%, transparent);
}

.group-secondary-btn {
  background: color-mix(in srgb, var(--bg-secondary) 78%, var(--bg-primary));
  color: var(--text-secondary);
}

.group-secondary-btn:hover:not(:disabled),
.group-icon-btn:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--primary-color, #2563eb) 34%, var(--border-color));
  background: color-mix(in srgb, var(--primary-color, #2563eb) 7%, var(--bg-primary));
  color: var(--primary-color, #2563eb);
  transform: translateY(-1px);
}

.group-secondary-btn.small {
  height: 34px;
  padding: 0 11px;
  font-size: 12px;
}

.group-primary-btn.small {
  height: 34px;
  padding: 0 11px;
  font-size: 12px;
}

.group-secondary-btn.small:disabled {
  background: color-mix(in srgb, var(--bg-secondary) 62%, var(--bg-primary));
  color: var(--text-tertiary);
}

.group-danger-btn,
.group-icon-btn.danger {
  border-color: color-mix(in srgb, var(--danger-color, #ef4444) 32%, var(--border-color));
  background: color-mix(in srgb, var(--danger-color, #ef4444) 7%, var(--bg-primary));
  color: var(--danger-color, #dc2626);
}

.group-danger-btn:hover:not(:disabled),
.group-icon-btn.danger:hover:not(:disabled) {
  border-color: var(--danger-color, #ef4444);
  background: color-mix(in srgb, var(--danger-color, #ef4444) 12%, var(--bg-primary));
  color: var(--danger-color, #dc2626);
  transform: translateY(-1px);
}

.group-primary-btn:disabled,
.group-secondary-btn:disabled,
.group-danger-btn:disabled,
.group-icon-btn:disabled {
  opacity: 0.52;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}

.group-add-search .group-secondary-btn {
  width: 52px;
  padding: 0;
  flex: 0 0 auto;
}

.group-members {
  overflow: visible;
  min-height: 0;
  max-height: none;
}

.member-title {
  margin-bottom: 8px;
}

.group-inline-state {
  min-height: 34px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: 12px;
  padding: 8px 10px;
  border: 1px dashed color-mix(in srgb, var(--border-color) 82%, transparent);
  border-radius: 9px;
  background: color-mix(in srgb, var(--bg-secondary) 52%, transparent);
}

.group-invite-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-invite-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 34px 34px;
  gap: 8px;
  align-items: center;
  min-height: 50px;
  padding: 9px 10px;
  border: 1px solid color-mix(in srgb, var(--border-color) 82%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--bg-secondary) 66%, var(--bg-primary));
  transition: border-color 0.16s ease, background 0.16s ease, box-shadow 0.16s ease;
}

.group-invite-row:hover {
  border-color: color-mix(in srgb, var(--primary-color, #2563eb) 20%, var(--border-color));
  background: var(--bg-primary);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}

.group-invite-row.disabled {
  opacity: 0.62;
}

.group-invite-row.disabled .group-icon-btn:not(.danger) {
  color: var(--text-tertiary);
}

.group-invite-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.group-invite-meta strong {
  font-size: 12px;
}

.group-invite-meta span {
  color: var(--text-tertiary);
  font-size: 11px;
}

.group-member-row {
  width: 100%;
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-height: 58px;
  padding: 8px 8px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--text-primary);
  text-align: left;
  transition: background 0.16s ease, border-color 0.16s ease;
}

.group-member-row:hover {
  border-color: color-mix(in srgb, var(--border-color) 68%, transparent);
  background: color-mix(in srgb, var(--bg-secondary) 50%, transparent);
}

.group-member-row.invite {
  appearance: none;
  -webkit-appearance: none;
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--primary-color, #2563eb) 18%, var(--border-color));
  border-radius: 10px;
  background: color-mix(in srgb, var(--primary-color, #2563eb) 6%, var(--bg-secondary));
  cursor: pointer;
  font: inherit;
}

.group-member-row.invite:hover {
  border-color: color-mix(in srgb, var(--primary-color, #2563eb) 32%, var(--border-color));
  background: color-mix(in srgb, var(--primary-color, #2563eb) 9%, var(--bg-primary));
}

.group-member-row img {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  object-fit: cover;
  box-shadow: 0 0 0 2px var(--bg-primary);
}

.group-member-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.group-member-meta strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.group-member-meta span {
  color: var(--text-tertiary);
  font-size: 12px;
}

.group-member-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.group-mute-menu-wrap {
  position: relative;
  flex: 0 0 auto;
}

.group-icon-btn {
  width: 34px;
  height: 34px;
  padding: 0;
  flex: 0 0 auto;
}

.group-icon-btn.active,
.group-icon-btn.muted {
  border-color: color-mix(in srgb, var(--danger-color, #f56c6c) 42%, transparent);
  color: var(--danger-color, #f56c6c);
  background: color-mix(in srgb, var(--danger-color, #f56c6c) 9%, transparent);
}

.group-mute-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 60;
  width: 168px;
  padding: 6px;
  border: 1px solid color-mix(in srgb, var(--border-color) 78%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--bg-primary) 96%, var(--bg-secondary));
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.18);
}

.group-mute-menu::before {
  content: '';
  position: absolute;
  top: -5px;
  right: 13px;
  width: 8px;
  height: 8px;
  border-left: 1px solid var(--border-color);
  border-top: 1px solid var(--border-color);
  background: var(--bg-primary);
  transform: rotate(45deg);
}

.group-mute-menu-title {
  padding: 5px 8px 4px;
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 1.2;
}

.group-mute-menu-item {
  appearance: none;
  -webkit-appearance: none;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 30px;
  padding: 0 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-primary);
  font: inherit;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: background 0.14s ease, color 0.14s ease;
}

.group-mute-menu-item:hover {
  background: color-mix(in srgb, var(--primary-color, #2563eb) 8%, var(--bg-secondary));
  color: var(--primary-color, #2563eb);
}

.group-mute-menu-item.primary {
  color: var(--success-color, #16a34a);
}

.group-mute-menu-separator {
  height: 1px;
  margin: 5px 4px;
  background: var(--border-color);
}

.group-panel-footer {
  border-top: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
  display: flex;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  background: color-mix(in srgb, var(--bg-secondary) 36%, var(--bg-primary));
}

.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin: 6px 0 2px;
  padding: 8px 12px;
  width: fit-content;
  max-width: 220px;
  border-radius: 14px;
  background: color-mix(in srgb, var(--bg-tertiary) 78%, transparent);
  color: var(--text-secondary);
  font-size: 12.5px;
}

.typing-dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.typing-dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
  display: block;
  animation: typing-bounce 1s infinite ease-in-out;
}

.typing-dots i:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dots i:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes typing-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.45; }
  40% { transform: translateY(-3px); opacity: 1; }
}

.date-sep {
  position: sticky;
  top: 6px;
  z-index: 2;
  font-size: 11px;
  color: var(--text-tertiary);
}

.date-sep::before,
.date-sep::after {
  width: 74px;
}

.message-input-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  background: color-mix(in srgb, var(--bg-primary) 78%, transparent);
}

.composer-shell {
  position: relative;
  display: grid;
  grid-template-columns: auto auto auto auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 6px;
  padding: 8px;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--border-color) 78%, transparent);
  background: color-mix(in srgb, var(--bg-secondary) 76%, var(--bg-primary) 24%);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}

.composer-shell:focus-within {
  border-color: color-mix(in srgb, var(--primary-color) 58%, var(--border-color));
  background: var(--bg-primary);
}

.tool-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tool-btn:hover:not(:disabled) {
  color: var(--primary-color);
  background: color-mix(in srgb, var(--bg-tertiary) 88%, transparent);
}

.tool-btn.recording {
  color: #fff;
  background: var(--danger-color, #ef4444);
  animation: recordingPulse 1.2s ease-in-out infinite;
}

.tool-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@keyframes recordingPulse {
  0%, 100% {
    box-shadow: 0 0 0 0 color-mix(in srgb, #ef4444 35%, transparent);
  }
  50% {
    box-shadow: 0 0 0 5px color-mix(in srgb, #ef4444 0%, transparent);
  }
}

.hidden-file-input {
  display: none;
}

.emoji-picker {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 4px;
  padding: 8px;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
  background: color-mix(in srgb, var(--bg-secondary) 84%, transparent);
}

.emoji-btn {
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  padding: 7px 0;
}

.emoji-btn:hover {
  background: color-mix(in srgb, var(--bg-tertiary) 85%, transparent);
}

.mention-picker {
  position: absolute;
  left: 156px;
  right: 118px;
  bottom: calc(100% + 8px);
  z-index: 70;
  max-height: 274px;
  overflow-y: auto;
  padding: 6px;
  border: 1px solid color-mix(in srgb, var(--border-color) 78%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--bg-primary) 96%, var(--bg-secondary));
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.18);
}

.mention-option {
  appearance: none;
  -webkit-appearance: none;
  width: 100%;
  min-height: 44px;
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  align-items: center;
  gap: 9px;
  padding: 6px 8px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--text-primary);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.mention-option:hover,
.mention-option.active {
  background: color-mix(in srgb, var(--primary-color) 9%, var(--bg-secondary));
}

.mention-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
  background: var(--bg-secondary);
}

.mention-avatar-all {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color) 12%, var(--bg-secondary));
}

.mention-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mention-meta strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  line-height: 1.2;
}

.mention-meta em {
  color: var(--text-tertiary);
  font-size: 11px;
  font-style: normal;
  line-height: 1.2;
}

.mention-empty {
  padding: 12px;
  color: var(--text-tertiary);
  font-size: 12px;
  text-align: center;
}

.attachment-tray {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pending-attachment {
  display: grid;
  grid-template-columns: auto minmax(0, 150px) auto;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--bg-secondary) 76%, transparent);
  border: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
  font-size: 12px;
}

.pending-attachment.type-image {
  grid-template-columns: 34px minmax(0, 140px) auto;
}

.pending-image {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  object-fit: cover;
}

.pending-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
}

.pending-remove {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  width: 24px;
  height: 24px;
  border-radius: 50%;
}

.pending-remove:hover {
  background: color-mix(in srgb, var(--bg-tertiary) 85%, transparent);
  color: var(--danger-color, #ef4444);
}

.reply-draft-bar {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  padding: 8px 10px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--bg-secondary) 72%, transparent);
  border: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
}

.reply-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--primary-color);
  font-weight: 600;
}

.reply-preview {
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-secondary);
}

.reply-cancel-btn {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  width: 24px;
  height: 24px;
  border-radius: 50%;
}

.reply-cancel-btn:hover {
  background: color-mix(in srgb, var(--bg-tertiary) 85%, transparent);
  color: var(--text-primary);
}

.message-input {
  min-height: 38px;
  max-height: 180px;
  height: 38px;
  padding: 8px 10px;
  border: none;
  border-radius: 10px;
  background: transparent;
  box-shadow: none;
}

.message-input:focus {
  background: transparent;
  border: none;
}

.send-btn {
  min-width: 82px;
  width: auto;
  height: 40px;
  padding: 0 16px;
  border-radius: 14px;
  gap: 6px;
  flex-shrink: 0;
}

.send-btn.compact {
  min-width: 100px;
}

.code-input-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border-radius: 14px;
  border: 1px solid color-mix(in srgb, var(--border-color) 72%, transparent);
  background: color-mix(in srgb, var(--bg-secondary) 84%, transparent);
}

.code-input {
  width: 100%;
  min-height: 132px;
  max-height: 260px;
  resize: vertical;
  border: 1px solid color-mix(in srgb, var(--border-color) 78%, transparent);
  border-radius: 10px;
  padding: 10px 12px;
  background: color-mix(in srgb, #0f172a 92%, #1e293b 8%);
  color: #e2e8f0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 12.5px;
  line-height: 1.55;
}

.code-input:focus {
  outline: none;
  border-color: color-mix(in srgb, var(--primary-color) 60%, transparent);
}

.code-input-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 2px;
}

.code-action-btn {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease, opacity 0.16s ease;
}

.code-action-btn i {
  font-size: 12px;
}

.code-action-btn.ghost {
  background: transparent;
  border-color: color-mix(in srgb, var(--border-color) 62%, transparent);
  color: var(--text-secondary);
}

.code-action-btn.ghost:hover:not(:disabled) {
  background: color-mix(in srgb, var(--bg-tertiary) 84%, transparent);
  color: var(--text-primary);
}

.code-action-btn.secondary {
  background: color-mix(in srgb, var(--bg-primary) 72%, var(--bg-secondary));
  border-color: color-mix(in srgb, var(--border-color) 82%, transparent);
  color: var(--text-primary);
}

.code-action-btn.secondary:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--primary-color, #2563eb) 36%, var(--border-color));
  background: color-mix(in srgb, var(--primary-color, #2563eb) 8%, var(--bg-primary));
  transform: translateY(-1px);
}

.code-action-btn.primary {
  min-width: 108px;
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: #fff;
  box-shadow: 0 8px 18px color-mix(in srgb, var(--primary-color, #2563eb) 24%, transparent);
}

.code-action-btn.primary:hover:not(:disabled) {
  background: color-mix(in srgb, var(--primary-color, #2563eb) 88%, #0f172a 12%);
  border-color: color-mix(in srgb, var(--primary-color, #2563eb) 88%, #0f172a 12%);
  transform: translateY(-1px);
}

.code-action-btn:disabled {
  opacity: 0.48;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}

.send-text {
  font-size: 13px;
  font-weight: 600;
}

/* ========== 鍝嶅簲寮?========== */
@media (max-width: 768px) {
  .messages-container {
    grid-template-columns: 1fr;
  }

  .chat-area {
    display: none;
  }

  .messages-container.mobile-chat-open .conversations-sidebar {
    display: none;
  }

  .messages-container.mobile-chat-open .chat-area {
    display: flex;
  }

  .mobile-back-btn {
    display: flex;
  }

  .selection-banner {
    align-items: flex-start;
    flex-direction: column;
    padding: 10px 12px;
  }

  .group-announcement-banner {
    min-height: 58px;
    grid-template-columns: 32px minmax(0, 1fr) 18px;
    padding: 10px 12px;
    gap: 9px;
  }

  .announcement-banner-icon {
    width: 32px;
    height: 32px;
  }

  .announcement-banner-main span {
    white-space: normal;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .selection-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .selection-actions .toolbar-btn {
    flex: 1 1 auto;
    min-width: 96px;
  }

  .scroll-bottom-btn {
    right: 16px;
    bottom: 94px;
    width: 40px;
    height: 40px;
  }

  .code-input-actions {
    justify-content: stretch;
  }

  .code-action-btn {
    flex: 1 1 88px;
    padding: 0 10px;
  }

  .selection-actions .link-btn {
    padding-left: 0;
  }

  .message-input-area {
    padding: 10px 12px;
  }

  .composer-shell {
    grid-template-columns: auto auto auto auto minmax(0, 1fr) auto;
    gap: 4px;
    padding: 7px;
    border-radius: 16px;
  }

  .mention-picker {
    left: 8px;
    right: 8px;
  }

  .composer-shell .char-count {
    display: none;
  }

  .tool-btn {
    width: 34px;
    height: 34px;
  }

  .group-panel-overlay {
    align-items: stretch;
    padding: 10px;
  }

  .group-panel {
    width: 100%;
    max-height: calc(100vh - 20px);
  }

  .group-panel-header,
  .group-edit-row,
  .group-config-box,
  .group-pinned-box,
  .group-add-box,
  .group-invite-box,
  .group-members,
  .group-panel-footer {
    padding-left: 14px;
    padding-right: 14px;
  }

  .group-panel-header {
    min-height: 78px;
    padding-top: 18px;
    padding-bottom: 18px;
  }

  .group-panel-heading {
    gap: 12px;
  }

  .group-panel-mark {
    width: 40px;
    height: 40px;
    border-radius: 11px;
  }

  .group-edit-row {
    grid-template-columns: 1fr;
  }

  .group-edit-row .group-primary-btn {
    width: 100%;
  }

  .group-toggle-grid,
  .group-switch-row.select-row {
    grid-template-columns: 1fr;
  }

  .group-switch-row.select-row {
    gap: 10px;
  }

  .group-config-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .group-history-head {
    grid-template-columns: minmax(0, 1fr);
  }

  .group-history-actions.compact {
    justify-content: flex-start;
  }

  .group-history-actions {
    align-items: stretch;
  }

  .group-history-actions .group-check {
    width: 100%;
  }

  .group-history-action-spacer {
    display: none;
  }

  .group-config-actions .group-secondary-btn {
    width: 100%;
  }

  .group-add-search {
    grid-template-columns: minmax(0, 1fr) 46px;
  }

  .group-add-search .group-secondary-btn {
    width: 46px;
  }

  .group-member-row {
    grid-template-columns: 34px minmax(0, 1fr);
  }

  .group-member-row img {
    width: 34px;
    height: 34px;
  }

  .group-member-actions,
  .group-member-row > .group-icon-btn {
    grid-column: 1 / -1;
    justify-content: flex-start;
    padding-left: 44px;
  }

  .group-invite-row {
    grid-template-columns: minmax(0, 1fr) 34px 34px;
  }

  .group-panel-footer {
    flex-direction: column;
  }

  .group-panel-footer .group-secondary-btn,
  .group-panel-footer .group-danger-btn {
    width: 100%;
  }

  .send-btn {
    min-width: 42px;
    width: 42px;
    padding: 0;
  }

  .send-text {
    display: none;
  }
}

/* ==== Turnstile 兜底弹窗 ==== */
.turnstile-gate-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.turnstile-gate-card {
  background: var(--bg-primary, #fff);
  color: var(--text-primary, #333);
  border-radius: 12px;
  padding: 24px;
  max-width: 400px;
  width: 92%;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25);
}

.turnstile-gate-card h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.turnstile-gate-desc {
  font-size: 13px;
  color: var(--text-secondary, #666);
  line-height: 1.6;
  margin: 0 0 16px 0;
}

.turnstile-gate-body {
  min-height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.turnstile-gate-loading {
  color: var(--text-tertiary, #999);
  font-size: 13px;
  display: inline-flex;
  gap: 8px;
  align-items: center;
}

.turnstile-gate-actions {
  display: flex;
  justify-content: flex-end;
}

.turnstile-gate-actions .btn-ghost {
  padding: 8px 16px;
  background: transparent;
  border: 1px solid var(--border-color, #d0d0d0);
  color: var(--text-primary, #333);
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.turnstile-gate-actions .btn-ghost:hover {
  background: var(--bg-tertiary, #f2f2f2);
}
</style>

<style>
/* 修复 Element Plus Message 图标异常放大的问题 */
.el-message__icon {
  font-size: 16px !important;
  width: 16px !important;
  height: 16px !important;
  flex-shrink: 0 !important;
}

.el-message__icon svg {
  width: 16px !important;
  height: 16px !important;
}

/* 确保 MessageBox 对话框显示在最上层且居中 */
.el-message-box__wrapper {
  z-index: 3000 !important;
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

.el-overlay {
  z-index: 2999 !important;
}

/* 公告跳转失败对话框的特殊样式 */
.announcement-jump-failed-dialog {
  z-index: 3001 !important;
}

/* 自定义公告对话框 */
.announcement-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(2px);
}

.announcement-dialog {
  background: white;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  min-width: 400px;
  max-width: 500px;
  overflow: hidden;
}

.announcement-dialog-header {
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  gap: 12px;
}

.announcement-dialog-header i {
  color: #f59e0b;
  font-size: 22px;
}

.announcement-dialog-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.announcement-dialog-body {
  padding: 24px;
  line-height: 1.6;
}

.announcement-dialog-body p {
  margin: 0 0 12px 0;
  color: #4b5563;
  font-size: 14px;
}

.announcement-dialog-body p:last-child {
  margin-bottom: 0;
}

.announcement-dialog-body .hint-text {
  font-size: 13px;
  color: #9ca3af;
  font-style: italic;
}

.announcement-dialog-footer {
  padding: 16px 24px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.announcement-dialog-footer button {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.announcement-dialog-footer .btn-cancel {
  background: #f3f4f6;
  color: #6b7280;
}

.announcement-dialog-footer .btn-cancel:hover {
  background: #e5e7eb;
}

.announcement-dialog-footer .btn-confirm {
  background: #3b82f6;
  color: white;
}

.announcement-dialog-footer .btn-confirm:hover {
  background: #2563eb;
}

/* 跳转高亮动画 */
.jump-highlighted {
  animation: jumpHighlight 2.5s ease-out;
}

@keyframes jumpHighlight {
  0% {
    background-color: #fef3c7;
    box-shadow: 0 0 0 4px #fbbf24;
    transform: scale(1.02);
  }
  10% {
    background-color: #fef3c7;
    box-shadow: 0 0 0 4px #fbbf24;
    transform: scale(1.02);
  }
  100% {
    background-color: transparent;
    box-shadow: none;
    transform: scale(1);
  }
}
</style>
