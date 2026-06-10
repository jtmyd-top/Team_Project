<template>
  <div class="home-container">
    <!-- 主内容区域 -->
    <main class="main-content">
      <div class="content-grid">
        <!-- 左侧边栏 -->
        <aside class="left-sidebar">
          <!-- 导航菜单 -->
          <div class="nav-card">
            <nav class="nav-menu" aria-label="主页导航">
              <div
                v-for="group in navGroups"
                :key="group.label"
                class="nav-group"
              >
                <div class="nav-group-label">{{ group.label }}</div>
                <a
                  v-for="nav in group.items"
                  :key="nav.id"
                  class="nav-item"
                  :class="{ active: activeNav === nav.id }"
                  @click="setActiveNav(nav.id)"
                >
                  <i class="home-fa-icon" :class="getIconClass(nav.icon)" aria-hidden="true"></i>
                  {{ nav.label }}
                </a>
              </div>
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
                    <i class="home-fa-icon" :class="getIconClass(topic.icon)" aria-hidden="true"></i>
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
            <i class="home-fa-icon content-search-icon" :class="getIconClass('search')" aria-hidden="true"></i>
            <input
              v-model="searchQuery"
              type="text"
              class="content-search-input"
              placeholder="搜索笔记标题、作者或标签..."
              @input="handleSearch"
            />
            <button v-if="searchQuery" class="search-clear-btn" @click="clearSearch">
              <i class="home-fa-icon" :class="getIconClass('close')" aria-hidden="true"></i>
            </button>
          </div>

          <!-- 搜索结果提示 -->
          <div v-if="isSearching" class="search-result-bar">
            <span class="search-result-text">
              <strong>{{ searchResultLabel }}</strong>，共 {{ articles.length }} 篇笔记
            </span>
            <button class="search-result-clear" @click="clearSearch">清除搜索</button>
          </div>

          <div class="feed-controls">
            <div class="feed-heading">
              <div>
                <p class="feed-kicker">{{ activeNavLabel }}</p>
                <h2 class="feed-title">知识笔记</h2>
              </div>
              <span class="feed-count">{{ articles.length }} 篇</span>
            </div>

            <div class="content-type-tabs" aria-label="内容类型">
              <button
                v-for="type in contentTypeTabs"
                :key="type.id"
                class="content-type-tab"
                :class="{ active: activeContentType === type.id }"
                @click="setContentType(type.id)"
              >
                <i class="home-fa-icon" :class="getIconClass(type.icon)" aria-hidden="true"></i>
                <span>{{ type.label }}</span>
                <span class="type-count">{{ type.count }}</span>
              </button>
            </div>

            <div class="sort-chips" aria-label="排序方式">
              <button
                v-for="option in sortOptions"
                :key="option.id"
                class="sort-chip"
                :class="{ active: activeSort === option.id }"
                @click="setSort(option.id)"
              >
                <i class="home-fa-icon" :class="getIconClass(option.icon)" aria-hidden="true"></i>
                {{ option.label }}
              </button>
            </div>
          </div>

          <!-- 加载状态 -->
          <div v-if="loading" class="loading-wrapper" aria-live="polite" aria-label="正在加载">
            <span class="home-loading-spinner" aria-hidden="true"></span>
          </div>

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
                      class="article-badge type-badge"
                      :class="article.type"
                    >
                      {{ article.typeLabel }}
                    </span>
                    <span
                      v-if="article.badge"
                      class="article-badge tag-badge"
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
                      <i class="home-fa-icon" :class="getIconClass(article.user_has_liked ? 'favorite' : 'favorite_border')" aria-hidden="true"></i>
                      <span>{{ article.likes || 0 }}</span>
                    </button>
                    <button class="action-btn comment" @click.stop="navigateToArticle(article)">
                      <i class="home-fa-icon" :class="getIconClass('chat_bubble_outline')" aria-hidden="true"></i>
                      <span>{{ article.comments || 0 }}</span>
                    </button>
                    <button class="action-btn view" @click.stop>
                      <i class="home-fa-icon" :class="getIconClass('visibility')" aria-hidden="true"></i>
                      <span>{{ article.views || 0 }}</span>
                    </button>
                    <button class="action-btn share" @click.stop>
                      <i class="home-fa-icon" :class="getIconClass('share')" aria-hidden="true"></i>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 空状态 -->
            <div v-if="articles.length === 0" class="empty-state">
              <i class="home-fa-icon" :class="getIconClass('auto_stories')" aria-hidden="true"></i>
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
                <i class="home-fa-icon" :class="getIconClass('analytics')" aria-hidden="true"></i>
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

          <!-- 快捷操作 -->
          <div class="quick-actions-card">
            <h3 class="card-title">快捷操作</h3>
            <div class="quick-actions-list">
              <button class="quick-action" @click="navigateToNewNote">
                <i class="home-fa-icon" :class="getIconClass('edit_note')" aria-hidden="true"></i>
                <span>发布笔记</span>
              </button>
              <button class="quick-action" @click="setActiveNav('hot')">
                <i class="home-fa-icon" :class="getIconClass('local_fire_department')" aria-hidden="true"></i>
                <span>热门内容</span>
              </button>
              <button class="quick-action" @click="setSort('comments')">
                <i class="home-fa-icon" :class="getIconClass('forum')" aria-hidden="true"></i>
                <span>讨论最多</span>
              </button>
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
      <i class="home-fa-icon" :class="getIconClass('add')" aria-hidden="true"></i>
    </button>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import { useHome } from '@/composables/useHome'
import '@/assets/styles/components/home.css'

const {
  loading,
  searchQuery,
  isSearching,
  articles,
  paginatedArticles,
  hasMore,
  activeNav,
  activeNavLabel,
  searchResultLabel,
  navGroups,
  activeContentType,
  activeSort,
  contentTypeTabs,
  sortOptions,
  hotTopics,
  communityStats,
  activeContributors,
  getIconClass,
  handleImageError,
  fetchArticles,
  fetchHomeStats,
  handleSearch,
  clearSearch,
  setContentType,
  setSort,
  navigateToArticle,
  navigateToNewNote,
  setActiveNav,
  loadMore,
  formatTimeAgo,
  toggleLike
} = useHome()

onMounted(() => {
  document.documentElement.classList.add('home-scroll-shell')
  document.body.classList.add('home-scroll-shell')
  fetchArticles()
  fetchHomeStats()
})

onBeforeUnmount(() => {
  document.documentElement.classList.remove('home-scroll-shell')
  document.body.classList.remove('home-scroll-shell')
})
</script>

<style scoped>
@import '@/assets/styles/components/home.css';
</style>
