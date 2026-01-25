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
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

// 状态
const loading = ref(false)
const searchQuery = ref('')
const articles = ref([])
const currentPage = ref(1)
const itemsPerPage = 12 // 每页最多12个笔记（4列×3行）

// 计算总页数
const totalPages = computed(() => {
  return Math.ceil(articles.value.length / itemsPerPage)
})

// 当前页的文章
const paginatedArticles = computed(() => {
  const start = (currentPage.value - 1) * itemsPerPage
  const end = start + itemsPerPage
  return articles.value.slice(start, end)
})

// 计算当前页网格列数（如果笔记数量少于2行，则平均分配）
const gridColumns = computed(() => {
  const count = paginatedArticles.value.length
  if (count <= 4) {
    // 少于等于4个，平均分配
    return count
  }
  // 否则使用固定4列
  return 4
})

// 图片加载错误处理
const handleImageError = (event) => {
  event.target.src = '/static/img/default-avatar.png'
}

// 获取文章列表
const fetchArticles = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/public-notes/')
    if (!response.ok) {
      throw new Error('获取文章列表失败')
    }
    const data = await response.json()
    
    // 转换数据格式以匹配模板
    articles.value = data.map(article => ({
      id: article.id,
      title: article.title,
      author: article.author,
      author_avatar: article.author_avatar || '/static/img/default-avatar.png',
      created_at: article.updated_at,
      summary: article.excerpt,
      tags: article.tags || [],
      public_url: article.public_url
    }))
  } catch (error) {
    console.error('获取文章列表失败:', error)
    ElMessage.error('获取文章列表失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

// 搜索处理
const handleSearch = () => {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入搜索关键词')
    return
  }
  // 跳转到搜索页面
  window.location.href = `/search/?q=${encodeURIComponent(searchQuery.value)}`
}

// 跳转到文章详情
const navigateToArticle = (article) => {
  window.location.href = article.public_url
}

// 页码改变处理
const handlePageChange = (page) => {
  currentPage.value = page
  // 滚动到顶部
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// 组件挂载时获取数据
onMounted(() => {
  fetchArticles()
})
</script>

<style scoped>
/* ========== 首页包装器 - 深色渐变背景 ========== */
.homepage-wrapper {
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1f3a 0%, #2d1b4e 50%, #1a1f3a 100%);
  padding-bottom: 60px;
}

/* ========== 顶部标题区域 ========== */
.hero-section {
  position: relative;
  padding: 60px 40px 0 40px;
  max-width: 1400px;
  margin: 0 auto;
  text-align: center;
  margin-bottom: 60px;
  animation: fadeInDown 0.8s ease-out;
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.hero-title {
  font-size: 3rem;
  font-weight: 700;
  margin: 0 0 15px 0;
  background: linear-gradient(135deg, #4fc3f7, #ab47bc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-shadow: none;
}

.hero-subtitle {
  font-size: 1.1rem;
  color: rgba(255, 255, 255, 0.7);
  margin: 0 0 40px 0;
  font-weight: 400;
}

/* ========== 搜索框 ========== */
.search-container {
  max-width: 600px;
  margin: 0 auto;
}

.search-input :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 50px;
  padding: 8px 16px;
  box-shadow: none;
}

.search-input :deep(.el-input__inner) {
  color: #ffffff;
  font-size: 1rem;
  background: transparent;
}

.search-input :deep(.el-input__inner)::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

.search-button {
  padding: 12px 32px;
  background: linear-gradient(135deg, #4fc3f7, #ab47bc);
  border: none;
  border-radius: 50px;
  color: #ffffff;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.search-button:hover {
  transform: scale(1.05);
  box-shadow: 0 8px 24px rgba(79, 195, 247, 0.4);
}

/* ========== 文章卡片网格 ========== */
.articles-grid {
  display: grid;
  gap: 24px;
  animation: fadeInUp 0.8s ease-out 0.2s backwards;
  min-height: 900px;
  padding: 0 40px;
  max-width: 1400px;
  margin: 0 auto;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ========== 文章卡片样式 ========== */
.article-card {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 24px;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  height: 420px;
  cursor: pointer;
}

.article-card:hover {
  transform: translateY(-8px);
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(79, 195, 247, 0.3);
  box-shadow: 0 12px 40px rgba(79, 195, 247, 0.2);
}

/* 作者信息 */
.article-author {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  font-size: 0.85rem;
  flex-shrink: 0;
}

.author-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.2);
  object-fit: cover;
  flex-shrink: 0;
  background: linear-gradient(135deg, #4fc3f7, #ab47bc);
  display: block;
}

.author-name {
  color: rgba(255, 255, 255, 0.9);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.publish-date {
  color: rgba(255, 255, 255, 0.5);
  margin-left: auto;
  font-size: 0.8rem;
}

/* 文章标题 */
.article-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 12px 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  height: 3.5rem;
  flex-shrink: 0;
}

/* 文章摘要 */
.article-summary {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9rem;
  line-height: 1.6;
  margin: 0 0 16px 0;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  height: 6.4rem;
  flex-shrink: 0;
}

/* 标签 */
.article-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  height: 32px;
  overflow: hidden;
  flex-shrink: 0;
}

.tag {
  padding: 6px 14px;
  background: rgba(79, 195, 247, 0.15);
  border: 1px solid rgba(79, 195, 247, 0.3);
  border-radius: 20px;
  font-size: 0.8rem;
  color: #4fc3f7;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
}

/* 阅读全文链接 */
.read-more {
  color: #4fc3f7;
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: all 0.3s ease;
  margin-top: auto;
  flex-shrink: 0;
}

.read-more:hover {
  color: #ab47bc;
  transform: translateX(4px);
}

.read-more i {
  font-size: 0.75rem;
  transition: transform 0.3s ease;
}

.read-more:hover i {
  transform: translateX(4px);
}

/* ========== 空状态 ========== */
.no-articles {
  grid-column: 1 / -1;
  text-align: center;
  padding: 80px 20px;
  color: rgba(255, 255, 255, 0.5);
}

.no-articles i {
  font-size: 4rem;
  margin-bottom: 20px;
  opacity: 0.3;
}

.no-articles p {
  font-size: 1.1rem;
  margin: 0;
}

/* ========== 分页器 ========== */
.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 60px;
  padding: 0 40px 60px 40px;
  max-width: 1400px;
  margin-left: auto;
  margin-right: auto;
  animation: fadeInUp 0.8s ease-out 0.4s backwards;
}

.pagination-container :deep(.el-pagination) {
  --el-pagination-bg-color: rgba(255, 255, 255, 0.05);
  --el-pagination-hover-color: #4fc3f7;
}

.pagination-container :deep(.el-pager li) {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.7);
  margin: 0 4px;
  border-radius: 8px;
  min-width: 36px;
  height: 36px;
  line-height: 36px;
  transition: all 0.3s ease;
}

.pagination-container :deep(.el-pager li:hover) {
  background: rgba(79, 195, 247, 0.2);
  border-color: rgba(79, 195, 247, 0.4);
  color: #4fc3f7;
  transform: translateY(-2px);
}

.pagination-container :deep(.el-pager li.is-active) {
  background: linear-gradient(135deg, #4fc3f7, #ab47bc);
  border-color: transparent;
  color: #ffffff;
  font-weight: 600;
}

.pagination-container :deep(.btn-prev),
.pagination-container :deep(.btn-next) {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.7);
  border-radius: 8px;
  min-width: 36px;
  height: 36px;
  transition: all 0.3s ease;
}

.pagination-container :deep(.btn-prev:not(:disabled):hover),
.pagination-container :deep(.btn-next:not(:disabled):hover) {
  background: rgba(79, 195, 247, 0.2);
  border-color: rgba(79, 195, 247, 0.4);
  color: #4fc3f7;
  transform: translateY(-2px);
}

.pagination-container :deep(.btn-prev:disabled),
.pagination-container :deep(.btn-next:disabled) {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ========== 响应式设计 ========== */
@media (max-width: 1400px) {
  .articles-grid {
    min-height: 850px;
  }
}

@media (max-width: 1024px) {
  .hero-title {
    font-size: 2.5rem;
  }
  
  .articles-grid {
    min-height: 800px;
  }
}

@media (max-width: 768px) {
  .hero-section {
    padding: 40px 20px 0 20px;
  }
  
  .articles-grid {
    padding: 0 20px;
  }
  
  .pagination-container {
    padding: 0 20px 40px 20px;
  }
  
  .hero-title {
    font-size: 2rem;
  }
  
  .hero-subtitle {
    font-size: 1rem;
  }
  
  .articles-grid {
    min-height: auto;
  }
  
  .pagination-container {
    margin-top: 40px;
  }
}
</style>
