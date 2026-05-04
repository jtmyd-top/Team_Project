// 公开笔记详情页 - 三栏布局 + 评论区
document.addEventListener('DOMContentLoaded', async function () {
  const { convertUbbMarkupInHtml, renderCommentUbb, hydrateUbbDom } = await import('@/utils/ubb')
  const { enhanceCodeBlocks } = await import('@/composables/useCodeEnhancer')


  // 解析服务端传递的数据
  window.GLOBAL_DATA = { noteData: null, navigationData: null, isAuthenticated: false };

  (function () {
    const navEl = document.getElementById('navigation-data');
    const noteEl = document.getElementById('note-data');
    if (navEl) {
      try {
        const navData = JSON.parse(navEl.textContent);
        window.GLOBAL_DATA.navigationData = navData;
        window.GLOBAL_DATA.isAuthenticated = navData.is_authenticated || false;
      } catch (e) { console.error('解析导航数据失败:', e); }
    }
    if (noteEl) {
      try {
        window.GLOBAL_DATA.noteData = JSON.parse(noteEl.textContent);
      } catch (e) { console.error('解析笔记数据失败:', e); }
    }
  })();

  if (typeof Vue === 'undefined') { console.error('Vue not loaded'); return; }

  const app = Vue.createApp({
    // ─── 模板 ──────────────────────────────────────────────────────────────
    template: `
      <div v-if="note">
        <!-- 顶部导航栏 -->
        <nav class="pn-navbar">
          <div class="pn-navbar-inner">
            <a href="/knowledge/" class="pn-back-btn">
              <i class="fas fa-arrow-left"></i> 返回首页
            </a>
            <span class="pn-navbar-title">{{ note.title }}</span>
            <div class="pn-navbar-actions">
              <button class="pn-icon-btn" @click="toggleTheme" title="切换主题">
                <i class="fas fa-moon"></i>
              </button>
              <button class="pn-icon-btn" @click="adjustFontSize" title="调整字体">
                <i class="fas fa-font"></i>
              </button>
              <button class="pn-icon-btn" @click="shareArticle" title="分享">
                <i class="fas fa-share-alt"></i>
              </button>
            </div>
          </div>
        </nav>

        <!-- 阅读进度条 -->
        <div class="pn-reading-progress">
          <div class="pn-reading-progress-bar" ref="progressBar"></div>
        </div>

        <!-- 三栏布局 -->
        <div class="pn-layout">

          <!-- ── 左侧边栏 ── -->
          <aside class="pn-sidebar-left">

            <!-- 作者信息卡 -->
            <div class="pn-card pn-author-card">
              <div class="pn-author-avatar">
                <img v-if="note.author.avatar_url" :src="note.author.avatar_url" :alt="note.author.username">
                <span v-else class="pn-author-avatar-text">{{ note.author.username.charAt(0).toUpperCase() }}</span>
              </div>
              <div class="pn-author-name">{{ note.author.username }}</div>
              <div class="pn-author-meta">已发布 {{ note.author.note_count }} 篇公开笔记</div>
              <hr class="pn-author-divider">
              <div class="pn-stats-grid">
                <div class="pn-stat-item">
                  <div class="pn-stat-value viewed">{{ note.views }}</div>
                  <div class="pn-stat-label">阅读</div>
                </div>
                <div class="pn-stat-item">
                  <div class="pn-stat-value liked">{{ note.likes }}</div>
                  <div class="pn-stat-label">点赞</div>
                </div>
                <div class="pn-stat-item">
                  <div class="pn-stat-value">{{ readingTime }}</div>
                  <div class="pn-stat-label">分钟读</div>
                </div>
                <div class="pn-stat-item">
                  <div class="pn-stat-value commented">{{ totalComments }}</div>
                  <div class="pn-stat-label">评论</div>
                </div>
              </div>
              <div class="pn-author-actions">
                <button
                  class="pn-like-btn"
                  :class="{ liked: note.user_has_liked }"
                  @click="toggleLike"
                  :disabled="isLiking"
                >
                  <i :class="note.user_has_liked ? 'fas fa-heart' : 'far fa-heart'"></i>
                  {{ note.user_has_liked ? '已点赞' : '点个赞' }}
                </button>
                <button
                  v-if="!isOwnNote"
                  class="pn-follow-btn"
                  :class="{ following: isFollowing }"
                  @click="toggleFollow"
                  :disabled="followLoading"
                  :title="isFollowing ? '取消关注' : '关注作者'"
                >
                  <i :class="isFollowing ? 'fas fa-user-check' : 'fas fa-user-plus'"></i>
                  {{ isFollowing ? '已关注' : '关注' }}
                  <span v-if="followersCount > 0" class="pn-follow-count">{{ followersCount }}</span>
                </button>
                <button
                  v-if="isAuthenticated && !isOwnNote"
                  class="pn-message-btn"
                  @click="openMessageModal"
                  title="发送私信"
                >
                  <i class="fas fa-envelope"></i>
                  私信
                </button>
              </div>
            </div>

            <!-- 标签卡 -->
            <div v-if="note.tags && note.tags.length" class="pn-card">
              <div class="pn-card-title">文章标签</div>
              <div class="pn-tags-wrap">
                <span v-for="tag in note.tags" :key="tag" class="pn-tag">#{{ tag }}</span>
              </div>
            </div>

          </aside>

          <!-- ── 中间主内容 ── -->
          <main class="pn-main">

            <!-- 文章卡片 -->
            <div class="pn-article-card">

              <!-- 文章头部 -->
              <div class="pn-article-header">
                <h1 class="pn-article-title">{{ note.title }}</h1>
                <div class="pn-meta-row">
                  <div class="pn-meta-author">
                    <img v-if="note.author.avatar_url" :src="note.author.avatar_url" class="pn-meta-avatar" :alt="note.author.username">
                    <div v-else class="pn-meta-avatar-text">{{ note.author.username.charAt(0).toUpperCase() }}</div>
                    <span class="pn-meta-author-name">{{ note.author.username }}</span>
                  </div>
                  <div class="pn-meta-item">
                    <i class="far fa-calendar-alt"></i>
                    {{ note.created_at }}
                  </div>
                  <div class="pn-meta-item">
                    <i class="far fa-clock"></i>
                    {{ readingTime }} 分钟阅读
                  </div>
                  <div class="pn-meta-item">
                    <i class="far fa-eye"></i>
                    {{ note.views }} 次阅读
                  </div>
                </div>
              </div>

              <!-- 正文内容 -->
              <div class="pn-article-body">
                <div class="pn-content" ref="articleContent" v-html="displayContent"></div>
              </div>

              <!-- 标签（内容区下方） -->
              <div v-if="note.tags && note.tags.length" class="pn-article-tags">
                <span v-for="tag in note.tags" :key="tag" class="pn-tag">#{{ tag }}</span>
              </div>

            </div><!-- /pn-article-card -->

            <!-- ── 评论区 ── -->
            <div class="pn-comments-card">

              <div class="pn-comments-header">
                <i class="fas fa-comments" style="color:#6366f1"></i>
                <h3>讨论区</h3>
                <span class="pn-comment-count-badge">{{ totalComments }}</span>
              </div>

              <!-- 已登录：评论输入框 -->
              <div v-if="isAuthenticated" class="pn-comment-form">
                <div class="pn-comment-form-inner">
                  <div class="pn-form-avatar-placeholder">{{ currentUserInitial }}</div>
                  <div class="pn-form-right">
                    <textarea
                      class="pn-comment-textarea"
                      v-model="commentContent"
                      placeholder="分享你的想法..."
                      rows="3"
                    ></textarea>
                    <div class="pn-form-actions">
                      <button class="pn-submit-btn" @click="submitComment" :disabled="isSubmittingComment || !commentContent.trim()">
                        {{ isSubmittingComment ? '发布中...' : '发表评论' }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 未登录：提示登录 -->
              <div v-else class="pn-login-prompt">
                <span>登录后参与讨论</span>
                <a :href="'/login/?next=' + encodeURIComponent(currentPath)">
                  <i class="fas fa-sign-in-alt"></i> 登录
                </a>
              </div>

              <!-- 评论列表 -->
              <div ref="commentList" class="pn-comment-list">
                <div v-if="isLoadingComments" style="padding:2rem;text-align:center;color:#94a3b8">
                  <i class="fas fa-spinner fa-spin"></i> 加载评论中...
                </div>
                <div v-else-if="comments.length === 0" class="pn-comment-empty">
                  <i class="far fa-comment-dots"></i>
                  暂无评论，来发表第一条吧！
                </div>
                <div v-else>
                  <div v-for="comment in comments" :key="comment.id" :id="'comment-' + comment.id" class="pn-comment-item">
                    <div class="pn-comment-row">
                      <img v-if="comment.author_avatar" :src="comment.author_avatar" class="pn-comment-avatar pn-clickable-user" :alt="comment.author" @click="showUserCard($event, comment)">
                      <div v-else class="pn-comment-avatar-text pn-clickable-user" @click="showUserCard($event, comment)">{{ comment.author.charAt(0).toUpperCase() }}</div>
                      <div class="pn-comment-body">
                        <div class="pn-comment-meta">
                          <span class="pn-comment-author pn-clickable-user" @click="showUserCard($event, comment)">{{ comment.author }}</span>
                          <span class="pn-comment-time">{{ comment.created_at }}</span>
                        </div>
                        <div class="pn-comment-content" v-html="comment.rendered_content"></div>
                        <div class="pn-comment-actions">
                          <button v-if="isAuthenticated" class="pn-comment-action-btn" @click="startReply(comment)">
                            <i class="fas fa-reply"></i> 回复
                          </button>
                          <button v-if="isAuthenticated && !comment.is_owner && comment.author_id !== currentUserId" class="pn-comment-action-btn message" @click="openCommentMessage(comment)">
                            <i class="fas fa-envelope"></i> 私信
                          </button>
                          <button v-if="comment.is_owner" class="pn-comment-action-btn delete" @click="openDeleteConfirm(comment)">
                            <i class="fas fa-trash"></i> 删除
                          </button>
                        </div>

                        <!-- 回复列表 -->
                        <div v-if="comment.replies && comment.replies.length" class="pn-replies">
                          <div v-for="reply in comment.replies" :key="reply.id" :id="'comment-' + reply.id" class="pn-reply-item">
                            <img v-if="reply.author_avatar" :src="reply.author_avatar" class="pn-reply-avatar pn-clickable-user" :alt="reply.author" @click="showUserCard($event, reply)">
                            <div v-else class="pn-reply-avatar-text pn-clickable-user" @click="showUserCard($event, reply)">{{ reply.author.charAt(0).toUpperCase() }}</div>
                            <div class="pn-reply-body">
                              <div class="pn-reply-meta">
                                <span class="pn-reply-author pn-clickable-user" @click="showUserCard($event, reply)">{{ reply.author }}</span>
                                <span class="pn-reply-time">{{ reply.created_at }}</span>
                              </div>
                              <div class="pn-reply-content" v-html="reply.rendered_content"></div>
                              <div class="pn-comment-actions">
                                <button v-if="isAuthenticated && !reply.is_owner && reply.author_id !== currentUserId" class="pn-comment-action-btn message" @click="openCommentMessage(reply)">
                                  <i class="fas fa-envelope"></i> 私信
                                </button>
                                <button v-if="reply.is_owner" class="pn-comment-action-btn delete" @click="openDeleteConfirm(reply, comment)">
                                  <i class="fas fa-trash"></i> 删除
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>

                        <!-- 回复输入框 -->
                        <div v-if="replyingToId === comment.id" class="pn-reply-form">
                          <div class="pn-comment-form-inner">
                            <div class="pn-form-avatar-placeholder" style="width:30px;height:30px;font-size:0.75rem">{{ currentUserInitial }}</div>
                            <div class="pn-form-right">
                              <textarea
                                class="pn-comment-textarea"
                                v-model="replyContent"
                                :placeholder="'回复 @' + comment.author + '...'"
                                rows="2"
                              ></textarea>
                              <div class="pn-form-actions">
                                <button class="pn-cancel-btn" @click="cancelReply">取消</button>
                                <button class="pn-submit-btn" @click="submitReply(comment.id)" :disabled="isSubmittingComment || !replyContent.trim()">
                                  {{ isSubmittingComment ? '发布中...' : '回复' }}
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>

                      </div>
                    </div>
                  </div>
                </div>
              </div>

            </div><!-- /pn-comments-card -->

          </main><!-- /pn-main -->

          <!-- ── 右侧边栏 ── -->
          <aside class="pn-sidebar-right">

            <!-- 目录 -->
            <div v-if="note.toc && note.toc.length" class="pn-card">
              <div class="pn-card-title">目录</div>
              <ul class="pn-toc-list">
                <li v-for="item in note.toc" :key="item.id" class="pn-toc-item">
                  <a
                    :href="'#' + item.id"
                    class="pn-toc-link"
                    :class="['level-' + (item.level || 1), activeTocId === item.id ? 'active' : '']"
                    @click.prevent="scrollToHeading(item.id)"
                  >{{ item.text }}</a>
                </li>
              </ul>
            </div>

            <!-- 更多公开文章 -->
            <div v-if="moreNotes.length" class="pn-card">
              <div class="pn-card-title">更多文章</div>
              <div class="pn-more-list">
                <a v-for="n in moreNotes" :key="n.public_id" :href="n.public_url" class="pn-more-item">
                  <div class="pn-more-icon"><i class="fas fa-file-alt"></i></div>
                  <span class="pn-more-title">{{ n.title }}</span>
                </a>
              </div>
            </div>

          </aside>

        </div><!-- /pn-layout -->
      </div>

      <!-- 错误状态 -->
      <div v-else class="pn-error">
        <div class="pn-error-box">
          <i class="fas fa-exclamation-triangle"></i>
          <h2>{{ errorMessage || '无法加载笔记' }}</h2>
          <p>请检查链接是否正确，或稍后重试</p>
          <a href="/knowledge/"><i class="fas fa-home"></i> 返回首页</a>
        </div>
      </div>

      <!-- 快速私信模态框（通用：作者 / 评论者） -->
      <div v-if="showMessageModal" class="pn-message-modal-overlay" @click.self="closeMessageModal">
        <div class="pn-message-modal">
          <div class="pn-modal-header">
            <div class="pn-modal-title">
              <img v-if="messageTarget.avatar" :src="messageTarget.avatar" class="pn-modal-avatar" :alt="messageTarget.username">
              <div v-else class="pn-modal-avatar-text">{{ messageTarget.username ? messageTarget.username.charAt(0).toUpperCase() : 'U' }}</div>
              <span>发送私信给 {{ messageTarget.username }}</span>
            </div>
            <button class="pn-modal-close" @click="closeMessageModal">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="pn-modal-body">
            <div v-if="messageContext" class="pn-message-context">
              <i class="fas fa-quote-left"></i>
              <span>{{ messageContext }}</span>
            </div>
            <textarea
              v-model="messageContent"
              class="pn-message-input"
              placeholder="输入你的私信内容..."
              maxlength="5000"
              @keydown.ctrl.enter="sendMessage"
              @keydown.meta.enter="sendMessage"
            ></textarea>
            <div class="pn-modal-footer">
              <span class="pn-char-count">{{ messageContent.length }}/5000</span>
              <button class="pn-modal-send-btn" @click="sendMessage" :disabled="isSendingMessage || !messageContent.trim()">
                <i v-if="!isSendingMessage" class="fas fa-paper-plane"></i>
                <i v-else class="fas fa-spinner fa-spin"></i>
                {{ isSendingMessage ? '发送中...' : '发送' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="deleteConfirm.visible" class="pn-message-modal-overlay" @click.self="closeDeleteConfirm">
        <div class="pn-message-modal pn-delete-modal">
          <div class="pn-modal-header pn-delete-modal-header">
            <div class="pn-modal-title pn-delete-modal-title">
              <div class="pn-delete-modal-icon">
                <i class="fas fa-trash-alt"></i>
              </div>
              <span>删除{{ deleteConfirm.kind === 'reply' ? '回复' : '评论' }}</span>
            </div>
            <button class="pn-modal-close" @click="closeDeleteConfirm" :disabled="deleteConfirm.deleting">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="pn-modal-body">
            <p class="pn-delete-modal-text">
              {{ deleteConfirm.kind === 'reply' ? '这条回复删除后将无法恢复。' : '这条评论删除后将无法恢复。' }}
            </p>
            <p v-if="deleteConfirm.replyCount > 0" class="pn-delete-modal-warning">
              该评论下还有 {{ deleteConfirm.replyCount }} 条回复，会一并删除。
            </p>
            <div v-if="deleteConfirm.preview" class="pn-delete-modal-preview">
              <div class="pn-delete-modal-preview-label">内容预览</div>
              <div class="pn-delete-modal-preview-text">{{ deleteConfirm.preview }}</div>
            </div>
            <div class="pn-modal-footer pn-delete-modal-footer">
              <button class="pn-modal-secondary-btn" @click="closeDeleteConfirm" :disabled="deleteConfirm.deleting">取消</button>
              <button class="pn-modal-danger-btn" @click="confirmDeleteComment" :disabled="deleteConfirm.deleting">
                <i v-if="deleteConfirm.deleting" class="fas fa-spinner fa-spin"></i>
                <i v-else class="fas fa-trash-alt"></i>
                {{ deleteConfirm.deleting ? '删除中...' : '确认删除' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 用户迷你名片弹窗 -->
      <div v-if="userCard.visible" class="pn-user-card-overlay" @click.self="closeUserCard">
        <div class="pn-user-card" :style="userCardPosition">
          <div class="pn-user-card-header">
            <img v-if="userCard.avatar" :src="userCard.avatar" class="pn-user-card-avatar" :alt="userCard.username">
            <div v-else class="pn-user-card-avatar-text">{{ userCard.username ? userCard.username.charAt(0).toUpperCase() : 'U' }}</div>
            <div class="pn-user-card-info">
              <div class="pn-user-card-name">{{ userCard.username }}</div>
            </div>
          </div>
          <div class="pn-user-card-actions">
            <button v-if="isAuthenticated && userCard.userId !== currentUserId" class="pn-user-card-btn primary" @click="openCardMessage">
              <i class="fas fa-envelope"></i> 发送私信
            </button>
            <button class="pn-user-card-btn" @click="startReplyToUser">
              <i class="fas fa-reply"></i> 回复评论
            </button>
          </div>
        </div>
      </div>
    `,

    // ─── 数据 ──────────────────────────────────────────────────────────────
    data() {
      return {
        note: null,
        errorMessage: null,
        fullContent: '',
        isLiking: false,
        isFollowing: false,
        followLoading: false,
        followersCount: 0,
        isAuthenticated: false,
        readingTime: 0,
        moreNotes: [],
        activeTocId: '',
        currentUserInitial: 'U',
        currentPath: window.location.pathname,
        currentUserId: null,
        // 评论
        comments: [],
        commentContent: '',
        replyContent: '',
        replyingToId: null,
        isSubmittingComment: false,
        isLoadingComments: false,
        totalComments: 0,
        // 私信
        showMessageModal: false,
        messageContent: '',
        isSendingMessage: false,
        messageTarget: { userId: null, username: '', avatar: '' },
        messageContext: '',
        messageContextLink: '',
        deleteConfirm: {
          visible: false,
          deleting: false,
          commentId: null,
          kind: 'comment',
          replyCount: 0,
          preview: ''
        },
        // 用户迷你名片
        userCard: { visible: false, userId: null, username: '', avatar: '', commentId: null },
        userCardClickPos: { x: 0, y: 0 },
      };
    },

    // ─── 计算属性 ─────────────────────────────────────────────────────────
    computed: {
      displayContent() {
        if (!this.fullContent) return '';
        return this.fixImageUrls(convertUbbMarkupInHtml(this.fullContent));
      },
      isOwnNote() {
        if (!this.note || !this.currentUserId) return false;
        return this.note.author.id === this.currentUserId;
      },
      userCardPosition() {
        return {};
      }
    },

    // ─── 生命周期 ─────────────────────────────────────────────────────────
    mounted() {
      this.initializeData();
      this.setupScrollListener();
    },

    updated() {
      this.hydrateRuntimeWidgets();
    },

    // ─── 方法 ─────────────────────────────────────────────────────────────
    methods: {

      initializeData() {
        const g = window.GLOBAL_DATA;
        if (!g || !g.noteData) {
          this.errorMessage = '无法获取页面数据';
          return;
        }
        this.note = g.noteData;
        this.isAuthenticated = g.isAuthenticated;
        this.totalComments = this.note.comment_count || 0;

        // 从 meta 标签获取当前用户ID
        const userIdMeta = document.querySelector('meta[name="user-id"]');
        if (userIdMeta && userIdMeta.content) {
          this.currentUserId = parseInt(userIdMeta.content);
        }

        // 从 currentUser cookie 获取用户首字母（简易方案）
        const usernameMeta = document.querySelector('meta[name="username"]');
        if (usernameMeta) {
          this.currentUserInitial = usernameMeta.content.charAt(0).toUpperCase();
        }

        if (g.navigationData) {
          this.moreNotes = (g.navigationData.navigation_list || [])
            .filter(n => n.public_id !== this.note.public_id)
            .slice(0, 5);
        }

        // 解析正文内容
        const contentEl = document.getElementById('full-content-data');
        if (contentEl) {
          try {
            this.fullContent = JSON.parse(contentEl.textContent);
          } catch (e) {
            this.fullContent = this.note.content || '';
          }
        } else {
          this.fullContent = this.note.content || '';
        }

        if (!this.fullContent) {
          this.errorMessage = '无法加载文章内容';
          return;
        }

        this.readingTime = Math.max(1, Math.ceil(this.fullContent.replace(/<[^>]+>/g, '').length / 400));

        this.fetchFollowStatus();

        // DOM 更新后增强代码块 + 初始化 TOC 高亮 + 加载评论
        this.$nextTick(() => {
          this.hydrateRuntimeWidgets();
          this.fetchComments();
        });
      },

      // ── 评论相关 ────────────────────────────────────────────────────────

      async fetchComments() {
        if (!this.note) return;
        this.isLoadingComments = true;
        try {
          const res = await fetch(`/api/notes/${this.note.id}/comments/`);
          const data = await res.json();
          this.comments = (data.comments || []).map(comment => this.decorateComment(comment));
          this.totalComments = data.total || 0;
        } catch (e) {
          console.error('加载评论失败:', e);
        } finally {
          this.isLoadingComments = false;
          this.$nextTick(() => {
            this.hydrateRuntimeWidgets();
            this.scrollToLinkedComment();
          });
        }
      },

      async submitComment() {
        if (!this.commentContent.trim() || this.isSubmittingComment) return;
        this.isSubmittingComment = true;
        try {
          const res = await fetch(`/api/notes/${this.note.id}/comments/create/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCookie('csrftoken') },
            body: JSON.stringify({ content: this.commentContent.trim() })
          });
          if (res.status === 201) {
            const newComment = this.decorateComment(await res.json());
            newComment.replies = [];
            this.comments.push(newComment);
            this.totalComments++;
            this.commentContent = '';
            this.$nextTick(() => this.hydrateRuntimeWidgets());
            this.showToast('评论发表成功！', 'success');
          } else {
            const err = await res.json();
            this.showToast(err.error || '发表失败', 'error');
          }
        } catch (e) {
          this.showToast('网络错误，请稍后重试', 'error');
        } finally {
          this.isSubmittingComment = false;
        }
      },

      async submitReply(parentId) {
        if (!this.replyContent.trim() || this.isSubmittingComment) return;
        this.isSubmittingComment = true;
        try {
          const res = await fetch(`/api/notes/${this.note.id}/comments/create/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCookie('csrftoken') },
            body: JSON.stringify({ content: this.replyContent.trim(), parent_id: parentId })
          });
          if (res.status === 201) {
            const reply = this.decorateComment(await res.json());
            const parent = this.comments.find(c => c.id === parentId);
            if (parent) { parent.replies.push(reply); }
            this.totalComments++;
            this.replyContent = '';
            this.replyingToId = null;
            this.$nextTick(() => this.hydrateRuntimeWidgets());
            this.showToast('回复成功！', 'success');
          } else {
            const err = await res.json();
            this.showToast(err.error || '回复失败', 'error');
          }
        } catch (e) {
          this.showToast('网络错误，请稍后重试', 'error');
        } finally {
          this.isSubmittingComment = false;
        }
      },

      openDeleteConfirm(target, parentComment = null) {
        this.deleteConfirm = {
          visible: true,
          deleting: false,
          commentId: target.id,
          kind: parentComment ? 'reply' : 'comment',
          replyCount: parentComment ? 0 : ((target.replies || []).length),
          preview: this.getCommentPreview(target.content || '')
        };
      },

      closeDeleteConfirm() {
        if (this.deleteConfirm.deleting) return;
        this.deleteConfirm.visible = false;
      },

      async confirmDeleteComment() {
        const commentId = this.deleteConfirm.commentId;
        if (!commentId) return;
        this.deleteConfirm.deleting = true;
        try {
          const res = await fetch(`/api/comments/${commentId}/delete/`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': this.getCookie('csrftoken') }
          });
          if (res.ok) {
            // 从顶级或回复中删除
            const idx = this.comments.findIndex(c => c.id === commentId);
            if (idx !== -1) {
              const removed = this.comments.splice(idx, 1)[0];
              this.totalComments -= 1 + (removed.replies ? removed.replies.length : 0);
            } else {
              this.comments.forEach(c => {
                const ri = (c.replies || []).findIndex(r => r.id === commentId);
                if (ri !== -1) { c.replies.splice(ri, 1); this.totalComments--; }
              });
            }
            this.showToast('评论已删除', 'success');
          }
        } catch (e) {
          this.showToast('删除失败', 'error');
        } finally {
          this.deleteConfirm = {
            visible: false,
            deleting: false,
            commentId: null,
            kind: 'comment',
            replyCount: 0,
            preview: ''
          };
        }
      },

      startReply(comment) { this.replyingToId = comment.id; this.replyContent = ''; },
      cancelReply() { this.replyingToId = null; this.replyContent = ''; },

      decorateComment(comment) {
        return {
          ...comment,
          rendered_content: renderCommentUbb(comment.content || ''),
          replies: (comment.replies || []).map(reply => ({
            ...reply,
            rendered_content: renderCommentUbb(reply.content || '')
          }))
        };
      },

      hydrateRuntimeWidgets() {
        const run = () => {
          hydrateUbbDom(this.$refs.articleContent);
          hydrateUbbDom(this.$refs.commentList);
          if (this.$refs.articleContent) enhanceCodeBlocks(this.$refs.articleContent);
          if (this.$refs.commentList) enhanceCodeBlocks(this.$refs.commentList);
        };

        run();
        requestAnimationFrame(run);
        setTimeout(run, 0);
      },

      getCommentPreview(content) {
        const raw = String(content || '')
          .replace(/\[(?:\/)?(?:b|i|u|img|audio|movie|qqmusic|wymusic|url|forecolor|code|text|codo)(?:=[^\]]+)?\]/gi, ' ')
          .replace(/\[now\]/gi, ' ')
          .replace(/https?:\/\/\S+/gi, ' ')
          .replace(/\s+/g, ' ')
          .trim();

        if (raw) {
          return raw.length > 90 ? raw.slice(0, 90) + '...' : raw;
        }

        if (/\[(?:img)\]/i.test(content || '')) return '这条评论包含图片内容';
        if (/\[(?:audio)\]/i.test(content || '')) return '这条评论包含音频内容';
        if (/\[(?:movie)\]/i.test(content || '')) return '这条评论包含视频内容';
        if (/\[(?:qqmusic|wymusic)\]/i.test(content || '')) return '这条评论包含音乐内容';
        if (/\[(?:code)\]/i.test(content || '')) return '这条评论包含代码内容';
        return '';
      },

      // ── TOC 滚动 ────────────────────────────────────────────────────────

      scrollToHeading(id) {
        const el = document.getElementById(id);
        if (!el) return;
        const mainEl = document.querySelector('.pn-main');
        if (mainEl && window.innerWidth >= 960) {
          // 在中间列容器内滚动
          const mainRect = mainEl.getBoundingClientRect();
          const elRect = el.getBoundingClientRect();
          const targetTop = elRect.top - mainRect.top + mainEl.scrollTop - 20;
          mainEl.scrollTo({ top: targetTop, behavior: 'smooth' });
        } else {
          window.scrollTo({ top: el.getBoundingClientRect().top + window.pageYOffset - 80, behavior: 'smooth' });
        }
      },

      // ── 点赞 ────────────────────────────────────────────────────────────

      async toggleLike() {
        if (!this.isAuthenticated) {
          window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname);
          return;
        }
        if (this.isLiking) return;
        this.isLiking = true;
        try {
          const res = await fetch('/api/toggle-note-like/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCookie('csrftoken') },
            body: JSON.stringify({ note_id: this.note.id })
          });
          const data = await res.json();
          if (data.status === 'success') {
            this.note.user_has_liked = data.user_has_liked;
            this.note.likes = data.total_likes;
            this.showToast(data.action === 'liked' ? '点赞成功！' : '已取消点赞', 'success');
          }
        } catch (e) {
          this.showToast('操作失败，请稍后重试', 'error');
        } finally {
          this.isLiking = false;
        }
      },

      // ── 私信 ────────────────────────────────────────────────────────────

      async fetchFollowStatus() {
        if (!this.note || !this.note.author || !this.note.author.id || this.isOwnNote) return;
        try {
          const res = await fetch(`/api/users/${this.note.author.id}/follow-status/`);
          if (!res.ok) return;
          const data = await res.json();
          this.isFollowing = !!data.is_following;
          this.followersCount = Number(data.followers_count || 0);
        } catch (e) {
          console.error('加载关注状态失败:', e);
        }
      },

      async toggleFollow() {
        if (this.followLoading || this.isOwnNote || !this.note || !this.note.author || !this.note.author.id) return;
        if (!this.isAuthenticated) {
          window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname);
          return;
        }
        this.followLoading = true;
        try {
          const endpoint = this.isFollowing ? '/api/users/unfollow/' : '/api/users/follow/';
          const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCookie('csrftoken') },
            body: JSON.stringify({ user_id: this.note.author.id })
          });
          const data = await res.json();
          if (res.ok && data.status === 'success') {
            this.isFollowing = !!data.is_following;
            this.followersCount = Number(data.followers_count || 0);
            this.showToast(this.isFollowing ? '关注成功' : '已取消关注', 'success');
          } else {
            this.showToast(data.error || '关注操作失败', 'error');
          }
        } catch (e) {
          this.showToast('网络错误，请稍后重试', 'error');
        } finally {
          this.followLoading = false;
        }
      },
      openMessageModal() {
        this.messageTarget = {
          userId: this.note.author.id,
          username: this.note.author.username,
          avatar: this.note.author.avatar_url
        };
        this.messageContext = '';
        this.messageContextLink = '';
        this.showMessageModal = true;
        this.messageContent = '';
      },

      openCommentMessage(commentOrReply) {
        this.closeUserCard();
        this.messageTarget = {
          userId: commentOrReply.author_id,
          username: commentOrReply.author,
          avatar: commentOrReply.author_avatar
        };
        this.messageContext = '来自笔记《' + this.note.title + '》下的评论';
        this.messageContextLink = this.buildCommentLink(commentOrReply.id);
        this.showMessageModal = true;
        this.messageContent = '';
      },

      closeMessageModal() {
        this.showMessageModal = false;
        this.messageContent = '';
        this.messageContext = '';
        this.messageContextLink = '';
      },

      async sendMessage() {
        if (!this.messageContent.trim() || this.isSendingMessage) return;

        this.isSendingMessage = true;
        try {
          let content = this.messageContent.trim();
          if (this.messageContext) {
            const context = this.messageContextLink
              ? '[' + this.sanitizeMarkdownLinkText(this.messageContext) + '](' + this.messageContextLink + ')'
              : '【' + this.messageContext + '】';
            content = context + '\n\n' + content;
          }
          const res = await fetch('/api/messages/send/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCookie('csrftoken') },
            body: JSON.stringify({
              recipient_id: this.messageTarget.userId,
              content: content
            })
          });
          const data = await res.json();
          if (res.ok) {
            this.showToast('私信已发送！', 'success');
            this.closeMessageModal();
          } else if (res.status === 403) {
            this.showToast(data.error || '此用户未开启私信功能', 'warning');
          } else if (res.status === 401) {
            this.showToast('请先登录后再发送私信', 'warning');
          } else {
            this.showToast(data.error || '发送失败', 'error');
          }
        } catch (e) {
          this.showToast('网络错误，请稍后重试', 'error');
        } finally {
          this.isSendingMessage = false;
        }
      },

      // ── 用户迷你名片 ──────────────────────────────────────────────────

      showUserCard(event, commentOrReply) {
        if (!commentOrReply.author_id) return;
        this.userCard = {
          visible: true,
          userId: commentOrReply.author_id,
          username: commentOrReply.author,
          avatar: commentOrReply.author_avatar,
          commentId: commentOrReply.id
        };
        this.userCardClickPos = { x: event.clientX, y: event.clientY };
      },

      closeUserCard() {
        this.userCard.visible = false;
      },

      openCardMessage() {
        this.openCommentMessage({
          author_id: this.userCard.userId,
          author: this.userCard.username,
          author_avatar: this.userCard.avatar,
          id: this.userCard.commentId
        });
      },

      startReplyToUser() {
        const comment = this.comments.find(c => c.id === this.userCard.commentId);
        if (comment) {
          this.startReply(comment);
        }
        this.closeUserCard();
      },

      // ── 工具函数 ─────────────────────────────────────────────────────────

      getCookie(name) {
        const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : '';
      },

      sanitizeMarkdownLinkText(text) {
        return String(text || '').replace(/[\r\n[\]]/g, ' ');
      },

      buildCommentLink(commentId) {
        if (!commentId) return '';
        const publicId = this.note && this.note.public_id;
        const path = publicId ? `/notes/public/${publicId}/` : window.location.pathname;
        return `${window.location.origin}${path}?comment=${encodeURIComponent(commentId)}#comment-${encodeURIComponent(commentId)}`;
      },

      getLinkedCommentId() {
        const params = new URLSearchParams(window.location.search);
        const queryId = params.get('comment');
        if (queryId) return queryId;
        const match = window.location.hash.match(/^#comment-(.+)$/);
        return match ? decodeURIComponent(match[1]) : '';
      },

      scrollToLinkedComment() {
        const commentId = this.getLinkedCommentId();
        if (!commentId) return;
        const el = document.getElementById(`comment-${commentId}`);
        if (!el) return;

        const mainEl = document.querySelector('.pn-main');
        if (mainEl && window.innerWidth >= 960) {
          const mainRect = mainEl.getBoundingClientRect();
          const elRect = el.getBoundingClientRect();
          const targetTop = elRect.top - mainRect.top + mainEl.scrollTop - 80;
          mainEl.scrollTo({ top: Math.max(0, targetTop), behavior: 'smooth' });
        } else {
          window.scrollTo({ top: el.getBoundingClientRect().top + window.pageYOffset - 80, behavior: 'smooth' });
        }

        el.classList.remove('pn-comment-jump-highlight');
        void el.offsetWidth;
        el.classList.add('pn-comment-jump-highlight');
        setTimeout(() => el.classList.remove('pn-comment-jump-highlight'), 2600);
      },

      fixImageUrls(html) {
        if (!html) return '';
        const base = window.location.origin + '/';
        const div = document.createElement('div');
        div.innerHTML = html;
        div.querySelectorAll('img').forEach(img => {
          const src = img.getAttribute('src');
          if (src && !src.match(/^https?:\/\//) && !src.match(/^\/\//)) {
            img.setAttribute('src', base + src.replace(/^\//, ''));
          }
        });
        return div.innerHTML;
      },

      showToast(message, type = 'success') {
        const t = document.createElement('div');
        t.className = `pn-toast ${type}`;
        t.textContent = message;
        document.body.appendChild(t);
        setTimeout(() => {
          t.classList.add('fade-out');
          setTimeout(() => t.remove(), 300);
        }, 2700);
      },

      toggleTheme() {
        const cur = document.documentElement.getAttribute('data-theme') || 'light';
        document.documentElement.setAttribute('data-theme', cur === 'light' ? 'dark' : 'light');
        localStorage.setItem('theme', cur === 'light' ? 'dark' : 'light');
      },

      adjustFontSize() {
        const el = this.$refs.articleContent;
        if (!el) return;
        const sizes = ['font-size-small', 'font-size-medium', 'font-size-large'];
        let idx = sizes.findIndex(s => el.classList.contains(s));
        if (idx === -1) idx = 1;
        el.classList.remove(...sizes);
        el.classList.add(sizes[(idx + 1) % sizes.length]);
      },

      shareArticle() {
        const url = window.location.href;
        if (navigator.share) {
          navigator.share({ title: this.note.title, url }).catch(() => this.copyLink(url));
        } else {
          this.copyLink(url);
        }
      },

      copyLink(url) {
        if (navigator.clipboard) {
          navigator.clipboard.writeText(url).then(() => this.showToast('链接已复制', 'success'));
        } else {
          const ta = document.createElement('textarea');
          ta.value = url;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          ta.remove();
          this.showToast('链接已复制', 'success');
        }
      },

      setupScrollListener() {
        const bar = this.$refs.progressBar;
        const self = this;
        let currentScrollTarget = null;
        let boundHandler = null;

        const updateTOC = (containerTop) => {
          if (!self.note || !self.note.toc || !self.note.toc.length) return;
          const headings = self.note.toc.map(t => document.getElementById(t.id)).filter(Boolean);
          let current = '';
          for (const h of headings) {
            const rect = h.getBoundingClientRect();
            if (rect.top - containerTop <= 90) current = h.id;
          }
          self.activeTocId = current;
        };

        const createHandler = (target) => {
          if (target === window) {
            return () => {
              if (bar) {
                const st = window.pageYOffset;
                const sh = document.documentElement.scrollHeight - window.innerHeight;
                bar.style.width = (sh > 0 ? (st / sh) * 100 : 0) + '%';
              }
              updateTOC(0);
            };
          }
          return () => {
            if (bar) {
              const sh = target.scrollHeight - target.clientHeight;
              bar.style.width = (sh > 0 ? (target.scrollTop / sh) * 100 : 0) + '%';
            }
            updateTOC(target.getBoundingClientRect().top);
          };
        };

        const bind = () => {
          // 先解绑旧的
          if (currentScrollTarget && boundHandler) {
            currentScrollTarget.removeEventListener('scroll', boundHandler);
          }

          const mainEl = document.querySelector('.pn-main');
          if (mainEl && window.innerWidth >= 960 && mainEl.scrollHeight > mainEl.clientHeight) {
            currentScrollTarget = mainEl;
          } else {
            currentScrollTarget = window;
          }

          boundHandler = createHandler(currentScrollTarget);
          currentScrollTarget.addEventListener('scroll', boundHandler, { passive: true });
        };

        this.$nextTick(bind);

        // 窗口尺寸变化时重新绑定
        let resizeTimer = null;
        window.addEventListener('resize', () => {
          clearTimeout(resizeTimer);
          resizeTimer = setTimeout(bind, 200);
        }, { passive: true });
      },

    }
  });

  app.config.errorHandler = (err, vm, info) => console.error('Vue error:', err, info);
  app.mount('#public-note-app');
});







