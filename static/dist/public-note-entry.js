const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["chunks/ubb-CzoRHiNp.js","chunks/vendor-wzGsUuS6.js"])))=>i.map(i=>d[i]);
import{_ as f}from"./chunks/preload-helper-CYKyUB34.js";document.addEventListener("DOMContentLoaded",async function(){const{convertUbbMarkupInHtml:g,renderCommentUbb:d,hydrateUbbDom:m}=await f(async()=>{const{convertUbbMarkupInHtml:e,renderCommentUbb:t,hydrateUbbDom:s}=await import("./chunks/ubb-CzoRHiNp.js");return{convertUbbMarkupInHtml:e,renderCommentUbb:t,hydrateUbbDom:s}},__vite__mapDeps([0,1])),{enhanceCodeBlocks:h}=await f(async()=>{const{enhanceCodeBlocks:e}=await import("./chunks/useCodeEnhancer-D0rmz2rR.js");return{enhanceCodeBlocks:e}},[]);if(window.GLOBAL_DATA={noteData:null,navigationData:null,isAuthenticated:!1},function(){const e=document.getElementById("navigation-data"),t=document.getElementById("note-data");if(e)try{const s=JSON.parse(e.textContent);window.GLOBAL_DATA.navigationData=s,window.GLOBAL_DATA.isAuthenticated=s.is_authenticated||!1}catch(s){console.error("解析导航数据失败:",s)}if(t)try{window.GLOBAL_DATA.noteData=JSON.parse(t.textContent)}catch(s){console.error("解析笔记数据失败:",s)}}(),typeof Vue>"u"){console.error("Vue not loaded");return}const u=Vue.createApp({template:`
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
    `,data(){return{note:null,errorMessage:null,fullContent:"",isLiking:!1,isFollowing:!1,followLoading:!1,followersCount:0,isAuthenticated:!1,readingTime:0,moreNotes:[],activeTocId:"",currentUserInitial:"U",currentPath:window.location.pathname,currentUserId:null,comments:[],commentContent:"",replyContent:"",replyingToId:null,isSubmittingComment:!1,isLoadingComments:!1,totalComments:0,showMessageModal:!1,messageContent:"",isSendingMessage:!1,messageTarget:{userId:null,username:"",avatar:""},messageContext:"",messageContextLink:"",deleteConfirm:{visible:!1,deleting:!1,commentId:null,kind:"comment",replyCount:0,preview:""},userCard:{visible:!1,userId:null,username:"",avatar:"",commentId:null},userCardClickPos:{x:0,y:0}}},computed:{displayContent(){return this.fullContent?this.fixImageUrls(g(this.fullContent)):""},isOwnNote(){return!this.note||!this.currentUserId?!1:this.note.author.id===this.currentUserId},userCardPosition(){return{}}},mounted(){this.initializeData(),this.setupScrollListener()},updated(){this.hydrateRuntimeWidgets()},methods:{initializeData(){const e=window.GLOBAL_DATA;if(!e||!e.noteData){this.errorMessage="无法获取页面数据";return}this.note=e.noteData,this.isAuthenticated=e.isAuthenticated,this.totalComments=this.note.comment_count||0;const t=document.querySelector('meta[name="user-id"]');t&&t.content&&(this.currentUserId=parseInt(t.content));const s=document.querySelector('meta[name="username"]');s&&(this.currentUserInitial=s.content.charAt(0).toUpperCase()),e.navigationData&&(this.moreNotes=(e.navigationData.navigation_list||[]).filter(i=>i.public_id!==this.note.public_id).slice(0,5));const n=document.getElementById("full-content-data");if(n)try{this.fullContent=JSON.parse(n.textContent)}catch{this.fullContent=this.note.content||""}else this.fullContent=this.note.content||"";if(!this.fullContent){this.errorMessage="无法加载文章内容";return}this.readingTime=Math.max(1,Math.ceil(this.fullContent.replace(/<[^>]+>/g,"").length/400)),this.fetchFollowStatus(),this.$nextTick(()=>{this.hydrateRuntimeWidgets(),this.fetchComments()})},async fetchComments(){if(this.note){this.isLoadingComments=!0;try{const t=await(await fetch(`/api/notes/${this.note.id}/comments/`)).json();this.comments=(t.comments||[]).map(s=>this.decorateComment(s)),this.totalComments=t.total||0}catch(e){console.error("加载评论失败:",e)}finally{this.isLoadingComments=!1,this.$nextTick(()=>{this.hydrateRuntimeWidgets(),this.scrollToLinkedComment()})}}},async submitComment(){if(!(!this.commentContent.trim()||this.isSubmittingComment)){this.isSubmittingComment=!0;try{const e=await fetch(`/api/notes/${this.note.id}/comments/create/`,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({content:this.commentContent.trim()})});if(e.status===201){const t=this.decorateComment(await e.json());t.replies=[],this.comments.push(t),this.totalComments++,this.commentContent="",this.$nextTick(()=>this.hydrateRuntimeWidgets()),this.showToast("评论发表成功！","success")}else{const t=await e.json();this.showToast(t.error||"发表失败","error")}}catch{this.showToast("网络错误，请稍后重试","error")}finally{this.isSubmittingComment=!1}}},async submitReply(e){if(!(!this.replyContent.trim()||this.isSubmittingComment)){this.isSubmittingComment=!0;try{const t=await fetch(`/api/notes/${this.note.id}/comments/create/`,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({content:this.replyContent.trim(),parent_id:e})});if(t.status===201){const s=this.decorateComment(await t.json()),n=this.comments.find(i=>i.id===e);n&&n.replies.push(s),this.totalComments++,this.replyContent="",this.replyingToId=null,this.$nextTick(()=>this.hydrateRuntimeWidgets()),this.showToast("回复成功！","success")}else{const s=await t.json();this.showToast(s.error||"回复失败","error")}}catch{this.showToast("网络错误，请稍后重试","error")}finally{this.isSubmittingComment=!1}}},openDeleteConfirm(e,t=null){this.deleteConfirm={visible:!0,deleting:!1,commentId:e.id,kind:t?"reply":"comment",replyCount:t?0:(e.replies||[]).length,preview:this.getCommentPreview(e.content||"")}},closeDeleteConfirm(){this.deleteConfirm.deleting||(this.deleteConfirm.visible=!1)},async confirmDeleteComment(){const e=this.deleteConfirm.commentId;if(e){this.deleteConfirm.deleting=!0;try{if((await fetch(`/api/comments/${e}/delete/`,{method:"DELETE",headers:{"X-CSRFToken":this.getCookie("csrftoken")}})).ok){const s=this.comments.findIndex(n=>n.id===e);if(s!==-1){const n=this.comments.splice(s,1)[0];this.totalComments-=1+(n.replies?n.replies.length:0)}else this.comments.forEach(n=>{const i=(n.replies||[]).findIndex(o=>o.id===e);i!==-1&&(n.replies.splice(i,1),this.totalComments--)});this.showToast("评论已删除","success")}}catch{this.showToast("删除失败","error")}finally{this.deleteConfirm={visible:!1,deleting:!1,commentId:null,kind:"comment",replyCount:0,preview:""}}}},startReply(e){this.replyingToId=e.id,this.replyContent=""},cancelReply(){this.replyingToId=null,this.replyContent=""},decorateComment(e){return{...e,rendered_content:d(e.content||""),replies:(e.replies||[]).map(t=>({...t,rendered_content:d(t.content||"")}))}},hydrateRuntimeWidgets(){const e=()=>{m(this.$refs.articleContent),m(this.$refs.commentList),this.$refs.articleContent&&h(this.$refs.articleContent),this.$refs.commentList&&h(this.$refs.commentList)};e(),requestAnimationFrame(e),setTimeout(e,0)},getCommentPreview(e){const t=String(e||"").replace(/\[(?:\/)?(?:b|i|u|img|audio|movie|qqmusic|wymusic|url|forecolor|code|text|codo)(?:=[^\]]+)?\]/gi," ").replace(/\[now\]/gi," ").replace(/https?:\/\/\S+/gi," ").replace(/\s+/g," ").trim();return t?t.length>90?t.slice(0,90)+"...":t:/\[(?:img)\]/i.test(e||"")?"这条评论包含图片内容":/\[(?:audio)\]/i.test(e||"")?"这条评论包含音频内容":/\[(?:movie)\]/i.test(e||"")?"这条评论包含视频内容":/\[(?:qqmusic|wymusic)\]/i.test(e||"")?"这条评论包含音乐内容":/\[(?:code)\]/i.test(e||"")?"这条评论包含代码内容":""},scrollToHeading(e){const t=document.getElementById(e);if(!t)return;const s=document.querySelector(".pn-main");if(s&&window.innerWidth>=960){const n=s.getBoundingClientRect(),o=t.getBoundingClientRect().top-n.top+s.scrollTop-20;s.scrollTo({top:o,behavior:"smooth"})}else window.scrollTo({top:t.getBoundingClientRect().top+window.pageYOffset-80,behavior:"smooth"})},async toggleLike(){if(!this.isAuthenticated){window.location.href="/login/?next="+encodeURIComponent(window.location.pathname);return}if(!this.isLiking){this.isLiking=!0;try{const t=await(await fetch("/api/toggle-note-like/",{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({note_id:this.note.id})})).json();t.status==="success"&&(this.note.user_has_liked=t.user_has_liked,this.note.likes=t.total_likes,this.showToast(t.action==="liked"?"点赞成功！":"已取消点赞","success"))}catch{this.showToast("操作失败，请稍后重试","error")}finally{this.isLiking=!1}}},async fetchFollowStatus(){if(!(!this.note||!this.note.author||!this.note.author.id||this.isOwnNote))try{const e=await fetch(`/api/users/${this.note.author.id}/follow-status/`);if(!e.ok)return;const t=await e.json();this.isFollowing=!!t.is_following,this.followersCount=Number(t.followers_count||0)}catch(e){console.error("加载关注状态失败:",e)}},async toggleFollow(){if(!(this.followLoading||this.isOwnNote||!this.note||!this.note.author||!this.note.author.id)){if(!this.isAuthenticated){window.location.href="/login/?next="+encodeURIComponent(window.location.pathname);return}this.followLoading=!0;try{const e=this.isFollowing?"/api/users/unfollow/":"/api/users/follow/",t=await fetch(e,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({user_id:this.note.author.id})}),s=await t.json();t.ok&&s.status==="success"?(this.isFollowing=!!s.is_following,this.followersCount=Number(s.followers_count||0),this.showToast(this.isFollowing?"关注成功":"已取消关注","success")):this.showToast(s.error||"关注操作失败","error")}catch{this.showToast("网络错误，请稍后重试","error")}finally{this.followLoading=!1}}},openMessageModal(){this.messageTarget={userId:this.note.author.id,username:this.note.author.username,avatar:this.note.author.avatar_url},this.messageContext="",this.messageContextLink="",this.showMessageModal=!0,this.messageContent=""},openCommentMessage(e){this.closeUserCard(),this.messageTarget={userId:e.author_id,username:e.author,avatar:e.author_avatar},this.messageContext="来自笔记《"+this.note.title+"》下的评论",this.messageContextLink=this.buildCommentLink(e.id),this.showMessageModal=!0,this.messageContent=""},closeMessageModal(){this.showMessageModal=!1,this.messageContent="",this.messageContext="",this.messageContextLink=""},async sendMessage(){if(!(!this.messageContent.trim()||this.isSendingMessage)){this.isSendingMessage=!0;try{let e=this.messageContent.trim();this.messageContext&&(e=(this.messageContextLink?"["+this.sanitizeMarkdownLinkText(this.messageContext)+"]("+this.messageContextLink+")":"【"+this.messageContext+"】")+`

`+e);const t=await fetch("/api/messages/send/",{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({recipient_id:this.messageTarget.userId,content:e})}),s=await t.json();t.ok?(this.showToast("私信已发送！","success"),this.closeMessageModal()):t.status===403?this.showToast(s.error||"此用户未开启私信功能","warning"):t.status===401?this.showToast("请先登录后再发送私信","warning"):this.showToast(s.error||"发送失败","error")}catch{this.showToast("网络错误，请稍后重试","error")}finally{this.isSendingMessage=!1}}},showUserCard(e,t){t.author_id&&(this.userCard={visible:!0,userId:t.author_id,username:t.author,avatar:t.author_avatar,commentId:t.id},this.userCardClickPos={x:e.clientX,y:e.clientY})},closeUserCard(){this.userCard.visible=!1},openCardMessage(){this.openCommentMessage({author_id:this.userCard.userId,author:this.userCard.username,author_avatar:this.userCard.avatar,id:this.userCard.commentId})},startReplyToUser(){const e=this.comments.find(t=>t.id===this.userCard.commentId);e&&this.startReply(e),this.closeUserCard()},getCookie(e){const t=document.cookie.match(new RegExp("(?:^|; )"+e+"=([^;]*)"));return t?decodeURIComponent(t[1]):""},sanitizeMarkdownLinkText(e){return String(e||"").replace(/[\r\n[\]]/g," ")},buildCommentLink(e){if(!e)return"";const t=this.note&&this.note.public_id,s=t?`/notes/public/${t}/`:window.location.pathname;return`${window.location.origin}${s}?comment=${encodeURIComponent(e)}#comment-${encodeURIComponent(e)}`},getLinkedCommentId(){const t=new URLSearchParams(window.location.search).get("comment");if(t)return t;const s=window.location.hash.match(/^#comment-(.+)$/);return s?decodeURIComponent(s[1]):""},scrollToLinkedComment(){const e=this.getLinkedCommentId();if(!e)return;const t=document.getElementById(`comment-${e}`);if(!t)return;const s=document.querySelector(".pn-main");if(s&&window.innerWidth>=960){const n=s.getBoundingClientRect(),o=t.getBoundingClientRect().top-n.top+s.scrollTop-80;s.scrollTo({top:Math.max(0,o),behavior:"smooth"})}else window.scrollTo({top:t.getBoundingClientRect().top+window.pageYOffset-80,behavior:"smooth"});t.classList.remove("pn-comment-jump-highlight"),t.offsetWidth,t.classList.add("pn-comment-jump-highlight"),setTimeout(()=>t.classList.remove("pn-comment-jump-highlight"),2600)},fixImageUrls(e){if(!e)return"";const t=window.location.origin+"/",s=document.createElement("div");return s.innerHTML=e,s.querySelectorAll("img").forEach(n=>{const i=n.getAttribute("src");i&&!i.match(/^https?:\/\//)&&!i.match(/^\/\//)&&n.setAttribute("src",t+i.replace(/^\//,""))}),s.innerHTML},showToast(e,t="success"){const s=document.createElement("div");s.className=`pn-toast ${t}`,s.textContent=e,document.body.appendChild(s),setTimeout(()=>{s.classList.add("fade-out"),setTimeout(()=>s.remove(),300)},2700)},toggleTheme(){const e=document.documentElement.getAttribute("data-theme")||"light";document.documentElement.setAttribute("data-theme",e==="light"?"dark":"light"),localStorage.setItem("theme",e==="light"?"dark":"light")},adjustFontSize(){const e=this.$refs.articleContent;if(!e)return;const t=["font-size-small","font-size-medium","font-size-large"];let s=t.findIndex(n=>e.classList.contains(n));s===-1&&(s=1),e.classList.remove(...t),e.classList.add(t[(s+1)%t.length])},shareArticle(){const e=window.location.href;navigator.share?navigator.share({title:this.note.title,url:e}).catch(()=>this.copyLink(e)):this.copyLink(e)},copyLink(e){if(navigator.clipboard)navigator.clipboard.writeText(e).then(()=>this.showToast("链接已复制","success"));else{const t=document.createElement("textarea");t.value=e,document.body.appendChild(t),t.select(),document.execCommand("copy"),t.remove(),this.showToast("链接已复制","success")}},setupScrollListener(){const e=this.$refs.progressBar,t=this;let s=null,n=null;const i=a=>{if(!t.note||!t.note.toc||!t.note.toc.length)return;const r=t.note.toc.map(c=>document.getElementById(c.id)).filter(Boolean);let l="";for(const c of r)c.getBoundingClientRect().top-a<=90&&(l=c.id);t.activeTocId=l},o=a=>a===window?()=>{if(e){const r=window.pageYOffset,l=document.documentElement.scrollHeight-window.innerHeight;e.style.width=(l>0?r/l*100:0)+"%"}i(0)}:()=>{if(e){const r=a.scrollHeight-a.clientHeight;e.style.width=(r>0?a.scrollTop/r*100:0)+"%"}i(a.getBoundingClientRect().top)},p=()=>{s&&n&&s.removeEventListener("scroll",n);const a=document.querySelector(".pn-main");a&&window.innerWidth>=960&&a.scrollHeight>a.clientHeight?s=a:s=window,n=o(s),s.addEventListener("scroll",n,{passive:!0})};this.$nextTick(p);let v=null;window.addEventListener("resize",()=>{clearTimeout(v),v=setTimeout(p,200)},{passive:!0})}}});u.config.errorHandler=(e,t,s)=>console.error("Vue error:",e,s),u.mount("#public-note-app")});
