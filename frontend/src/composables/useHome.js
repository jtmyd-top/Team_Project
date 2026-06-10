import { ref, computed } from 'vue'
import { getCsrfToken } from '@utils/csrf'
import { formatDateOnly } from '@utils/datetime'
import { extractApiErrorMessage } from '@utils/apiError'

// 从模板注入的全局数据中读取登录状态
const homeData = window.__HOME_DATA__ || {}
const isAuthenticated = ref(homeData.isAuthenticated || false)
const loginUrl = homeData.loginUrl || '/login/'
const signupUrl = homeData.signupUrl || '/signup/'
const initialAuthorFilter = new URLSearchParams(window.location.search).get('author') || ''
const initialAuthorNameFilter = new URLSearchParams(window.location.search).get('author_name') || ''

const iconClassMap = {
  add: 'fa-solid fa-plus',
  analytics: 'fa-solid fa-chart-line',
  apps: 'fa-solid fa-grip',
  auto_stories: 'fa-solid fa-book-open',
  bookmarks: 'fa-solid fa-bookmark',
  build_circle: 'fa-solid fa-screwdriver-wrench',
  chat_bubble_outline: 'fa-regular fa-comment-dots',
  close: 'fa-solid fa-xmark',
  description: 'fa-regular fa-file-lines',
  edit_note: 'fa-regular fa-pen-to-square',
  explore: 'fa-regular fa-compass',
  extension: 'fa-solid fa-puzzle-piece',
  favorite: 'fa-solid fa-heart',
  favorite_border: 'fa-regular fa-heart',
  forum: 'fa-regular fa-comments',
  history: 'fa-solid fa-clock-rotate-left',
  local_fire_department: 'fa-solid fa-fire',
  school: 'fa-solid fa-graduation-cap',
  schedule: 'fa-regular fa-clock',
  search: 'fa-solid fa-magnifying-glass',
  share: 'fa-solid fa-share-nodes',
  tips_and_updates: 'fa-regular fa-lightbulb',
  visibility: 'fa-regular fa-eye',
  whatshot: 'fa-solid fa-fire'
}

const getIconClass = (icon) => iconClassMap[icon] || 'fa-solid fa-circle'

const notify = (type, message) => {
  if (!message || typeof document === 'undefined') return

  const rootId = 'home-toast-root'
  let root = document.getElementById(rootId)
  if (!root) {
    root = document.createElement('div')
    root.id = rootId
    root.className = 'home-toast-root'
    document.body.appendChild(root)
  }

  const toast = document.createElement('div')
  toast.className = `home-toast home-toast-${type}`
  toast.textContent = message
  root.appendChild(toast)

  window.setTimeout(() => {
    toast.classList.add('is-leaving')
    window.setTimeout(() => toast.remove(), 180)
  }, 2600)
}

export function useHome() {
  // 状态
  const loading = ref(false)
  const searchQuery = ref('')
  const allArticles = ref([])
  const currentPage = ref(1)
  const itemsPerPage = 10
  const activeNav = ref('explore')
  const isSearching = ref(!!initialAuthorFilter)
  const activeContentType = ref('all')
  const activeSort = ref('latest')
  const authorFilter = ref(initialAuthorFilter)
  const authorNameFilter = ref(initialAuthorNameFilter)

  // 收藏和历史相关状态
  const favoriteArticles = ref([])
  const historyArticles = ref([])
  const hotArticles = ref([])

  // 导航菜单配置
  const navGroups = ref([
    {
      label: '发现',
      items: [
        { id: 'explore', icon: 'explore', label: '探索发现' },
        { id: 'hot', icon: 'whatshot', label: '热门讨论' }
      ]
    },
    {
      label: '个人',
      items: [
        { id: 'favorites', icon: 'bookmarks', label: '我的收藏' },
        { id: 'history', icon: 'history', label: '浏览历史' }
      ]
    }
  ])
  const navItems = computed(() => navGroups.value.flatMap(group => group.items))

  const contentTypes = ref([
    { id: 'all', label: '全部', icon: 'apps' },
    { id: 'tutorial', label: '教程', icon: 'school' },
    { id: 'troubleshooting', label: '问题排查', icon: 'build_circle' },
    { id: 'resource', label: '工具资源', icon: 'extension' },
    { id: 'document', label: '项目文档', icon: 'description' },
    { id: 'experience', label: '经验分享', icon: 'tips_and_updates' }
  ])

  const sortOptions = ref([
    { id: 'latest', label: '最新', icon: 'schedule' },
    { id: 'hot', label: '最热', icon: 'local_fire_department' },
    { id: 'comments', label: '最多评论', icon: 'forum' },
    { id: 'likes', label: '最多收藏', icon: 'favorite' }
  ])

  // 热门话题数据 (由后台管理)
  const hotTopics = ref([])

  // 社区统计数据
  const communityStats = ref({
    totalNotes: '-',
    onlineUsers: '-',
    todayNew: 0
  })

  // 活跃贡献者列表
  const activeContributors = ref([])

  // 用户头像
  const userAvatar = ref('/static/img/default-avatar.png')

  const inferArticleType = (article) => {
    const tags = (article.tags || []).map(tag => String(tag).toLowerCase())
    const text = `${article.title || ''} ${article.excerpt || article.summary || ''} ${tags.join(' ')}`.toLowerCase()

    if (/(教程|指南|quick start|使用方法|入门|配置)/i.test(text)) return 'tutorial'
    if (/(失效|修复|报错|问题|bug|排查|认证|ssh|登录)/i.test(text)) return 'troubleshooting'
    if (/(工具|api|客户端|模型|cli|proxy|资源|库)/i.test(text)) return 'resource'
    if (/(文档|项目|说明|规范|注册表|流程)/i.test(text)) return 'document'
    return 'experience'
  }

  const getTypeMeta = (typeId) => {
    return contentTypes.value.find(type => type.id === typeId) || contentTypes.value[0]
  }

  // 根据当前导航、内容类型、排序和搜索词过滤文章
  const articles = computed(() => {
    let sourceArticles = allArticles.value

    // 根据activeNav选择数据源
    if (activeNav.value === 'favorites') {
      sourceArticles = favoriteArticles.value
    } else if (activeNav.value === 'hot') {
      sourceArticles = hotArticles.value
    } else if (activeNav.value === 'history') {
      sourceArticles = historyArticles.value
    }

    let filtered = [...sourceArticles]

    if (activeContentType.value !== 'all') {
      filtered = filtered.filter(a => a.type === activeContentType.value)
    }

    if (authorFilter.value) {
      filtered = filtered.filter(a => String(a.author_id || '') === String(authorFilter.value))
    }

    // 应用搜索过滤
    const q = searchQuery.value.trim().toLowerCase()
    if (q) {
      filtered = filtered.filter(a =>
        a.title.toLowerCase().includes(q) ||
        a.author.toLowerCase().includes(q) ||
        (a.summary && a.summary.toLowerCase().includes(q)) ||
        (a.tags && a.tags.some(t => t.toLowerCase().includes(q)))
      )
    }

    const sorters = {
      latest: (a, b) => new Date(b.created_at) - new Date(a.created_at),
      hot: (a, b) => (b.views || 0) - (a.views || 0),
      comments: (a, b) => (b.comments || 0) - (a.comments || 0),
      likes: (a, b) => (b.likes || 0) - (a.likes || 0)
    }

    return filtered.sort(sorters[activeSort.value] || sorters.latest)
  })

  const contentTypeTabs = computed(() => {
    let sourceArticles = allArticles.value
    if (activeNav.value === 'favorites') {
      sourceArticles = favoriteArticles.value
    } else if (activeNav.value === 'hot') {
      sourceArticles = hotArticles.value
    } else if (activeNav.value === 'history') {
      sourceArticles = historyArticles.value
    }

    return contentTypes.value.map(type => ({
      ...type,
      count: type.id === 'all'
        ? sourceArticles.length
        : sourceArticles.filter(article => article.type === type.id).length
    }))
  })

  const activeNavLabel = computed(() => {
    if (authorFilter.value) return `${authorNameFilter.value || '该用户'}的公开笔记`
    return navItems.value.find(item => item.id === activeNav.value)?.label || '探索发现'
  })

  const searchResultLabel = computed(() => {
    if (authorFilter.value) return `查看 ${authorNameFilter.value || '该用户'} 的公开笔记`
    return `搜索 "${searchQuery.value}"`
  })

  // 计算是否有更多数据
  const hasMore = computed(() => {
    return currentPage.value * itemsPerPage < articles.value.length
  })

  // 当前页的文章
  const paginatedArticles = computed(() => {
    const end = currentPage.value * itemsPerPage
    return articles.value.slice(0, end)
  })

  // 图片加载错误处理
  const handleImageError = (event) => {
    event.target.src = '/static/img/default-avatar.png'
  }

  // 头像加载错误处理
  const handleAvatarError = (event) => {
    event.target.src = '/static/img/default-avatar.png'
  }

  // 时间格式化（x小时前）
  const formatTimeAgo = (dateString) => {
    if (!dateString) return ''

    const date = new Date(dateString)
    const now = new Date()
    const diffInSeconds = Math.floor((now - date) / 1000)

    if (diffInSeconds < 60) {
      return '刚刚'
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60)
      return `${minutes}分钟前`
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600)
      return `${hours}小时前`
    } else if (diffInSeconds < 604800) {
      const days = Math.floor(diffInSeconds / 86400)
      return `${days}天前`
    } else {
      return formatDateOnly(date)
    }
  }

  // 获取文章列表
  const fetchArticles = async () => {
    loading.value = true
    try {
      const response = await fetch('/api/public-notes/')
      const raw = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(extractApiErrorMessage(raw, '获取文章列表失败'))
      }
      const data = Array.isArray(raw) ? raw : (raw.notes || [])

      const badgeColors = ['purple', 'blue', 'green']

      allArticles.value = data.map((article, index) => {
        const type = inferArticleType(article)
        return {
          id: article.id,
          title: article.title,
          author_id: article.author_id,
          author: article.author,
          author_avatar: article.author_avatar || '/static/img/default-avatar.png',
          created_at: article.created_at,
          summary: article.excerpt,
          tags: article.tags || [],
          public_url: article.public_url,
          type,
          typeLabel: getTypeMeta(type).label,
          badge: article.tags && article.tags.length > 0 ? article.tags[0] : null,
          badgeColor: badgeColors[index % badgeColors.length],
          likes: article.likes || 0,
          user_has_liked: article.user_has_liked || false,
          comments: article.comments_count || 0,
          views: article.views || 0,
          is_favorited: article.is_favorited || false
        }
      })

      // 初始化热门文章（按views排序）
      hotArticles.value = [...allArticles.value].sort((a, b) => b.views - a.views)
    } catch (error) {
      console.error('获取文章列表失败:', error)
      notify('error', error.message || '获取文章列表失败，请稍后重试')
    } finally {
      loading.value = false
    }
  }

  // 获取收藏列表
  const fetchFavorites = async () => {
    if (!isAuthenticated.value) {
      notify('warning', '请先登录')
      navigateToLogin()
      return
    }

    loading.value = true
    try {
      const response = await fetch('/api/notes/favorited/')
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(extractApiErrorMessage(data, '获取收藏列表失败'))
      }

      const badgeColors = ['purple', 'blue', 'green']

      favoriteArticles.value = data.map((article, index) => {
        const type = inferArticleType(article)
        return {
          id: article.id,
          title: article.title,
          author_id: article.author_id,
          author: article.author,
          author_avatar: article.author_avatar || '/static/img/default-avatar.png',
          created_at: article.created_at,
          summary: article.excerpt,
          tags: article.tags || [],
          public_url: article.public_url,
          type,
          typeLabel: getTypeMeta(type).label,
          badge: article.tags && article.tags.length > 0 ? article.tags[0] : null,
          badgeColor: badgeColors[index % badgeColors.length],
          likes: article.likes || 0,
          user_has_liked: article.user_has_liked || false,
          comments: article.comments_count || 0,
          views: article.views || 0,
          is_favorited: true
        }
      })
    } catch (error) {
      console.error('获取收藏列表失败:', error)
      notify('error', error.message || '获取收藏列表失败，请稍后重试')
    } finally {
      loading.value = false
    }
  }

  // 获取浏览历史
  const fetchHistory = async () => {
    loading.value = true
    try {
      if (isAuthenticated.value) {
        // 已登录：从服务器获取历史
        const response = await fetch('/api/notes/history/')
        if (response.ok) {
          const data = await response.json()
          const badgeColors = ['purple', 'blue', 'green']

          historyArticles.value = data.map((article, index) => {
            const type = inferArticleType(article)
            return {
              id: article.id,
              title: article.title,
              author_id: article.author_id,
              author: article.author,
              author_avatar: article.author_avatar || '/static/img/default-avatar.png',
              created_at: article.created_at,
              summary: article.excerpt,
              tags: article.tags || [],
              public_url: article.public_url,
              type,
              typeLabel: getTypeMeta(type).label,
              badge: article.tags && article.tags.length > 0 ? article.tags[0] : null,
              badgeColor: badgeColors[index % badgeColors.length],
              likes: article.likes || 0,
              user_has_liked: article.user_has_liked || false,
              comments: article.comments_count || 0,
              views: article.views || 0,
              is_favorited: article.is_favorited || false
            }
          })
        }
      } else {
        // 未登录：从本地存储获取历史
        const localHistory = localStorage.getItem('noteHistory')
        if (localHistory) {
          const historyIds = JSON.parse(localHistory)
          historyArticles.value = allArticles.value.filter(a => historyIds.includes(a.id))
        }
      }
    } catch (error) {
      console.error('获取浏览历史失败:', error)
      // 如果服务器请求失败，尝试从本地存储获取
      const localHistory = localStorage.getItem('noteHistory')
      if (localHistory) {
        const historyIds = JSON.parse(localHistory)
        historyArticles.value = allArticles.value.filter(a => historyIds.includes(a.id))
      }
    } finally {
      loading.value = false
    }
  }

  // 记录浏览历史
  const recordHistory = (articleId) => {
    if (isAuthenticated.value) {
      // 已登录：发送到服务器
      fetch('/api/notes/record-history/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        },
        body: JSON.stringify({ note_id: articleId })
      }).catch(error => console.error('记录浏览历史失败:', error))
    } else {
      // 未登录：保存到本地存储
      let history = localStorage.getItem('noteHistory')
      let historyIds = history ? JSON.parse(history) : []

      // 移除重复项并添加到开头
      historyIds = historyIds.filter(id => id !== articleId)
      historyIds.unshift(articleId)

      // 只保留最近100条
      historyIds = historyIds.slice(0, 100)

      localStorage.setItem('noteHistory', JSON.stringify(historyIds))
    }
  }

  // 获取社区统计和活跃贡献者
  const fetchHomeStats = async () => {
    try {
      const response = await fetch('/api/home-stats/')
      if (!response.ok) return
      const data = await response.json()
      communityStats.value = data.stats
      activeContributors.value = data.contributors
    } catch (error) {
      console.error('获取社区统计失败:', error)
    }
  }

  // 搜索处理（本地过滤，articles 计算属性会自动响应）
  const handleSearch = () => {
    currentPage.value = 1
    isSearching.value = !!searchQuery.value.trim()
  }

  // 清除搜索
  const clearSearch = () => {
    searchQuery.value = ''
    authorFilter.value = ''
    authorNameFilter.value = ''
    isSearching.value = false
    currentPage.value = 1
    const url = new URL(window.location.href)
    url.searchParams.delete('author')
    url.searchParams.delete('author_name')
    window.history.replaceState({}, '', url)
  }

  const setContentType = (typeId) => {
    activeContentType.value = typeId
    currentPage.value = 1
  }

  const setSort = (sortId) => {
    activeSort.value = sortId
    currentPage.value = 1
  }

  // 跳转到文章详情
  const navigateToArticle = (article) => {
    // 记录浏览历史
    recordHistory(article.id)
    window.location.href = article.public_url
  }

  // 跳转到新建笔记
  const navigateToNewNote = () => {
    window.location.href = '/knowledge/?create=1'
  }

  // 跳转到登录页
  const navigateToLogin = () => {
    window.location.href = `${loginUrl}?next=${encodeURIComponent(window.location.pathname)}`
  }

  // 跳转到注册页
  const navigateToSignup = () => {
    window.location.href = signupUrl
  }

  // 设置当前选中的导航
  const setActiveNav = async (navId) => {
    activeNav.value = navId
    currentPage.value = 1
    activeContentType.value = 'all'
    searchQuery.value = ''
    authorFilter.value = ''
    authorNameFilter.value = ''
    isSearching.value = false

    // 根据导航类型加载数据
    if (navId === 'favorites') {
      if (!isAuthenticated.value) {
        notify('warning', '请先登录查看收藏')
        navigateToLogin()
        activeNav.value = 'explore'
        return
      }
      await fetchFavorites()
    } else if (navId === 'history') {
      await fetchHistory()
    } else if (navId === 'hot') {
      // 热门讨论已在fetchArticles中初始化
    }
  }

  // 加载更多
  const loadMore = () => {
    currentPage.value++
  }

  // 点赞切换
  const toggleLike = async (article) => {
    if (!isAuthenticated.value) {
      // 未登录，跳转登录页，登录后自动返回当前页
      window.location.href = `${loginUrl}?next=${encodeURIComponent(window.location.pathname)}`
      return
    }

    try {
      const response = await fetch('/api/toggle-note-like/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ note_id: article.id })
      })
      const data = await response.json()
      if (data.status === 'success') {
        article.user_has_liked = data.user_has_liked
        article.likes = data.total_likes
      } else {
        throw new Error(extractApiErrorMessage(data, '点赞失败'))
      }
    } catch (error) {
      console.error('点赞失败:', error)
      notify('error', error.message || '点赞失败，请稍后重试')
    }
  }

  // 切换收藏
  const toggleFavorite = async (article) => {
    if (!isAuthenticated.value) {
      notify('warning', '请先登录')
      navigateToLogin()
      return
    }

    try {
      const response = await fetch(`/api/notes/${article.id}/favorite/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        }
      })
      const data = await response.json()
      if (data.status === 'success') {
        article.is_favorited = data.is_favorited
        notify('success', data.is_favorited ? '已收藏' : '已取消收藏')
      } else {
        throw new Error(extractApiErrorMessage(data, '收藏失败'))
      }
    } catch (error) {
      console.error('收藏失败:', error)
      notify('error', error.message || '收藏失败，请稍后重试')
    }
  }

  return {
    loading,
    searchQuery,
    isSearching,
    isAuthenticated,
    articles,
    currentPage,
    itemsPerPage,
    paginatedArticles,
    hasMore,
    activeNav,
    activeNavLabel,
    searchResultLabel,
    navItems,
    navGroups,
    activeContentType,
    activeSort,
    contentTypes,
    contentTypeTabs,
    sortOptions,
    hotTopics,
    communityStats,
    activeContributors,
    getIconClass,
    userAvatar,
    handleImageError,
    handleAvatarError,
    fetchArticles,
    fetchFavorites,
    fetchHistory,
    fetchHomeStats,
    handleSearch,
    clearSearch,
    setContentType,
    setSort,
    navigateToArticle,
    navigateToNewNote,
    navigateToLogin,
    navigateToSignup,
    setActiveNav,
    loadMore,
    formatTimeAgo,
    toggleLike,
    toggleFavorite,
    recordHistory
  }
}
