// Vue 3 公共笔记应用 - 使用内联组件定义
// 等待DOM加载完成
document.addEventListener('DOMContentLoaded', function() {

    // 设置全局数据
    window.GLOBAL_DATA = {
        noteData: null,
        navigationData: null,
        isAuthenticated: false
    };

    // 解析页面数据
    (function() {
        const navigationDataElement = document.getElementById('navigation-data');
        const noteDataElement = document.getElementById('note-data');

        if (navigationDataElement && navigationDataElement.textContent) {
            try {
                const navigationData = JSON.parse(navigationDataElement.textContent);
                window.GLOBAL_DATA.navigationData = navigationData;
                window.GLOBAL_DATA.isAuthenticated = navigationData.is_authenticated || false;
              } catch (error) {
                console.error('解析导航数据失败:', error);
            }
        }

        if (noteDataElement && noteDataElement.textContent) {
            try {
                const noteData = JSON.parse(noteDataElement.textContent);
                window.GLOBAL_DATA.noteData = noteData;
                } catch (error) {
                console.error('解析笔记数据失败:', error);
            }
        }
    })();

    // Vue组件定义
    const PublicNoteView = {
        template: '' +
            '<div v-if="note" class="note-detail-container">' +
                '<!-- 顶部导航栏 -->' +
                '<nav class="detail-navbar">' +
                    '<div class="navbar-content">' +
                        '<div class="navbar-left">' +
                            '<a href="/knowledge/" class="back-button">' +
                                '<i class="fas fa-arrow-left"></i>' +
                                '返回列表' +
                            '</a>' +
                        '</div>' +
                        '<div class="navbar-actions">' +
                            '<button class="action-button" @click="toggleTheme" title="切换主题">' +
                                '<i class="fas fa-moon"></i>' +
                            '</button>' +
                            '<button class="action-button" @click="adjustFontSize" title="调整字体">' +
                                '<i class="fas fa-font"></i>' +
                            '</button>' +
                            '<button class="action-button" @click="shareArticle" title="分享">' +
                                '<i class="fas fa-share-alt"></i>' +
                            '</button>' +
                        '</div>' +
                    '</div>' +
                '</nav>' +

                '<!-- 主内容区域 -->' +
                '<main class="detail-main">' +
                    '<!-- 文章头部 -->' +
                    '<header class="article-header">' +
                        '<h1 class="article-title">{{ note.title }}</h1>' +

                        '<div class="article-meta">' +
                            '<div class="meta-item author-info">' +
                                '<div class="author-avatar">' +
                                    '<template v-if="note.author.avatar_url">' +
                                        '<img :src="note.author.avatar_url" :alt="note.author.username" class="avatar-img">' +
                                    '</template>' +
                                    '<template v-else>' +
                                        '<span class="avatar-text">{{ note.author.username.charAt(0).toUpperCase() }}</span>' +
                                    '</template>' +
                                '</div>' +
                                '<div class="author-details">' +
                                    '<span class="author-name">{{ note.author.username }}</span>' +
                                    '<span class="publish-date">' +
                                        '<i class="far fa-calendar-alt"></i>' +
                                        '发布于 {{ note.created_at }}' +
                                    '</span>' +
                                '</div>' +
                            '</div>' +

                            '<div class="meta-divider"></div>' +

                            '<div class="meta-item">' +
                                '<div class="meta-icon">' +
                                    '<i class="far fa-clock"></i>' +
                                '</div>' +
                                '<span class="meta-text">阅读时间 {{ readingTime }} 分钟</span>' +
                            '</div>' +

                            '<div class="meta-divider"></div>' +

                            '<div class="meta-item">' +
                                '<div class="meta-icon">' +
                                    '<i class="far fa-eye"></i>' +
                                '</div>' +
                                '<span class="meta-text">{{ note.views || 0 }} 次阅读</span>' +
                            '</div>' +

                            '<div class="meta-divider"></div>' +

                            '<div class="meta-item">' +
                                '<button ' +
                                    'class="like-button" ' +
                                    ':class="{ \'liked\': note.user_has_liked }" ' +
                                    '@click="toggleLike" ' +
                                    ':disabled="isLiking" ' +
                                    'title="给作者点赞"' +
                                '>' +
                                    '<div class="like-icon" :class="{ \'liked\': note.user_has_liked }">' +
                                        '<i :class="note.user_has_liked ? \'fas\' : \'far\'" class="fa-heart"></i>' +
                                    '</div>' +
                                    '<span class="like-count">{{ note.likes || 0 }}</span>' +
                                '</button>' +
                            '</div>' +
                        '</div>' +
                    '</header>' +

                    '<!-- 文章内容 - 显示完整内容 -->' +
                    '<article class="article-content content-wrapper" v-html="displayContent"></article>' +

                    '<!-- 章节导航 -->' +
                    '<div class="chapter-navigation">' +
                        '<div class="navigation-container">' +
                            '<a v-if="previousNote" :href="previousNote.public_url" class="chapter-link prev">' +
                                '<div class="nav-icon">' +
                                    '<i class="fas fa-arrow-left"></i>' +
                                '</div>' +
                                '<div class="chapter-info">' +
                                    '<span class="chapter-label">' +
                                        '上一篇' +
                                    '</span>' +
                                    '<span class="chapter-title">{{ previousNote.title }}</span>' +
                                '</div>' +
                            '</a>' +

                            '<div v-else class="chapter-link prev disabled">' +
                                '<div class="nav-icon">' +
                                    '<i class="fas fa-arrow-left"></i>' +
                                '</div>' +
                                '<div class="chapter-info">' +
                                    '<span class="chapter-label">上一篇</span>' +
                                    '<span class="chapter-title">没有更多文章了</span>' +
                                '</div>' +
                            '</div>' +

                            '<div class="divider"></div>' +

                            '<a v-if="nextNote" :href="nextNote.public_url" class="chapter-link next">' +
                                '<div class="chapter-info">' +
                                    '<span class="chapter-label">' +
                                        '下一篇' +
                                    '</span>' +
                                    '<span class="chapter-title">{{ nextNote.title }}</span>' +
                                '</div>' +
                                '<div class="nav-icon">' +
                                    '<i class="fas fa-arrow-right"></i>' +
                                '</div>' +
                            '</a>' +

                            '<div v-else class="chapter-link next disabled">' +
                                '<div class="chapter-info">' +
                                    '<span class="chapter-label">下一篇</span>' +
                                    '<span class="chapter-title">没有更多文章了</span>' +
                                '</div>' +
                                '<div class="nav-icon">' +
                                    '<i class="fas fa-arrow-right"></i>' +
                                '</div>' +
                            '</div>' +
                        '</div>' +
                    '</div>' +
                '</main>' +
            '</div>' +

            '<!-- 错误状态 -->' +
            '<div v-else class="error-container">' +
                '<div class="error-message">' +
                    '<i class="fas fa-exclamation-triangle error-icon"></i>' +
                    '<h2>{{ errorMessage || "无法加载笔记数据" }}</h2>' +
                    '<p>请检查链接是否正确，或稍后重试</p>' +
                    '<a href="/knowledge/" class="back-to-home-btn">' +
                        '返回首页' +
                    '</a>' +
                '</div>' +
            '</div>',
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
        computed: {
            displayContent() {
                if (!this.fullContent) return '';
                return this.fixImageUrls(this.fullContent);
            }
        },
        mounted() {
                    this.initializeData();
            this.setupScrollListener();
        },
        methods: {
            initializeData() {
                if (window.GLOBAL_DATA) {
                    this.note = window.GLOBAL_DATA.noteData;
                    this.isAuthenticated = window.GLOBAL_DATA.isAuthenticated;

                    if (window.GLOBAL_DATA.navigationData) {
                        const navData = window.GLOBAL_DATA.navigationData;
                        this.previousNote = navData.previous_note;
                        this.nextNote = navData.next_note;
                    }

                    // 总是尝试从full-content-data获取完整内容
                    const fullContentElement = document.getElementById('full-content-data');

                    if (fullContentElement && fullContentElement.textContent) {
                        try {
                            const parsedContent = JSON.parse(fullContentElement.textContent);
                            this.fullContent = parsedContent;
                        } catch (error) {
                            console.error('解析内容失败:', error);
                            // 如果JSON解析失败，直接使用原始内容
                            this.fullContent = fullContentElement.textContent.replace(/^"|"$/g, '');
                        }
                    } else {
                        this.fullContent = this.note?.content || '';
                    }

                    // 计算阅读时间并增强代码块
                    if (this.fullContent) {
                        this.readingTime = Math.ceil(this.fullContent.length / 300);
                        // DOM 更新后增强代码块
                        this.$nextTick(() => {
                            this.enhanceCodeBlocks();
                        });
                    } else {
                        console.error('No content available');
                        this.errorMessage = '无法加载文章内容';
                    }
                } else {
                    this.errorMessage = '无法获取页面数据';
                    console.error('No global data available');
                }
            },

            enhanceCodeBlocks() {
                const articleContent = document.querySelector('.article-content');
                if (!articleContent) {
                    console.log('[CodeBlock] No article-content found');
                    return;
                }

                const codeBlocks = articleContent.querySelectorAll('pre');
                console.log(`[CodeBlock] Found ${codeBlocks.length} code blocks`);

                codeBlocks.forEach((pre, index) => {
                    // 跳过已经处理过的代码块
                    if (pre.classList.contains('code-block-enhanced')) {
                        console.log(`[CodeBlock] Block ${index} already enhanced, skipping`);
                        return;
                    }

                    // 获取代码元素或使用 pre 本身
                    let codeEl = pre.querySelector('code');
                    if (!codeEl) {
                        // 如果没有 code 标签，创建一个包裹 pre 的内容
                        const originalContent = pre.innerHTML;
                        pre.innerHTML = `<code>${originalContent}</code>`;
                        codeEl = pre.querySelector('code');
                        console.log(`[CodeBlock] Block ${index} wrapped with <code> tag`);
                    }

                    if (!codeEl) {
                        console.log(`[CodeBlock] Block ${index} has no code element, skipping`);
                        return;
                    }

                    // 添加类名
                    pre.classList.add('code-block-enhanced');

                    // 计算行数 - 处理两种情况：
                    // 1. 有实际换行符的情况
                    // 2. TinyMCE 使用 <br> 标签的情况
                    let lineCount = 1;
                    const textContent = codeEl.textContent;
                    const actualNewLines = textContent.split('\n');
                    if (actualNewLines.length > 1) {
                        lineCount = actualNewLines.length;
                    } else {
                        // 计算实际渲染的行数（通过 <br> 标签数量）
                        const brCount = (codeEl.innerHTML.match(/<br\s*\/?>/gi) || []).length;
                        lineCount = brCount + 1;
                    }

                    console.log(`[CodeBlock] Block ${index} has ${lineCount} lines (brCount: ${codeEl.innerHTML.match(/<br\s*\/?>/gi) || [].length})`);

                    // 超过5行添加折叠功能，默认折叠
                    if (lineCount > 5) {
                        pre.classList.add('long-code');
                        pre.classList.add('collapsed');
                    }

                    // 添加复制按钮
                    const copyBtn = document.createElement('button');
                    copyBtn.className = 'copy-btn';
                    copyBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
                    copyBtn.setAttribute('aria-label', '复制代码');
                    pre.appendChild(copyBtn);

                    copyBtn.addEventListener('click', async (e) => {
                        e.preventDefault();
                        e.stopPropagation();

                        const textToCopy = codeEl.textContent;

                        // 复制函数
                        const copyToClipboard = async (text) => {
                            if (navigator.clipboard && navigator.clipboard.writeText) {
                                try {
                                    await navigator.clipboard.writeText(text);
                                    return true;
                                } catch (err) {
                                    console.warn('Clipboard API 失败，尝试备用方法:', err);
                                }
                            }

                            try {
                                const textarea = document.createElement('textarea');
                                textarea.value = text;
                                textarea.style.position = 'fixed';
                                textarea.style.left = '-999999px';
                                textarea.style.top = '-999999px';
                                document.body.appendChild(textarea);
                                textarea.focus();
                                textarea.select();

                                const successful = document.execCommand('copy');
                                document.body.removeChild(textarea);
                                return successful;
                            } catch (err) {
                                console.error('复制失败:', err);
                                return false;
                            }
                        };

                        const success = await copyToClipboard(textToCopy);

                        if (success) {
                            copyBtn.classList.add('copied');
                            copyBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline><polyline points="4 12 9 7 20 17"></polyline></svg>';

                            setTimeout(() => {
                                copyBtn.classList.remove('copied');
                                copyBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
                            }, 2000);
                        }
                    });

                    // 添加折叠按钮（超过5行的代码块）
                    if (lineCount > 5) {
                        const collapseBtn = document.createElement('button');
                        collapseBtn.className = 'collapse-btn';
                        collapseBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>';
                        collapseBtn.setAttribute('aria-label', '展开代码');
                        pre.appendChild(collapseBtn);

                        collapseBtn.addEventListener('click', (e) => {
                            e.preventDefault();
                            e.stopPropagation();

                            const isCollapsed = pre.classList.contains('collapsed');
                            if (isCollapsed) {
                                pre.classList.remove('collapsed');
                                collapseBtn.setAttribute('aria-label', '折叠代码');
                            } else {
                                pre.classList.add('collapsed');
                                collapseBtn.setAttribute('aria-label', '展开代码');
                            }
                        });
                    }
                });
            },

            fixImageUrls(html) {
                if (!html) return '';
                const baseUrl = window.location.origin + '/';
                // 创建临时DOM来处理图片URL
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = html;
                const images = tempDiv.querySelectorAll('img');
                images.forEach(img => {
                    const src = img.getAttribute('src');
                    if (src && !src.match(/^https?:\/\//) && !src.match(/^\/\//)) {
                        // 相对路径，转换为绝对路径
                        if (!src.match(/^[a-zA-Z][a-zA-Z0-9+.-]*:/)) {
                            img.setAttribute('src', baseUrl + src.replace(/^\//, ''));
                        }
                    }
                });
                return tempDiv.innerHTML;
            },

            async toggleLike() {
                if (!this.isAuthenticated) {
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
                const notification = document.createElement('div');
                notification.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: ${success ? '#10b981' : '#ef4444'};
                    color: white;
                    padding: 12px 20px;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    z-index: 10000;
                    font-size: 14px;
                    font-weight: 500;
                    animation: slideInRight 0.3s ease-out;
                `;
                notification.textContent = message;
                document.body.appendChild(notification);

                setTimeout(() => {
                    notification.style.animation = 'slideOutRight 0.3s ease-out';
                    setTimeout(() => document.body.removeChild(notification), 300);
                }, 3000);
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
                if (currentIndex === -1) currentIndex = 1;

                articleContent.classList.remove(sizes[currentIndex]);
                currentIndex = (currentIndex + 1) % sizes.length;
                articleContent.classList.add(sizes[currentIndex]);
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
    };

    // 创建Vue应用
    if (typeof Vue !== 'undefined') {
          try {
            const app = Vue.createApp(PublicNoteView);
            // 使用默认的Vue分隔符 {{ }}
            // app.config.compiler.delimiters = ['${', '}']; // 注释掉自定义分隔符

            // 全局错误处理
            app.config.errorHandler = (err, instance, info) => {
                console.error('Vue error:', err, info);
            };

            app.mount('#public-note-app');
                } catch (error) {
            console.error('Failed to create Vue app:', error);
        }
    } else {
        console.error('Vue is not loaded');
    }
});