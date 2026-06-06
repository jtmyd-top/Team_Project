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
              <a href="/knowledge/" class="back-button hover-glow" @click.prevent="goBack">
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
              <div
                class="meta-item author-info hover-lift cursor-pointer"
                @click="showAuthorModal = true">
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

              <div class="meta-divider"></div>

              <!-- 私信按钮 -->
              <div class="meta-item">
                <button
                  v-if="isAuthenticated && note.author.id !== currentUserId"
                  class="message-button"
                  @click="showAuthorModal = true"
                  title="发送私信"
                >
                  <i class="fas fa-envelope"></i>
                  <span>私信</span>
                </button>
              </div>

              <!-- 关注按钮 -->
              <div class="meta-item" v-if="isAuthenticated && note.author.id !== currentUserId">
                <button
                  class="follow-button"
                  :class="{ 'is-following': isFollowing }"
                  :disabled="followLoading"
                  @click="toggleFollow"
                  :title="isFollowing ? '取消关注' : '关注此作者'"
                >
                  <i :class="isFollowing ? 'fas fa-user-check' : 'fas fa-user-plus'"></i>
                  <span>${ isFollowing ? '已关注' : '关注' }</span>
                  <span v-if="followersCount > 0" class="follow-count">${ followersCount }</span>
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
          <a href="/knowledge/" class="back-to-home-btn modern-btn-primary" @click.prevent="goBack">
            返回首页
          </a>
        </div>
    </div>

    <!-- 使用 BaseNotification 组件 -->
    <BaseNotification ref="notificationRef" />

    <!-- 用户卡片弹窗 -->
    <UserCardModal
      :isVisible="showAuthorModal"
      :userId="note?.author?.id"
      :currentUserId="currentUserId"
      @close="showAuthorModal = false"
      @message-sent="handleMessageSent"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import NoteShadowViewer from '@components/knowledge/NoteShadowViewer/index.vue'
import BaseNotification from '@components/common/BaseNotification/index.vue'
import UserCardModal from '@components/common/UserCardModal/index.vue'
import { usePublicNoteView } from '@composables/usePublicNoteView'
import { getCsrfToken } from '@utils/csrf'
import '@/assets/styles/components/public-note-view.css'

const notificationRef = ref(null)
const showAuthorModal = ref(false)
const currentUserId = ref(null)
const isAuthenticated = ref(false)

// 关注状态
const isFollowing = ref(false)
const followersCount = ref(0)
const followLoading = ref(false)

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

// 从DOM获取当前用户ID和认证状态
const getCurrentUserId = () => {
  const userIdMeta = document.querySelector('meta[name="user-id"]')
  if (userIdMeta && userIdMeta.content) {
    // 用户已登录
    isAuthenticated.value = true
    const userId = parseInt(userIdMeta.content)
    return userId > 0 ? userId : null
  }
  isAuthenticated.value = false
  return null
}

// 返回上一页，无历史则回首页
const goBack = () => {
  if (window.history.length > 1) {
    window.history.back()
  } else {
    window.location.href = '/knowledge/'
  }
}

// 消息发送回调
const handleMessageSent = () => {
  notificationRef.value?.showSuccess('私信已发送')
}

// 关注状态 / 切换
const loadFollowStatus = async () => {
  if (!note.value?.author?.id) return
  try {
    const r = await fetch(`/api/users/${note.value.author.id}/follow-status/`)
    if (r.ok) {
      const d = await r.json()
      isFollowing.value = !!d.is_following
      followersCount.value = d.followers_count || 0
    }
  } catch (e) {
    console.error('加载关注状态失败:', e)
  }
}

const toggleFollow = async () => {
  if (!isAuthenticated.value || !note.value?.author?.id) return
  if (followLoading.value) return
  followLoading.value = true
  const endpoint = isFollowing.value ? '/api/users/unfollow/' : '/api/users/follow/'
  try {
    const r = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ user_id: note.value.author.id }),
    })
    const d = await r.json()
    if (r.ok && d.status === 'success') {
      isFollowing.value = !!d.is_following
      followersCount.value = d.followers_count ?? followersCount.value
      notificationRef.value?.showSuccess(isFollowing.value ? '关注成功' : '已取消关注')
    } else {
      notificationRef.value?.showError(d.message || d.error || '操作失败')
    }
  } catch (e) {
    notificationRef.value?.showError('网络错误，请稍后重试')
  } finally {
    followLoading.value = false
  }
}

onMounted(() => {
  currentUserId.value = getCurrentUserId()
  initializeData()
  setupScrollListener()
})

// 笔记加载完成后再拉关注状态
watch(
  () => note.value?.author?.id,
  (authorId) => {
    if (authorId && isAuthenticated.value && authorId !== currentUserId.value) {
      loadFollowStatus()
    }
  }
)
</script>

<style scoped>
@import '@/assets/styles/components/public-note-view.css';

/* 私信按钮样式 */
.message-button {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: none;
  border: none;
  cursor: pointer;
  color: #409eff;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.message-button:hover {
  transform: translateY(-2px);
  color: #66b1ff;
}

.message-button i {
  font-size: 16px;
}

/* 关注按钮样式 */
.follow-button {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  background: none;
  border: 1px solid #67c23a;
  border-radius: 8px;
  color: #67c23a;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.follow-button:hover:not(:disabled) {
  transform: translateY(-2px);
  background: rgba(103, 194, 58, 0.08);
}

.follow-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.follow-button.is-following {
  background: #67c23a;
  color: #fff;
}

.follow-button.is-following:hover:not(:disabled) {
  background: #f56c6c;
  border-color: #f56c6c;
}

.follow-button i {
  font-size: 16px;
}

.follow-count {
  font-size: 10px;
  opacity: 0.85;
}
</style>
