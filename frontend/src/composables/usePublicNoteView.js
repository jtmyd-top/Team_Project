import { ref } from 'vue'

export function usePublicNoteView(notificationRef) {
  // 状态
  const note = ref(null)
  const errorMessage = ref(null)
  const fullContent = ref('')
  const isLiking = ref(false)
  const isAuthenticated = ref(false)
  const readingTime = ref(0)
  const previousNote = ref(null)
  const nextNote = ref(null)

  // 初始化数据
  const initializeData = () => {
    if (window.GLOBAL_DATA) {
      note.value = window.GLOBAL_DATA.noteData
      isAuthenticated.value = window.GLOBAL_DATA.isAuthenticated

      if (window.GLOBAL_DATA.navigationData) {
        const navData = window.GLOBAL_DATA.navigationData
        previousNote.value = navData.previous_note
        nextNote.value = navData.next_note
      }

      if (note.value && note.value.content) {
        fullContent.value = note.value.content
        // 计算阅读时间（假设300字符/分钟）
        readingTime.value = Math.ceil(fullContent.value.length / 300)
      }
    } else {
      errorMessage.value = '无法获取页面数据'
    }
  }

  // 获取 Cookie
  const getCookie = (name) => {
    let cookieValue = null
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';')
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim()
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
          break
        }
      }
    }
    return cookieValue
  }

  // 显示通知
  const showNotification = (success, message) => {
    if (notificationRef.value) {
      if (success) {
        notificationRef.value.success(message)
      } else {
        notificationRef.value.error(message)
      }
    }
  }

  // 切换点赞
  const toggleLike = async () => {
    if (!isAuthenticated.value) {
      window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname)
      return
    }

    if (isLiking.value) return

    isLiking.value = true

    try {
      const response = await fetch('/api/toggle-note-like/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
          note_id: note.value.id
        })
      })

      const data = await response.json()

      if (data.status === 'success') {
        note.value.user_has_liked = data.user_has_liked
        note.value.likes = data.total_likes

        const message = data.action === 'liked' ? '点赞成功！' : '已取消点赞'
        showNotification(true, message)
      } else {
        showNotification(false, data.message || '操作失败')
      }
    } catch (error) {
      console.error('点赞失败:', error)
      showNotification(false, '网络错误，请稍后重试')
    } finally {
      isLiking.value = false
    }
  }

  // 切换主题
  const toggleTheme = () => {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light'
    const newTheme = currentTheme === 'light' ? 'dark' : 'light'
    document.documentElement.setAttribute('data-theme', newTheme)
    localStorage.setItem('theme', newTheme)
  }

  // 调整字体大小
  const adjustFontSize = () => {
    const articleContent = document.querySelector('.article-content')
    if (!articleContent) return

    const sizes = ['font-size-small', 'font-size-medium', 'font-size-large']
    let currentIndex = sizes.findIndex(size => articleContent.classList.contains(size))
    if (currentIndex === -1) currentIndex = 1

    articleContent.classList.remove(sizes[currentIndex])
    currentIndex = (currentIndex + 1) % sizes.length
    articleContent.classList.add(sizes[currentIndex])
  }

  // 切换目录
  const toggleToc = () => {
    const toc = document.querySelector('.table-of-contents')
    if (toc) {
      toc.style.display = toc.style.display === 'none' ? 'block' : 'none'
    }
  }

  // 复制到剪贴板
  const copyToClipboard = (text) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        showNotification(true, '链接已复制到剪贴板')
      })
    } else {
      const textArea = document.createElement('textarea')
      textArea.value = text
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      showNotification(true, '链接已复制到剪贴板')
    }
  }

  // 分享文章
  const shareArticle = () => {
    const url = window.location.href
    const title = note.value.title

    if (navigator.share) {
      navigator.share({ title, url }).catch(() => copyToClipboard(url))
    } else {
      copyToClipboard(url)
    }
  }

  // 设置滚动监听
  const setupScrollListener = () => {
    const progressBar = document.getElementById('reading-progress-bar')
    if (progressBar) {
      window.addEventListener('scroll', () => {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop
        const scrollHeight = document.documentElement.scrollHeight - window.innerHeight
        const progress = (scrollTop / scrollHeight) * 100
        progressBar.style.width = progress + '%'
      })
    }
  }

  return {
    note,
    errorMessage,
    fullContent,
    isLiking,
    isAuthenticated,
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
  }
}
