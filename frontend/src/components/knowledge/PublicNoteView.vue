<template>
  <div class="note-detail-container">
    <!-- 背景动画效果 -->
    <div class="bg-animation">
      <div class="floating-shapes">
        <div class="shape shape-1"></div>
        <div class="shape shape-2"></div>
        <div class="shape shape-3"></div>
        <div class="shape shape-4"></div>
        <div class="shape shape-5"></div>
      </div>
    </div>

    <!-- 阅读进度条 -->
    <div class="reading-progress">
      <div class="reading-progress-bar" id="reading-progress-bar"></div>
    </div>

    <div v-if="note">
        <!-- 顶部导航栏 -->
        <nav class="detail-navbar glass-effect animate__animated animate__fadeInDown">
          <div class="navbar-content">
            <div class="navbar-left">
              <a href="/knowledge/" class="back-button hover-glow">
                <i class="fas fa-arrow-left"></i>
                返回列表
              </a>
            </div>

            <div class="navbar-actions">
              <button class="action-button magnetic-btn" @click="toggleTheme" title="切换主题">
                <i class="fas fa-moon"></i>
              </button>
              <button class="action-button magnetic-btn" @click="adjustFontSize" title="调整字体">
                <i class="fas fa-font"></i>
              </button>
              <button class="action-button magnetic-btn" @click="toggleToc" title="目录">
                <i class="fas fa-list"></i>
              </button>
              <button class="action-button magnetic-btn" @click="shareArticle" title="分享">
                <i class="fas fa-share-alt"></i>
              </button>
            </div>
          </div>
        </nav>

        <!-- 主内容区域 -->
        <main class="detail-main">
          <!-- 文章头部 -->
          <header class="article-header animate__animated animate__fadeInUp">
            <div class="header-decoration">
              <div class="decoration-line"></div>
            </div>
            <h1 class="article-title gradient-text shimmer-text">${ note.title }</h1>

            <div class="article-meta glass-card">
              <div class="meta-item author-info hover-lift">
                <div class="author-avatar pulse-avatar">
                  <template v-if="note.author.avatar_url">
                    <img :src="note.author.avatar_url" :alt="note.author.username" class="avatar-img">
                  </template>
                  <template v-else>
                    <span class="avatar-text">${ note.author.username.charAt(0).toUpperCase() }</span>
                  </template>
                  <div class="avatar-ring"></div>
                </div>
                <div class="author-details">
                  <span class="author-name text-gradient">${ note.author.username }</span>
                  <span class="publish-date">
                    <i class="far fa-calendar-alt"></i>
                    发布于 ${ note.created_at }
                  </span>
                </div>
              </div>

              <div class="meta-divider"></div>

              <div class="meta-item hover-pulse">
                <div class="meta-icon">
                  <i class="far fa-clock"></i>
                </div>
                <span class="meta-text">阅读时间 ${ readingTime } 分钟</span>
              </div>

              <div class="meta-divider"></div>

              <div class="meta-item hover-pulse">
                <div class="meta-icon">
                  <i class="far fa-eye"></i>
                </div>
                <span class="meta-text">${ note.views || 0 } 次阅读</span>
              </div>

              <div class="meta-divider"></div>

              <div class="meta-item">
                <button
                  class="like-button"
                  :class="{ 'liked': note.user_has_liked }"
                  @click="toggleLike"
                  :disabled="isLiking"
                  title="给作者点赞"
                >
                  <div class="like-icon" :class="{ 'liked': note.user_has_liked }">
                    <i :class="note.user_has_liked ? 'fas' : 'far'" class="fa-heart"></i>
                  </div>
                  <span class="like-count">${ note.likes || 0 }</span>
                </button>
              </div>
            </div>
          </header>

          <!-- 文章内容 - 显示完整内容，无分页 -->
          <article class="article-content content-wrapper animate__animated animate__fadeIn" id="article-content">
            <NoteShadowViewer :content="fullContent" />
          </article>

          <!-- 文章标签 -->
          <div v-if="note.tags && note.tags.length > 0" class="article-tags animate__animated animate__fadeInUp">
            <div class="tags-container">
              <span v-for="tag in note.tags" :key="tag" class="tag hover-glow magnetic-tag">
                <i class="fas fa-tag tag-icon"></i>
                ${ tag }
              </span>
            </div>
          </div>

          <!-- 章节导航 -->
          <div class="chapter-navigation animate__animated animate__fadeInUp">
            <div class="navigation-container">
              <a v-if="previousNote" :href="previousNote.public_url" class="chapter-link prev hover-lift glass-card">
                <div class="nav-icon">
                  <i class="fas fa-arrow-left"></i>
                </div>
                <div class="chapter-info">
                  <span class="chapter-label">
                    <i class="fas fa-book-open"></i>
                    上一篇
                  </span>
                  <span class="chapter-title">${ previousNote.title }</span>
                </div>
              </a>

              <div v-else class="chapter-link prev disabled glass-card">
                <div class="nav-icon">
                  <i class="fas fa-arrow-left"></i>
                </div>
                <div class="chapter-info">
                  <span class="chapter-label">上一篇</span>
                  <span class="chapter-title">没有更多文章了</span>
                </div>
              </div>

              <div class="divider"></div>

              <a v-if="nextNote" :href="nextNote.public_url" class="chapter-link next hover-lift glass-card">
                <div class="chapter-info">
                  <span class="chapter-label">
                    下一篇
                    <i class="fas fa-book-open"></i>
                  </span>
                  <span class="chapter-title">${ nextNote.title }</span>
                </div>
                <div class="nav-icon">
                  <i class="fas fa-arrow-right"></i>
                </div>
              </a>

              <div v-else class="chapter-link next disabled glass-card">
                <div class="chapter-info">
                  <span class="chapter-label">下一篇</span>
                  <span class="chapter-title">没有更多文章了</span>
                </div>
                <div class="nav-icon">
                  <i class="fas fa-arrow-right"></i>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      <!-- 错误状态 -->
      <div v-else class="error-container">
        <div class="error-message glass-card">
          <i class="fas fa-exclamation-triangle error-icon"></i>
          <h2>${ errorMessage || '无法加载笔记数据' }</h2>
          <p>请检查链接是否正确，或稍后重试</p>
          <a href="/knowledge/" class="back-to-home-btn modern-btn-primary">
            返回首页
          </a>
    </div>

    <!-- 使用 BaseNotification 组件 -->
    <BaseNotification ref="notificationRef" />
  </div>
</template>

<script>
import NoteShadowViewer from './NoteShadowViewer/index.vue'
import BaseNotification from './common/BaseNotification.vue'

export default {
  name: 'PublicNoteView',
  components: {
    NoteShadowViewer,
    BaseNotification
  },
  data() {
    return {
      note: null,
      errorMessage: null,
      fullContent: '',
      isLiking: false,
      isAuthenticated: false,
      readingTime: 0,
      previousNote: null,
      nextNote: null
    }
  },
  mounted() {
    this.initializeData();
    this.setupScrollListener();
  },
  methods: {
    initializeData() {
      // 从全局数据获取信息
      if (window.GLOBAL_DATA) {
        this.note = window.GLOBAL_DATA.noteData;
        this.isAuthenticated = window.GLOBAL_DATA.isAuthenticated;

        if (window.GLOBAL_DATA.navigationData) {
          const navData = window.GLOBAL_DATA.navigationData;
          this.previousNote = navData.previous_note;
          this.nextNote = navData.next_note;
        }

        if (this.note && this.note.content) {
          this.fullContent = this.note.content;
          // 计算阅读时间（假设300字符/分钟）
          this.readingTime = Math.ceil(this.fullContent.length / 300);
        }
      } else {
        this.errorMessage = '无法获取页面数据';
      }
    },

    async toggleLike() {
      if (!this.isAuthenticated) {
        // 跳转到登录页面
        window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname);
        return;
      }

      if (this.isLiking) return;

      this.isLiking = true;

      try {
        const response = await fetch('/api/toggle-note-like/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCookie('csrftoken')
          },
          body: JSON.stringify({
            note_id: this.note.id
          })
        });

        const data = await response.json();

        if (data.status === 'success') {
          this.note.user_has_liked = data.user_has_liked;
          this.note.likes = data.total_likes;

          const message = data.action === 'liked' ? '点赞成功！' : '已取消点赞';
          this.showNotification(true, message);
        } else {
          this.showNotification(false, data.message || '操作失败');
        }
      } catch (error) {
        console.error('点赞失败:', error);
        this.showNotification(false, '网络错误，请稍后重试');
      } finally {
        this.isLiking = false;
      }
    },

    getCookie(name) {
      let cookieValue = null;
      if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
          const cookie = cookies[i].trim();
          if (cookie.substring(0, name.length + 1) === (name + '=')) {
            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            break;
          }
        }
      }
      return cookieValue;
    },

    showNotification(success, message) {
      // 使用 BaseNotification 组件
      if (this.$refs.notificationRef) {
        if (success) {
          this.$refs.notificationRef.success(message);
        } else {
          this.$refs.notificationRef.error(message);
        }
      }
    },

    toggleTheme() {
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
      const newTheme = currentTheme === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('theme', newTheme);
    },

    adjustFontSize() {
      const articleContent = document.querySelector('.article-content');
      if (!articleContent) return;

      const sizes = ['font-size-small', 'font-size-medium', 'font-size-large'];
      let currentIndex = sizes.findIndex(size => articleContent.classList.contains(size));
      if (currentIndex === -1) currentIndex = 1; // 默认 medium

      articleContent.classList.remove(sizes[currentIndex]);
      currentIndex = (currentIndex + 1) % sizes.length;
      articleContent.classList.add(sizes[currentIndex]);
    },

    toggleToc() {
      // 目录功能的简单实现
      const toc = document.querySelector('.table-of-contents');
      if (toc) {
        toc.style.display = toc.style.display === 'none' ? 'block' : 'none';
      }
    },

    shareArticle() {
      const url = window.location.href;
      const title = this.note.title;

      if (navigator.share) {
        navigator.share({ title, url }).catch(() => this.copyToClipboard(url));
      } else {
        this.copyToClipboard(url);
      }
    },

    copyToClipboard(text) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          this.showNotification(true, '链接已复制到剪贴板');
        });
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        this.showNotification(true, '链接已复制到剪贴板');
      }
    },

    setupScrollListener() {
      // 设置阅读进度条
      const progressBar = document.getElementById('reading-progress-bar');
      if (progressBar) {
        window.addEventListener('scroll', () => {
          const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
          const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
          const progress = (scrollTop / scrollHeight) * 100;
          progressBar.style.width = progress + '%';
        });
      }
    }
  }
}
</script>

<style scoped>
[v-cloak] {
  display: none;
}

.error-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  padding: var(--spacing-8);
}

.error-message {
  text-align: center;
  max-width: 500px;
}

.error-icon {
  font-size: 4rem;
  color: var(--error-color);
  margin-bottom: var(--spacing-6);
}

.error-message h2 {
  color: var(--text-primary);
  margin-bottom: var(--spacing-4);
}

.error-message p {
  color: var(--text-secondary);
  margin-bottom: var(--spacing-6);
}

.back-to-home-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
}
</style>