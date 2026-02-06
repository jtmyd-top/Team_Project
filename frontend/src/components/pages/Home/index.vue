<template>
  <div class="homepage-wrapper">
    <!-- 顶部标题区域 -->
    <div class="hero-section">
        <h1 class="hero-title">探索知识宇宙</h1>
        <p class="hero-subtitle">探索知识阅读、开拓、共享和撰写知识宇宙</p>

        <!-- 搜索框 -->
        <div class="search-container">
          <el-input
            v-model="searchQuery"
            placeholder="搜索..."
            size="large"
            class="search-input"
            @keyup.enter="handleSearch"
          >
            <template #suffix>
              <el-button
                type="primary"
                @click="handleSearch"
                class="search-button"
              >
                搜索
              </el-button>
            </template>
          </el-input>
        </div>
      </div>

      <!-- 文章卡片网格 -->
      <div v-loading="loading" class="articles-grid" :style="{ gridTemplateColumns: `repeat(${gridColumns}, 1fr)` }">
        <div
          v-for="article in paginatedArticles"
          :key="article.id"
          class="article-card"
          @click="navigateToArticle(article)"
        >
          <!-- 作者信息 -->
          <div class="article-author">
            <img
              :src="article.author_avatar || '/static/img/default-avatar.png'"
              :alt="article.author"
              class="author-avatar"
              @error="handleImageError"
            />
            <span class="author-name">{{ article.author }}</span>
            <span class="publish-date">{{ article.created_at }}</span>
          </div>

          <!-- 文章标题 -->
          <h3 class="article-title">{{ article.title }}</h3>

          <!-- 文章摘要 -->
          <p class="article-summary">{{ article.summary }}</p>

          <!-- 标签 -->
          <div class="article-tags">
            <span
              v-for="tag in article.tags.slice(0, 3)"
              :key="tag"
              class="tag"
            >
              {{ tag }}
            </span>
          </div>

          <!-- 阅读全文链接 -->
          <a
            :href="article.public_url"
            class="read-more"
            @click.stop
          >
            阅读全文 <i class="fas fa-chevron-right"></i>
          </a>
        </div>

        <!-- 空状态 -->
        <div v-if="!loading && articles.length === 0" class="no-articles">
          <i class="fas fa-book-open"></i>
          <p>暂无文章，开始创建你的第一篇知识吧！</p>
        </div>
      </div>

    <!-- 分页器 -->
    <div v-if="totalPages > 1" class="pagination-container">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="itemsPerPage"
        :total="articles.length"
        layout="prev, pager, next"
        @current-change="handlePageChange"
        background
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useHome } from '@/composables/useHome'
import '@/assets/styles/components/home.css'

const {
  loading,
  searchQuery,
  articles,
  currentPage,
  itemsPerPage,
  totalPages,
  paginatedArticles,
  gridColumns,
  handleImageError,
  fetchArticles,
  handleSearch,
  navigateToArticle,
  handlePageChange
} = useHome()

onMounted(() => {
  fetchArticles()
})
</script>

<style scoped>
@import '@/assets/styles/components/home.css';
</style>
