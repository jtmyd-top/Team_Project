document.addEventListener("DOMContentLoaded",function(){if(window.GLOBAL_DATA={noteData:null,navigationData:null,isAuthenticated:!1},function(){const t=document.getElementById("navigation-data"),e=document.getElementById("note-data");if(t)try{const s=JSON.parse(t.textContent);window.GLOBAL_DATA.navigationData=s,window.GLOBAL_DATA.isAuthenticated=s.is_authenticated||!1}catch(s){console.error("解析导航数据失败:",s)}if(e)try{window.GLOBAL_DATA.noteData=JSON.parse(e.textContent)}catch(s){console.error("解析笔记数据失败:",s)}}(),typeof Vue>"u"){console.error("Vue not loaded");return}const h=Vue.createApp({template:`
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
                v-if="isAuthenticated && !isOwnNote"
                class="pn-message-btn"
                @click="openMessageModal"
                title="发送私信"
              >
                <i class="fas fa-envelope"></i>
                私信
              </button>
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
              <div class="pn-comment-list">
                <div v-if="isLoadingComments" style="padding:2rem;text-align:center;color:#94a3b8">
                  <i class="fas fa-spinner fa-spin"></i> 加载评论中...
                </div>
                <div v-else-if="comments.length === 0" class="pn-comment-empty">
                  <i class="far fa-comment-dots"></i>
                  暂无评论，来发表第一条吧！
                </div>
                <div v-else>
                  <div v-for="comment in comments" :key="comment.id" class="pn-comment-item">
                    <div class="pn-comment-row">
                      <img v-if="comment.author_avatar" :src="comment.author_avatar" class="pn-comment-avatar pn-clickable-user" :alt="comment.author" @click="showUserCard($event, comment)">
                      <div v-else class="pn-comment-avatar-text pn-clickable-user" @click="showUserCard($event, comment)">{{ comment.author.charAt(0).toUpperCase() }}</div>
                      <div class="pn-comment-body">
                        <div class="pn-comment-meta">
                          <span class="pn-comment-author pn-clickable-user" @click="showUserCard($event, comment)">{{ comment.author }}</span>
                          <span class="pn-comment-time">{{ comment.created_at }}</span>
                        </div>
                        <div class="pn-comment-content">{{ comment.content }}</div>
                        <div class="pn-comment-actions">
                          <button v-if="isAuthenticated" class="pn-comment-action-btn" @click="startReply(comment)">
                            <i class="fas fa-reply"></i> 回复
                          </button>
                          <button v-if="isAuthenticated && !comment.is_owner && comment.author_id !== currentUserId" class="pn-comment-action-btn message" @click="openCommentMessage(comment)">
                            <i class="fas fa-envelope"></i> 私信
                          </button>
                          <button v-if="comment.is_owner" class="pn-comment-action-btn delete" @click="deleteComment(comment.id)">
                            <i class="fas fa-trash"></i> 删除
                          </button>
                        </div>

                        <!-- 回复列表 -->
                        <div v-if="comment.replies && comment.replies.length" class="pn-replies">
                          <div v-for="reply in comment.replies" :key="reply.id" class="pn-reply-item">
                            <img v-if="reply.author_avatar" :src="reply.author_avatar" class="pn-reply-avatar pn-clickable-user" :alt="reply.author" @click="showUserCard($event, reply)">
                            <div v-else class="pn-reply-avatar-text pn-clickable-user" @click="showUserCard($event, reply)">{{ reply.author.charAt(0).toUpperCase() }}</div>
                            <div class="pn-reply-body">
                              <div class="pn-reply-meta">
                                <span class="pn-reply-author pn-clickable-user" @click="showUserCard($event, reply)">{{ reply.author }}</span>
                                <span class="pn-reply-time">{{ reply.created_at }}</span>
                              </div>
                              <div class="pn-reply-content">{{ reply.content }}</div>
                              <div class="pn-comment-actions">
                                <button v-if="isAuthenticated && !reply.is_owner && reply.author_id !== currentUserId" class="pn-comment-action-btn message" @click="openCommentMessage(reply)">
                                  <i class="fas fa-envelope"></i> 私信
                                </button>
                                <button v-if="reply.is_owner" class="pn-comment-action-btn delete" @click="deleteComment(reply.id)">
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
    `,data(){return{note:null,errorMessage:null,fullContent:"",isLiking:!1,isAuthenticated:!1,readingTime:0,moreNotes:[],activeTocId:"",currentUserInitial:"U",currentPath:window.location.pathname,currentUserId:null,comments:[],commentContent:"",replyContent:"",replyingToId:null,isSubmittingComment:!1,isLoadingComments:!1,totalComments:0,showMessageModal:!1,messageContent:"",isSendingMessage:!1,messageTarget:{userId:null,username:"",avatar:""},messageContext:"",userCard:{visible:!1,userId:null,username:"",avatar:"",commentId:null},userCardClickPos:{x:0,y:0}}},computed:{displayContent(){return this.fullContent?this.fixImageUrls(this.fullContent):""},isOwnNote(){return!this.note||!this.currentUserId?!1:this.note.author.id===this.currentUserId},userCardPosition(){return{}}},mounted(){this.initializeData(),this.setupScrollListener()},methods:{initializeData(){const t=window.GLOBAL_DATA;if(!t||!t.noteData){this.errorMessage="无法获取页面数据";return}this.note=t.noteData,this.isAuthenticated=t.isAuthenticated,this.totalComments=this.note.comment_count||0;const e=document.querySelector('meta[name="user-id"]');e&&e.content&&(this.currentUserId=parseInt(e.content));const s=document.querySelector('meta[name="username"]');s&&(this.currentUserInitial=s.content.charAt(0).toUpperCase()),t.navigationData&&(this.moreNotes=(t.navigationData.navigation_list||[]).filter(a=>a.public_id!==this.note.public_id).slice(0,5));const n=document.getElementById("full-content-data");if(n)try{this.fullContent=JSON.parse(n.textContent)}catch{this.fullContent=this.note.content||""}else this.fullContent=this.note.content||"";if(!this.fullContent){this.errorMessage="无法加载文章内容";return}this.readingTime=Math.max(1,Math.ceil(this.fullContent.replace(/<[^>]+>/g,"").length/400)),this.$nextTick(()=>{this.enhanceCodeBlocks(),this.fetchComments()})},async fetchComments(){if(this.note){this.isLoadingComments=!0;try{const e=await(await fetch(`/api/notes/${this.note.id}/comments/`)).json();this.comments=e.comments||[],this.totalComments=e.total||0}catch(t){console.error("加载评论失败:",t)}finally{this.isLoadingComments=!1}}},async submitComment(){if(!(!this.commentContent.trim()||this.isSubmittingComment)){this.isSubmittingComment=!0;try{const t=await fetch(`/api/notes/${this.note.id}/comments/create/`,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({content:this.commentContent.trim()})});if(t.status===201){const e=await t.json();e.replies=[],this.comments.push(e),this.totalComments++,this.commentContent="",this.showToast("评论发表成功！","success")}else{const e=await t.json();this.showToast(e.error||"发表失败","error")}}catch{this.showToast("网络错误，请稍后重试","error")}finally{this.isSubmittingComment=!1}}},async submitReply(t){if(!(!this.replyContent.trim()||this.isSubmittingComment)){this.isSubmittingComment=!0;try{const e=await fetch(`/api/notes/${this.note.id}/comments/create/`,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({content:this.replyContent.trim(),parent_id:t})});if(e.status===201){const s=await e.json(),n=this.comments.find(a=>a.id===t);n&&n.replies.push(s),this.totalComments++,this.replyContent="",this.replyingToId=null,this.showToast("回复成功！","success")}else{const s=await e.json();this.showToast(s.error||"回复失败","error")}}catch{this.showToast("网络错误，请稍后重试","error")}finally{this.isSubmittingComment=!1}}},async deleteComment(t){if(confirm("确定要删除这条评论吗？"))try{if((await fetch(`/api/comments/${t}/delete/`,{method:"DELETE",headers:{"X-CSRFToken":this.getCookie("csrftoken")}})).ok){const s=this.comments.findIndex(n=>n.id===t);if(s!==-1){const n=this.comments.splice(s,1)[0];this.totalComments-=1+(n.replies?n.replies.length:0)}else this.comments.forEach(n=>{const a=(n.replies||[]).findIndex(i=>i.id===t);a!==-1&&(n.replies.splice(a,1),this.totalComments--)});this.showToast("评论已删除","success")}}catch{this.showToast("删除失败","error")}},startReply(t){this.replyingToId=t.id,this.replyContent=""},cancelReply(){this.replyingToId=null,this.replyContent=""},scrollToHeading(t){const e=document.getElementById(t);if(!e)return;const s=document.querySelector(".pn-main");if(s&&window.innerWidth>=960){const n=s.getBoundingClientRect(),i=e.getBoundingClientRect().top-n.top+s.scrollTop-20;s.scrollTo({top:i,behavior:"smooth"})}else window.scrollTo({top:e.getBoundingClientRect().top+window.pageYOffset-80,behavior:"smooth"})},async toggleLike(){if(!this.isAuthenticated){window.location.href="/login/?next="+encodeURIComponent(window.location.pathname);return}if(!this.isLiking){this.isLiking=!0;try{const e=await(await fetch("/api/toggle-note-like/",{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({note_id:this.note.id})})).json();e.status==="success"&&(this.note.user_has_liked=e.user_has_liked,this.note.likes=e.total_likes,this.showToast(e.action==="liked"?"点赞成功！":"已取消点赞","success"))}catch{this.showToast("操作失败，请稍后重试","error")}finally{this.isLiking=!1}}},openMessageModal(){this.messageTarget={userId:this.note.author.id,username:this.note.author.username,avatar:this.note.author.avatar_url},this.messageContext="",this.showMessageModal=!0,this.messageContent=""},openCommentMessage(t){this.closeUserCard(),this.messageTarget={userId:t.author_id,username:t.author,avatar:t.author_avatar},this.messageContext="来自笔记《"+this.note.title+"》下的评论",this.showMessageModal=!0,this.messageContent=""},closeMessageModal(){this.showMessageModal=!1,this.messageContent="",this.messageContext=""},async sendMessage(){if(!(!this.messageContent.trim()||this.isSendingMessage)){this.isSendingMessage=!0;try{let t=this.messageContent.trim();this.messageContext&&(t="【"+this.messageContext+`】

`+t);const e=await fetch("/api/messages/send/",{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":this.getCookie("csrftoken")},body:JSON.stringify({recipient_id:this.messageTarget.userId,content:t})}),s=await e.json();e.ok?(this.showToast("私信已发送！","success"),this.closeMessageModal()):e.status===403?this.showToast(s.error||"此用户未开启私信功能","warning"):e.status===401?this.showToast("请先登录后再发送私信","warning"):this.showToast(s.error||"发送失败","error")}catch{this.showToast("网络错误，请稍后重试","error")}finally{this.isSendingMessage=!1}}},showUserCard(t,e){e.author_id&&(this.userCard={visible:!0,userId:e.author_id,username:e.author,avatar:e.author_avatar,commentId:e.id},this.userCardClickPos={x:t.clientX,y:t.clientY})},closeUserCard(){this.userCard.visible=!1},openCardMessage(){this.openCommentMessage({author_id:this.userCard.userId,author:this.userCard.username,author_avatar:this.userCard.avatar})},startReplyToUser(){const t=this.comments.find(e=>e.id===this.userCard.commentId);t&&this.startReply(t),this.closeUserCard()},getCookie(t){const e=document.cookie.match(new RegExp("(?:^|; )"+t+"=([^;]*)"));return e?decodeURIComponent(e[1]):""},fixImageUrls(t){if(!t)return"";const e=window.location.origin+"/",s=document.createElement("div");return s.innerHTML=t,s.querySelectorAll("img").forEach(n=>{const a=n.getAttribute("src");a&&!a.match(/^https?:\/\//)&&!a.match(/^\/\//)&&n.setAttribute("src",e+a.replace(/^\//,""))}),s.innerHTML},showToast(t,e="success"){const s=document.createElement("div");s.className=`pn-toast ${e}`,s.textContent=t,document.body.appendChild(s),setTimeout(()=>{s.classList.add("fade-out"),setTimeout(()=>s.remove(),300)},2700)},toggleTheme(){const t=document.documentElement.getAttribute("data-theme")||"light";document.documentElement.setAttribute("data-theme",t==="light"?"dark":"light"),localStorage.setItem("theme",t==="light"?"dark":"light")},adjustFontSize(){const t=this.$refs.articleContent;if(!t)return;const e=["font-size-small","font-size-medium","font-size-large"];let s=e.findIndex(n=>t.classList.contains(n));s===-1&&(s=1),t.classList.remove(...e),t.classList.add(e[(s+1)%e.length])},shareArticle(){const t=window.location.href;navigator.share?navigator.share({title:this.note.title,url:t}).catch(()=>this.copyLink(t)):this.copyLink(t)},copyLink(t){if(navigator.clipboard)navigator.clipboard.writeText(t).then(()=>this.showToast("链接已复制","success"));else{const e=document.createElement("textarea");e.value=t,document.body.appendChild(e),e.select(),document.execCommand("copy"),e.remove(),this.showToast("链接已复制","success")}},setupScrollListener(){const t=this.$refs.progressBar,e=this;let s=null,n=null;const a=o=>{if(!e.note||!e.note.toc||!e.note.toc.length)return;const c=e.note.toc.map(m=>document.getElementById(m.id)).filter(Boolean);let d="";for(const m of c)m.getBoundingClientRect().top-o<=90&&(d=m.id);e.activeTocId=d},i=o=>o===window?()=>{if(t){const c=window.pageYOffset,d=document.documentElement.scrollHeight-window.innerHeight;t.style.width=(d>0?c/d*100:0)+"%"}a(0)}:()=>{if(t){const c=o.scrollHeight-o.clientHeight;t.style.width=(c>0?o.scrollTop/c*100:0)+"%"}a(o.getBoundingClientRect().top)},r=()=>{s&&n&&s.removeEventListener("scroll",n);const o=document.querySelector(".pn-main");o&&window.innerWidth>=960&&o.scrollHeight>o.clientHeight?s=o:s=window,n=i(s),s.addEventListener("scroll",n,{passive:!0})};this.$nextTick(r);let l=null;window.addEventListener("resize",()=>{clearTimeout(l),l=setTimeout(r,200)},{passive:!0})},enhanceCodeBlocks(){const t=this.$refs.articleContent;t&&t.querySelectorAll("pre").forEach(e=>{if(e.classList.contains("code-block-enhanced"))return;let s=e.querySelector("code");if(s||(e.innerHTML=`<code>${e.innerHTML}</code>`,s=e.querySelector("code")),!s)return;e.classList.add("code-block-enhanced");let n=s.textContent.split(`
`).length;n<=1&&(n=(s.innerHTML.match(/<br\s*\/?>/gi)||[]).length+1);const a=5;n>a&&e.classList.add("long-code","collapsed");const i=document.createElement("button");if(i.className="copy-btn",i.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>',e.appendChild(i),i.addEventListener("click",async r=>{r.stopPropagation();try{await navigator.clipboard.writeText(s.textContent),i.classList.add("copied"),i.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>',setTimeout(()=>{i.classList.remove("copied"),i.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'},2e3)}catch{}}),n>a){const r=document.createElement("button");r.className="collapse-btn",r.textContent="展开代码",e.appendChild(r),r.addEventListener("click",l=>{l.stopPropagation(),e.classList.toggle("collapsed"),r.textContent=e.classList.contains("collapsed")?"展开代码":"收起代码"})}})}}});h.config.errorHandler=(t,e,s)=>console.error("Vue error:",t,s),h.mount("#public-note-app")});
