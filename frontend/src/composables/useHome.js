import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

export function useHome() {
  // 状态
  const loading = ref(false)
  const searchQuery = ref('')
  const articles = ref([])
  const currentPage = ref(1)
  const itemsPerPage = 12 // 每页最多12个笔记（4列x3行）

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

  return {
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
  }
}
