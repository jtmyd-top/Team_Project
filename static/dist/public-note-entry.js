const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["chunks/ubb-DLUgd71s.js","chunks/vendor-wzGsUuS6.js"])))=>i.map(i=>d[i]);
import{_ as v}from"./chunks/preload-helper-CYKyUB34.js";document.addEventListener("DOMContentLoaded",async function(){const{convertUbbMarkupInHtml:g,renderCommentUbb:d,hydrateUbbDom:m}=await v(async()=>{const{convertUbbMarkupInHtml:t,renderCommentUbb:e,hydrateUbbDom:s}=await import("./chunks/ubb-DLUgd71s.js");return{convertUbbMarkupInHtml:t,renderCommentUbb:e,hydrateUbbDom:s}},__vite__mapDeps([0,1])),{enhanceCodeBlocks:h}=await v(async()=>{const{enhanceCodeBlocks:t}=await import("./chunks/useCodeEnhancer-D0rmz2rR.js");return{enhanceCodeBlocks:t}},[]);if(!document.getElementById("pn-author-card-inline-styles")){const t=document.createElement("style");t.id="pn-author-card-inline-styles",t.textContent=`
      .pn-author-clickable { cursor: pointer; transition: transform 0.18s ease, box-shadow 0.18s ease, color 0.18s ease; }
      .pn-author-avatar.pn-author-clickable:hover { transform: translateY(-2px) scale(1.04); box-shadow: 0 6px 18px rgba(99, 102, 241, 0.18); }
      .pn-author-name.pn-author-clickable:hover { color: #6366f1; }

      .pn-author-modal-overlay { position: fixed; inset: 0; z-index: 10001; background: rgba(15, 23, 42, 0.55); display: flex; align-items: center; justify-content: center; animation: pn-fade-in 0.2s ease; backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px); }
      .pn-author-modal { position: relative; background: #fff; border-radius: 18px; width: min(90vw, 380px); max-height: 90vh; overflow: hidden; box-shadow: 0 24px 48px rgba(15, 23, 42, 0.25), 0 4px 12px rgba(15, 23, 42, 0.08); animation: pn-author-modal-in 0.28s cubic-bezier(0.34, 1.56, 0.64, 1); }
      @keyframes pn-author-modal-in { from { transform: translateY(16px) scale(0.96); opacity: 0; } to { transform: translateY(0) scale(1); opacity: 1; } }
      .pn-author-modal-banner { height: 80px; background: linear-gradient(135deg, #6366f1, #ec4899); }
      .pn-author-modal-close { position: absolute; top: 12px; right: 12px; width: 32px; height: 32px; border-radius: 50%; border: none; background: rgba(255, 255, 255, 0.85); color: #475569; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.18s ease; z-index: 2; font-size: 14px; }
      .pn-author-modal-close:hover { background: #fff; color: #ec4899; transform: rotate(90deg); }
      .pn-author-modal-body { padding: 0 24px 24px; text-align: center; }
      .pn-author-modal-avatar-wrap { margin-top: -42px; margin-bottom: 12px; display: flex; justify-content: center; }
      .pn-author-modal-avatar { width: 84px; height: 84px; border-radius: 50%; border: 4px solid #fff; object-fit: cover; background: #f1f5f9; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12); }
      .pn-author-modal-avatar-text { display: flex; align-items: center; justify-content: center; font-size: 1.85rem; font-weight: 700; color: #fff; background: linear-gradient(135deg, #6366f1, #ec4899); }
      .pn-author-modal-name { font-size: 1.15rem; font-weight: 700; color: #1e293b; margin: 0 0 6px; }
      .pn-author-modal-bio { font-size: 0.85rem; color: #475569; line-height: 1.55; margin: 0 0 18px; padding: 0 6px; word-break: break-word; }
      .pn-author-modal-bio.placeholder { color: #94a3b8; font-style: italic; }
      .pn-author-modal-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding: 12px; background: #f8fafc; border-radius: 12px; margin-bottom: 18px; }
      .pn-author-modal-stat { text-align: center; }
      .pn-author-modal-stat-value { font-size: 1.05rem; font-weight: 700; color: #1e293b; line-height: 1.2; }
      .pn-author-modal-stat-label { font-size: 0.7rem; color: #94a3b8; margin-top: 2px; }
      .pn-author-modal-actions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
      .pn-author-modal-btn { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 10px 8px; font-size: 0.82rem; font-weight: 600; border: 1px solid #e2e8f0; border-radius: 9px; background: #fff; color: #475569; cursor: pointer; transition: all 0.18s ease; }
      .pn-author-modal-btn:hover:not(:disabled) { border-color: #6366f1; color: #6366f1; background: rgba(99, 102, 241, 0.06); transform: translateY(-1px); }
      .pn-author-modal-btn:disabled { opacity: 0.6; cursor: not-allowed; }
      .pn-author-modal-btn.primary { background: #6366f1; color: #fff; border-color: #6366f1; }
      .pn-author-modal-btn.primary:hover:not(:disabled) { background: #8b5cf6; border-color: #8b5cf6; color: #fff; }
      .pn-author-modal-btn.is-following { background: #67c23a; color: #fff; border-color: #67c23a; }
      .pn-author-modal-btn.is-following:hover:not(:disabled) { background: #f56c6c; border-color: #f56c6c; color: #fff; }
      .pn-author-modal-hint { margin-top: 12px; padding: 8px 12px; background: #f0f9ff; border-left: 3px solid #6366f1; border-radius: 0 6px 6px 0; font-size: 0.78rem; color: #475569; display: flex; align-items: center; gap: 6px; }
      @keyframes pn-fade-in { from { opacity: 0; } to { opacity: 1; } }
    `,document.head.appendChild(t)}if(window.GLOBAL_DATA={noteData:null,navigationData:null,isAuthenticated:!1},function(){const t=document.getElementById("navigation-data"),e=document.getElementById("note-data");if(t)try{const s=JSON.parse(t.textContent);window.GLOBAL_DATA.navigationData=s,window.GLOBAL_DATA.isAuthenticated=s.is_authenticated||!1}catch(s){console.error("解析导航数据失败:",s)}if(e)try{window.GLOBAL_DATA.noteData=JSON.parse(e.textContent)}catch(s){console.error("解析笔记数据失败:",s)}}(),typeof Vue>"u"){console.error("Vue not loaded");return}const u=Vue.createApp({template:`
      <div v-if="note">
        <!-- 顶部导航栏 -->
        <nav class="pn-navbar">
          <div class="pn-navbar-inner">
            <a href="/" class="pn-back-btn">
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
              <div class="pn-author-avatar pn-author-clickable" @click="openAuthorCard" title="查看作者资料">
                <img v-if="note.author.avatar_url" :src="note.author.avatar_url" :alt="note.author.username">
                <span v-else class="pn-author-avatar-text">{{ note.author.username.charAt(0).toUpperCase() }}</span>
              </div>
              <div class="pn-author-name pn-author-clickable" @click="openAuthorCard">{{ note.author.username }}</div>
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
                  <div v-if="hasMoreComments" style="text-align:center;padding:12px 0 4px;">
                    <button class="pn-submit-btn" @click="loadMoreComments" :disabled="isLoadingComments">
                      {{ isLoadingComments ? '加载中...' : '加载更多评论' }}
                    </button>
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
          <a href="/"><i class="fas fa-home"></i> 返回首页</a>
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

      <!-- 作者资料卡弹窗 -->
      <div v-if="authorCard.visible" class="pn-author-modal-overlay" @click.self="closeAuthorCard">
        <div class="pn-author-modal">
          <button class="pn-author-modal-close" @click="closeAuthorCard" title="关闭">
            <i class="fas fa-times"></i>
          </button>

          <div class="pn-author-modal-banner"></div>

          <div class="pn-author-modal-body">
            <div class="pn-author-modal-avatar-wrap">
              <img v-if="authorCard.avatar" :src="authorCard.avatar" class="pn-author-modal-avatar" :alt="authorCard.username">
              <div v-else class="pn-author-modal-avatar pn-author-modal-avatar-text">{{ authorCard.username ? authorCard.username.charAt(0).toUpperCase() : 'U' }}</div>
            </div>

            <h3 class="pn-author-modal-name">{{ authorCard.username }}</h3>

            <p v-if="authorCard.bio" class="pn-author-modal-bio">{{ authorCard.bio }}</p>
            <p v-else class="pn-author-modal-bio placeholder">这个人很懒，什么都没写...</p>

            <div class="pn-author-modal-stats">
              <div class="pn-author-modal-stat">
                <div class="pn-author-modal-stat-value">{{ authorCard.notes_count }}</div>
                <div class="pn-author-modal-stat-label">笔记</div>
              </div>
              <div class="pn-author-modal-stat">
                <div class="pn-author-modal-stat-value">{{ authorCard.views_count }}</div>
                <div class="pn-author-modal-stat-label">阅读</div>
              </div>
              <div class="pn-author-modal-stat">
                <div class="pn-author-modal-stat-value">{{ authorCard.likes_count }}</div>
                <div class="pn-author-modal-stat-label">获赞</div>
              </div>
            </div>

            <div class="pn-author-modal-actions">
              <button v-if="isAuthenticated && !isOwnNote" class="pn-author-modal-btn primary" @click="messageFromAuthorCard">
                <i class="fas fa-envelope"></i> 私信
              </button>
              <button v-if="isAuthenticated && !isOwnNote" class="pn-author-modal-btn" :class="{ 'is-following': isFollowing }" :disabled="followLoading" @click="toggleFollow">
                <i :class="isFollowing ? 'fas fa-user-check' : 'fas fa-user-plus'"></i>
                {{ isFollowing ? '已关注' : '关注' }}
              </button>
              <button class="pn-author-modal-btn" @click="goToAuthorProfile">
                <i class="fas fa-user-circle"></i> 主页
              </button>
            </div>

            <div v-if="isOwnNote" class="pn-author-modal-hint">
              <i class="fas fa-info-circle"></i> 这是你自己的笔记
            </div>
          </div>
        </div>
      </div>
    `,data(){return{note:null,errorMessage:null,fullContent:"",isLiking:!1,isFollowing:!1,followLoading:!1,followersCount:0,isAuthenticated:!1,readingTime:0,moreNotes:[],activeTocId:"",currentUserInitial:"U",currentPath:window.location.pathname,currentUserId:null,comments:[],commentContent:"",replyContent:"",replyingToId:null,isSubmittingComment:!1,isLoadingComments:!1,totalComments:0,commentsPage:1,commentsPageSize:20,commentsTotalPages:1,hasMoreComments:!1,showMessageModal:!1,messageContent:"",isSendingMessage:!1,messageTarget:{userId:null,username:"",avatar:""},messageContext:"",messageContextLink:"",deleteConfirm:{visible:!1,deleting:!1,commentId:null,kind:"comment",replyCount:0,preview:""},userCard:{visible:!1,userId:null,username:"",avatar:"",commentId:null},userCardClickPos:{x:0,y:0},authorCard:{visible:!1,username:"",avatar:"",bio:"",notes_count:0,views_count:0,likes_count:0,loading:!1}}},computed:{displayContent(){return this.fullContent?this.fixImageUrls(g(this.fullContent)):""},isOwnNote(){return!this.note||!this.currentUserId?!1:this.note.author.id===this.currentUserId},userCardPosition(){return{}}},mounted(){this.initializeData(),this.setupScrollListener()},updated(){this.hydrateRuntimeWidgets()},methods:{initializeData(){const t=window.GLOBAL_DATA;if(!t||!t.noteData){this.errorMessage="无法获取页面数据";return}this.note=t.noteData,this.isAuthenticated=t.isAuthenticated,this.totalComments=this.note.comment_count||0;const e=document.querySelector('meta[name="user-id"]');e&&e.content&&(this.currentUserId=parseInt(e.content));const s=document.querySelector('meta[name="username"]');s&&(this.currentUserInitial=s.content.charAt(0).toUpperCase()),t.navigationData&&(this.moreNotes=(t.navigationData.navigation_list||[]).filter(n=>n.public_id!==this.note.public_id).slice(0,5));const a=document.getElementById("full-content-data");if(a)try{this.fullContent=JSON.parse(a.textContent)}catch{this.fullContent=this.note.content||""}else this.fullContent=this.note.content||"";if(!this.fullContent){this.errorMessage="无法加载文章内容";return}this.readingTime=Math.max(1,Math.ceil(this.fullContent.replace(/<[^>]+>/g,"").length/400)),this.fetchFollowStatus(),this.$nextTick(()=>{this.hydrateRuntimeWidgets(),this.fetchComments()})},async fetchComments(t=!0){if(this.note){t&&(this.commentsPage=1),this.isLoadingComments=!0;try{const s=await(await fetch(`/api/notes/${this.note.id}/comments/?page=${this.commentsPage}&page_size=${this.commentsPageSize}`)).json(),a=(s.comments||[]).map(o=>this.decorateComment(o));this.comments=t?a:[...this.comments,...a],this.totalComments=s.total||0;const n=s.pagination||{};this.commentsTotalPages=n.top_level_total_pages||1,this.hasMoreComments=this.commentsPage<this.commentsTotalPages}catch(e){console.error("加载评论失败:",e)}finally{this.isLoadingComments=!1,this.$nextTick(()=>{this.hydrateRuntimeWidgets(),this.scrollToLinkedComment()})}}},async loadMoreComments(){this.isLoadingComments||!this.hasMoreComments||(this.commentsPage+=1,await this.fetchComments(!1))},async submitComment(){if(!(!this.commentContent.trim()||this.isSubmittingComment)){this.isSubmittingComment=!0;try{const t=await fetch(`/api/notes/${this.note.id}/comments/create/`,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({content:this.commentContent.trim()})});if(t.status===201){const e=this.decorateComment(await t.json());e.replies=[],this.comments.push(e),this.totalComments++,this.hasMoreComments=this.commentsPage<this.commentsTotalPages,this.commentContent="",this.$nextTick(()=>this.hydrateRuntimeWidgets()),this.showToast("评论发表成功！","success")}else{const e=await t.json();this.showToast(e.error||"发表失败","error")}}catch{this.showToast("网络错误，请稍后重试","error")}finally{this.isSubmittingComment=!1}}},async submitReply(t){if(!(!this.replyContent.trim()||this.isSubmittingComment)){this.isSubmittingComment=!0;try{const e=await fetch(`/api/notes/${this.note.id}/comments/create/`,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({content:this.replyContent.trim(),parent_id:t})});if(e.status===201){const s=this.decorateComment(await e.json()),a=this.comments.find(n=>n.id===t);a&&a.replies.push(s),this.totalComments++,this.replyContent="",this.replyingToId=null,this.$nextTick(()=>this.hydrateRuntimeWidgets()),this.showToast("回复成功！","success")}else{const s=await e.json();this.showToast(s.error||"回复失败","error")}}catch{this.showToast("网络错误，请稍后重试","error")}finally{this.isSubmittingComment=!1}}},openDeleteConfirm(t,e=null){this.deleteConfirm={visible:!0,deleting:!1,commentId:t.id,kind:e?"reply":"comment",replyCount:e?0:(t.replies||[]).length,preview:this.getCommentPreview(t.content||"")}},closeDeleteConfirm(){this.deleteConfirm.deleting||(this.deleteConfirm.visible=!1)},async confirmDeleteComment(){const t=this.deleteConfirm.commentId;if(t){this.deleteConfirm.deleting=!0;try{if((await fetch(`/api/comments/${t}/delete/`,{method:"DELETE",headers:{"X-CSRFToken":this.getCookie("csrftoken")}})).ok){const s=this.comments.findIndex(a=>a.id===t);if(s!==-1){const a=this.comments.splice(s,1)[0];this.totalComments-=1+(a.replies?a.replies.length:0)}else this.comments.forEach(a=>{const n=(a.replies||[]).findIndex(o=>o.id===t);n!==-1&&(a.replies.splice(n,1),this.totalComments--)});this.showToast("评论已删除","success")}}catch{this.showToast("删除失败","error")}finally{this.deleteConfirm={visible:!1,deleting:!1,commentId:null,kind:"comment",replyCount:0,preview:""}}}},startReply(t){this.replyingToId=t.id,this.replyContent=""},cancelReply(){this.replyingToId=null,this.replyContent=""},decorateComment(t){return{...t,rendered_content:d(t.content||""),replies:(t.replies||[]).map(e=>({...e,rendered_content:d(e.content||"")}))}},hydrateRuntimeWidgets(){const t=()=>{m(this.$refs.articleContent),m(this.$refs.commentList),this.$refs.articleContent&&h(this.$refs.articleContent),this.$refs.commentList&&h(this.$refs.commentList)};t(),requestAnimationFrame(t),setTimeout(t,0)},getCommentPreview(t){const e=String(t||"").replace(/\[(?:\/)?(?:b|i|u|img|audio|movie|qqmusic|wymusic|url|forecolor|code|text|codo)(?:=[^\]]+)?\]/gi," ").replace(/\[now\]/gi," ").replace(/https?:\/\/\S+/gi," ").replace(/\s+/g," ").trim();return e?e.length>90?e.slice(0,90)+"...":e:/\[(?:img)\]/i.test(t||"")?"这条评论包含图片内容":/\[(?:audio)\]/i.test(t||"")?"这条评论包含音频内容":/\[(?:movie)\]/i.test(t||"")?"这条评论包含视频内容":/\[(?:qqmusic|wymusic)\]/i.test(t||"")?"这条评论包含音乐内容":/\[(?:code)\]/i.test(t||"")?"这条评论包含代码内容":""},scrollToHeading(t){const e=document.getElementById(t);if(!e)return;const s=document.querySelector(".pn-main");if(s&&window.innerWidth>=960){const a=s.getBoundingClientRect(),o=e.getBoundingClientRect().top-a.top+s.scrollTop-20;s.scrollTo({top:o,behavior:"smooth"})}else window.scrollTo({top:e.getBoundingClientRect().top+window.pageYOffset-80,behavior:"smooth"})},async toggleLike(){if(!this.isAuthenticated){window.location.href="/login/?next="+encodeURIComponent(window.location.pathname);return}if(!this.isLiking){this.isLiking=!0;try{const e=await(await fetch("/api/toggle-note-like/",{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({note_id:this.note.id})})).json();e.status==="success"&&(this.note.user_has_liked=e.user_has_liked,this.note.likes=e.total_likes,this.showToast(e.action==="liked"?"点赞成功！":"已取消点赞","success"))}catch{this.showToast("操作失败，请稍后重试","error")}finally{this.isLiking=!1}}},async fetchFollowStatus(){if(!(!this.note||!this.note.author||!this.note.author.id||this.isOwnNote))try{const t=await fetch(`/api/users/${this.note.author.id}/follow-status/`);if(!t.ok)return;const e=await t.json();this.isFollowing=!!e.is_following,this.followersCount=Number(e.followers_count||0)}catch(t){console.error("加载关注状态失败:",t)}},async toggleFollow(){if(!(this.followLoading||this.isOwnNote||!this.note||!this.note.author||!this.note.author.id)){if(!this.isAuthenticated){window.location.href="/login/?next="+encodeURIComponent(window.location.pathname);return}this.followLoading=!0;try{const t=this.isFollowing?"/api/users/unfollow/":"/api/users/follow/",e=await fetch(t,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({user_id:this.note.author.id})}),s=await e.json();e.ok&&s.status==="success"?(this.isFollowing=!!s.is_following,this.followersCount=Number(s.followers_count||0),this.showToast(this.isFollowing?"关注成功":"已取消关注","success")):this.showToast(s.error||"关注操作失败","error")}catch{this.showToast("网络错误，请稍后重试","error")}finally{this.followLoading=!1}}},openMessageModal(){this.messageTarget={userId:this.note.author.id,username:this.note.author.username,avatar:this.note.author.avatar_url},this.messageContext="",this.messageContextLink="",this.showMessageModal=!0,this.messageContent=""},openCommentMessage(t){this.closeUserCard(),this.messageTarget={userId:t.author_id,username:t.author,avatar:t.author_avatar},this.messageContext="来自笔记《"+this.note.title+"》下的评论",this.messageContextLink=this.buildCommentLink(t.id),this.showMessageModal=!0,this.messageContent=""},closeMessageModal(){this.showMessageModal=!1,this.messageContent="",this.messageContext="",this.messageContextLink=""},async sendMessage(){if(!(!this.messageContent.trim()||this.isSendingMessage)){this.isSendingMessage=!0;try{let t=this.messageContent.trim();this.messageContext&&(t=(this.messageContextLink?"["+this.sanitizeMarkdownLinkText(this.messageContext)+"]("+this.messageContextLink+")":"【"+this.messageContext+"】")+`

`+t);const e=await fetch("/api/messages/send/",{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({recipient_id:this.messageTarget.userId,content:t})}),s=await e.json();e.ok?(this.showToast("私信已发送！","success"),this.closeMessageModal()):e.status===403?this.showToast(s.error||"此用户未开启私信功能","warning"):e.status===401?this.showToast("请先登录后再发送私信","warning"):this.showToast(s.error||"发送失败","error")}catch{this.showToast("网络错误，请稍后重试","error")}finally{this.isSendingMessage=!1}}},showUserCard(t,e){e.author_id&&(this.userCard={visible:!0,userId:e.author_id,username:e.author,avatar:e.author_avatar,commentId:e.id},this.userCardClickPos={x:t.clientX,y:t.clientY})},closeUserCard(){this.userCard.visible=!1},openCardMessage(){this.openCommentMessage({author_id:this.userCard.userId,author:this.userCard.username,author_avatar:this.userCard.avatar,id:this.userCard.commentId})},startReplyToUser(){const t=this.comments.find(e=>e.id===this.userCard.commentId);t&&this.startReply(t),this.closeUserCard()},async openAuthorCard(){if(!(!this.note||!this.note.author)){this.authorCard={visible:!0,username:this.note.author.username||"",avatar:this.note.author.avatar_url||"",bio:"",notes_count:this.note.author.note_count||0,views_count:0,likes_count:0,loading:!0};try{const t=await fetch(`/api/users/${this.note.author.id}/profile/`);if(t.ok){const e=await t.json();this.authorCard.bio=e.bio||"",typeof e.notes_count=="number"&&(this.authorCard.notes_count=e.notes_count),typeof e.views_count=="number"&&(this.authorCard.views_count=e.views_count),typeof e.likes_count=="number"&&(this.authorCard.likes_count=e.likes_count),e.avatar&&!this.authorCard.avatar&&(this.authorCard.avatar=e.avatar)}}catch(t){console.error("加载作者资料失败:",t)}finally{this.authorCard.loading=!1}}},closeAuthorCard(){this.authorCard.visible=!1},messageFromAuthorCard(){this.closeAuthorCard(),this.openMessageModal()},goToAuthorProfile(){this.note&&this.note.author&&this.note.author.id&&(window.location.href=`/user/${this.note.author.id}/`)},getCookie(t){const e=document.cookie.match(new RegExp("(?:^|; )"+t+"=([^;]*)"));return e?decodeURIComponent(e[1]):""},sanitizeMarkdownLinkText(t){return String(t||"").replace(/[\r\n[\]]/g," ")},buildCommentLink(t){if(!t)return"";const e=this.note&&this.note.public_id,s=e?`/notes/public/${e}/`:window.location.pathname;return`${window.location.origin}${s}?comment=${encodeURIComponent(t)}#comment-${encodeURIComponent(t)}`},getLinkedCommentId(){const e=new URLSearchParams(window.location.search).get("comment");if(e)return e;const s=window.location.hash.match(/^#comment-(.+)$/);return s?decodeURIComponent(s[1]):""},scrollToLinkedComment(){const t=this.getLinkedCommentId();if(!t)return;const e=document.getElementById(`comment-${t}`);if(!e)return;const s=document.querySelector(".pn-main");if(s&&window.innerWidth>=960){const a=s.getBoundingClientRect(),o=e.getBoundingClientRect().top-a.top+s.scrollTop-80;s.scrollTo({top:Math.max(0,o),behavior:"smooth"})}else window.scrollTo({top:e.getBoundingClientRect().top+window.pageYOffset-80,behavior:"smooth"});e.classList.remove("pn-comment-jump-highlight"),e.offsetWidth,e.classList.add("pn-comment-jump-highlight"),setTimeout(()=>e.classList.remove("pn-comment-jump-highlight"),2600)},fixImageUrls(t){if(!t)return"";const e=window.location.origin+"/",s=document.createElement("div");return s.innerHTML=t,s.querySelectorAll("img").forEach(a=>{const n=a.getAttribute("src");n&&!n.match(/^https?:\/\//)&&!n.match(/^\/\//)&&a.setAttribute("src",e+n.replace(/^\//,""))}),s.innerHTML},showToast(t,e="success"){const s=document.createElement("div");s.className=`pn-toast ${e}`,s.textContent=t,document.body.appendChild(s),setTimeout(()=>{s.classList.add("fade-out"),setTimeout(()=>s.remove(),300)},2700)},toggleTheme(){const t=document.documentElement.getAttribute("data-theme")||"light";document.documentElement.setAttribute("data-theme",t==="light"?"dark":"light"),localStorage.setItem("theme",t==="light"?"dark":"light")},adjustFontSize(){const t=this.$refs.articleContent;if(!t)return;const e=["font-size-small","font-size-medium","font-size-large"];let s=e.findIndex(a=>t.classList.contains(a));s===-1&&(s=1),t.classList.remove(...e),t.classList.add(e[(s+1)%e.length])},shareArticle(){const t=window.location.href;navigator.share?navigator.share({title:this.note.title,url:t}).catch(()=>this.copyLink(t)):this.copyLink(t)},copyLink(t){if(navigator.clipboard)navigator.clipboard.writeText(t).then(()=>this.showToast("链接已复制","success"));else{const e=document.createElement("textarea");e.value=t,document.body.appendChild(e),e.select(),document.execCommand("copy"),e.remove(),this.showToast("链接已复制","success")}},setupScrollListener(){const t=this.$refs.progressBar,e=this;let s=null,a=null;const n=i=>{if(!e.note||!e.note.toc||!e.note.toc.length)return;const r=e.note.toc.map(c=>document.getElementById(c.id)).filter(Boolean);let l="";for(const c of r)c.getBoundingClientRect().top-i<=90&&(l=c.id);e.activeTocId=l},o=i=>i===window?()=>{if(t){const r=window.pageYOffset,l=document.documentElement.scrollHeight-window.innerHeight;t.style.width=(l>0?r/l*100:0)+"%"}n(0)}:()=>{if(t){const r=i.scrollHeight-i.clientHeight;t.style.width=(r>0?i.scrollTop/r*100:0)+"%"}n(i.getBoundingClientRect().top)},p=()=>{s&&a&&s.removeEventListener("scroll",a);const i=document.querySelector(".pn-main");i&&window.innerWidth>=960&&i.scrollHeight>i.clientHeight?s=i:s=window,a=o(s),s.addEventListener("scroll",a,{passive:!0})};this.$nextTick(p);let f=null;window.addEventListener("resize",()=>{clearTimeout(f),f=setTimeout(p,200)},{passive:!0})}}});u.config.errorHandler=(t,e,s)=>console.error("Vue error:",t,s),u.mount("#public-note-app")});
