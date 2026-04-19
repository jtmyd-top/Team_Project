<template>
  <div class="home-container">
    <!-- 主内容区域 -->
    <main class="main-content">
      <div class="content-grid">
        <!-- 左侧边栏 -->
        <aside class="left-sidebar">
          <!-- 导航菜单 -->
          <div class="nav-card">
            <nav class="nav-menu">
              <a
                v-for="nav in navItems"
                :key="nav.id"
                class="nav-item"
                :class="{ active: activeNav === nav.id }"
                @click="setActiveNav(nav.id)"
              >
                <span class="material-icons-outlined">{{ nav.icon }}</span>
                {{ nav.label }}
              </a>
            </nav>
          </div>

          <!-- 热门话题 (仅在有数据时显示) -->
          <div v-if="hotTopics.length > 0" class="topics-card">
            <h3 class="card-title">热门话题</h3>
            <div class="topic-list">
              <div
                v-for="topic in hotTopics"
                :key="topic.id"
                class="topic-item"
              >
                <div class="topic-info">
                  <span class="topic-icon" :class="topic.color">
                    <span class="material-icons-outlined">{{ topic.icon }}</span>
                  </span>
                  <span class="topic-name">{{ topic.name }}</span>
                </div>
                <span class="topic-count">{{ topic.count }}</span>
              </div>
            </div>
          </div>
        </aside>

        <!-- 中间内容区 -->
        <section class="center-content">

          <!-- 搜索框 -->
          <div class="content-search-bar">
            <span class="material-icons-outlined content-search-icon">search</span>
            <input
              v-model="searchQuery"
              type="text"
              class="content-search-input"
              placeholder="搜索笔记标题、作者或标签..."
              @input="handleSearch"
            />
            <button v-if="searchQuery" class="search-clear-btn" @click="clearSearch">
              <span class="material-icons-outlined">close</span>
            </button>
          </div>

          <!-- 搜索结果提示 -->
          <div v-if="isSearching" class="search-result-bar">
            <span class="search-result-text">
              搜索 "<strong>{{ searchQuery }}</strong>" 找到 {{ articles.length }} 篇笔记
            </span>
            <button class="search-result-clear" @click="clearSearch">清除搜索</button>
          </div>

          <!-- 加载状态 -->
          <div v-if="loading" class="loading-wrapper" v-loading="loading"></div>

          <!-- 文章列表 -->
          <template v-else>
            <div
              v-for="article in paginatedArticles"
              :key="article.id"
              class="article-card"
              @click="navigateToArticle(article)"
            >
              <div class="article-inner">
                <img
                  :src="article.author_avatar"
                  :alt="article.author"
                  class="article-avatar"
                  @error="handleImageError"
                />
                <div class="article-content">
                  <div class="article-header">
                    <div class="author-info">
                      <span class="author-name">{{ article.author }}</span>
                      <span class="publish-time">• {{ formatTimeAgo(article.created_at) }}</span>
                    </div>
                    <span
                      v-if="article.badge"
                      class="article-badge"
                      :class="article.badgeColor || 'purple'"
                    >
                      {{ article.badge }}
                    </span>
                  </div>
                  <h3 class="article-title">{{ article.title }}</h3>
                  <p class="article-summary">{{ article.summary }}</p>
                  <div class="article-tags">
                    <span
                      v-for="tag in article.tags.slice(0, 3)"
                      :key="tag"
                      class="article-tag"
                    >
                      #{{ tag }}
                    </span>
                  </div>
                  <div class="article-actions">
                    <button
                      class="action-btn like"
                      :class="{ liked: article.user_has_liked }"
                      @click.stop="toggleLike(article)"
                    >
                      <span class="material-icons-outlined">{{ article.user_has_liked ? 'favorite' : 'favorite_border' }}</span>
                      <span>{{ article.likes || 0 }}</span>
                    </button>
                    <button class="action-btn comment" @click.stop="navigateToArticle(article)">
                      <span class="material-icons-outlined">chat_bubble_outline</span>
                      <span>{{ article.comments || 0 }}</span>
                    </button>
                    <button class="action-btn view" @click.stop>
                      <span class="material-icons-outlined">visibility</span>
                      <span>{{ article.views || 0 }}</span>
                    </button>
                    <button class="action-btn share" @click.stop>
                      <span class="material-icons-outlined">share</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 空状态 -->
            <div v-if="articles.length === 0" class="empty-state">
              <span class="material-icons-outlined">auto_stories</span>
              <p>暂无文章，开始创建你的第一篇知识吧！</p>
            </div>

            <!-- 加载更多 -->
            <div v-if="hasMore" class="load-more-section">
              <button class="load-more-btn" @click="loadMore">
                加载更多内容...
              </button>
            </div>
          </template>
        </section>

        <!-- 右侧边栏 -->
        <aside class="right-sidebar">
          <!-- 社区动态 -->
          <div class="stats-card">
            <div class="stats-header">
              <h3 class="stats-title">
                <span class="material-icons-outlined">analytics</span>
                社区动态
              </h3>
              <div class="stats-grid">
                <div class="stat-item">
                  <div class="stat-value">{{ communityStats.totalNotes }}</div>
                  <div class="stat-label">知识笔记</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value">{{ communityStats.onlineUsers }}</div>
                  <div class="stat-label">在线用户</div>
                </div>
              </div>
              <div class="stats-today">
                <span class="stats-today-label">今日新增</span>
                <span class="stats-today-value">+{{ communityStats.todayNew }} 篇</span>
              </div>
            </div>
          </div>

          <!-- 活跃贡献者 -->
          <div class="contributors-card">
            <div class="contributors-header">
              <h3 class="card-title">活跃贡献者</h3>
              <button class="view-all-btn">查看全部</button>
            </div>
            <ul class="contributors-list">
              <li
                v-for="contributor in activeContributors"
                :key="contributor.id"
                class="contributor-item"
              >
                <div class="contributor-avatar-wrapper">
                  <img
                    :src="contributor.avatar"
                    :alt="contributor.name"
                    class="contributor-avatar"
                    @error="handleImageError"
                  />
                  <span
                    class="online-indicator"
                    :class="contributor.online ? 'online' : 'offline'"
                  ></span>
                </div>
                <div class="contributor-info">
                  <p class="contributor-name">{{ contributor.name }}</p>
                  <p class="contributor-activity">{{ contributor.activity }}</p>
                </div>
              </li>
            </ul>
          </div>
        </aside>
      </div>
    </main>

    <!-- 页脚 -->
    <footer class="page-footer">
      <div class="footer-links">
        <a href="#" class="footer-link">关于我们</a>
        <a href="#" class="footer-link">隐私政策</a>
        <a href="#" class="footer-link">帮助中心</a>
        <span class="footer-link footer-copyright">© 2026 Knowledge Verse</span>
      </div>
    </footer>

    <!-- 移动端浮动按钮 -->
    <button class="fab-button" @click="navigateToNewNote">
      <span class="material-icons-outlined">add</span>
    </button>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useHome } from '@/composables/useHome'
import '@/assets/styles/components/home.css'

const {
  loading,
  searchQuery,
  isSearching,
  isAuthenticated,
  articles,
  paginatedArticles,
  hasMore,
  activeNav,
  navItems,
  hotTopics,
  communityStats,
  activeContributors,
  userAvatar,
  handleImageError,
  handleAvatarError,
  fetchArticles,
  fetchHomeStats,
  handleSearch,
  clearSearch,
  navigateToArticle,
  navigateToNewNote,
  navigateToLogin,
  navigateToSignup,
  setActiveNav,
  loadMore,
  formatTimeAgo,
  toggleLike
} = useHome()

onMounted(() => {
  fetchArticles()
  fetchHomeStats()
})
</script>

<style scoped>
@import '@/assets/styles/components/home.css';
</style>
