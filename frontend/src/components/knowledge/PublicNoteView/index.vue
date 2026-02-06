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
    </div>

    <!-- 使用 BaseNotification 组件 -->
    <BaseNotification ref="notificationRef" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import NoteShadowViewer from '@components/knowledge/NoteShadowViewer/index.vue'
import BaseNotification from '@components/common/BaseNotification/index.vue'
import { usePublicNoteView } from '@composables/usePublicNoteView'
import '@/assets/styles/components/public-note-view.css'

const notificationRef = ref(null)

const {
  note,
  errorMessage,
  fullContent,
  isLiking,
  readingTime,
  previousNote,
  nextNote,
  initializeData,
  toggleLike,
  toggleTheme,
  adjustFontSize,
  toggleToc,
  shareArticle,
  setupScrollListener
} = usePublicNoteView(notificationRef)

onMounted(() => {
  initializeData()
  setupScrollListener()
})
</script>

<style scoped>
@import '@/assets/styles/components/public-note-view.css';
</style>
