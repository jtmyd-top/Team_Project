// static/JS/public_note_page.js (功能完整版)

const { createApp, ref, computed, onMounted, nextTick, watch } = Vue;

// 每页的字符数 (可以根据需要调整)
const CHARS_PER_PAGE = 2000;

createApp({
    delimiters: ['[[', ']]'],
    setup() {
        // --- 响应式状态定义 ---
        const note = ref(null);
        const fullContent = ref('');
        const message = ref('正在加载笔记...');

        const currentPage = ref(1);
        const totalPages = ref(1);

        // 【新增】用于存储上一篇和下一篇文章信息的状态
        const previousNote = ref(null);
        const nextNote = ref(null);

        const isEditingPageNumber = ref(false);
        const pageInputNumber = ref(1);
        const pageInputRef = ref(null);

        // 【新增】工具栏功能相关状态
        const showToc = ref(false); // 是否显示目录
        const headings = ref([]); // 文章标题列表
        const activeHeading = ref(''); // 当前激活的标题
        const currentTheme = ref('light'); // 当前主题
        const currentFontSize = ref('medium'); // 当前字体大小：small, medium, large
        const readingTime = ref(0); // 阅读时间（分钟）

        // --- 数据初始化 ---
        onMounted(() => {
            // 初始化主题管理器
            if (window.themeManager) {
                window.themeManager.initialize().catch(error => {
                    console.error('主题初始化失败:', error);
                });
            }

            const getJsonData = (id) => {
                const el = document.getElementById(id);
                if (el && el.textContent) return JSON.parse(el.textContent);
                return null;
            };

            const noteData = getJsonData('note-data');
            const contentData = getJsonData('full-content-data');
            const errorData = getJsonData('error-message');

            if (errorData) {
                message.value = errorData;
                return;
            }

            if (noteData && typeof contentData === 'string') {
                note.value = noteData; // 直接使用整个 noteData 对象
                fullContent.value = contentData;

                const totalLength = fullContent.value.length;
                totalPages.value = totalLength > 0 ? Math.ceil(totalLength / CHARS_PER_PAGE) : 1;

                const urlParams = new URLSearchParams(window.location.search);
                let pageFromUrl = parseInt(urlParams.get('page'), 10);
                if (isNaN(pageFromUrl) || pageFromUrl < 1 || pageFromUrl > totalPages.value) {
                    pageFromUrl = 1;
                }
                currentPage.value = pageFromUrl;

                // --- vvv 【核心新增逻辑】 vvv ---
                // 读取 sessionStorage 中由列表页存入的导航数据
                const navListString = sessionStorage.getItem('noteNavigationList');
                if (navListString) {
                    try {
                        const navList = JSON.parse(navListString);
                        // 根据 public_id 找到当前笔记在列表中的位置
                        const currentIndex = navList.findIndex(item => item.public_id === note.value.public_id);

                        if (currentIndex !== -1) {
                            // 如果当前笔记不是第一篇，则设置 "上一章"
                            if (currentIndex > 0) {
                                previousNote.value = navList[currentIndex - 1];
                            }
                            // 如果当前笔记不是最后一篇，则设置 "下一章"
                            if (currentIndex < navList.length - 1) {
                                nextNote.value = navList[currentIndex + 1];
                            }
                        }
                    } catch (e) {
                        console.error("无法解析导航列表:", e);
                        // 清理可能已损坏的数据
                        sessionStorage.removeItem('noteNavigationList');
                    }
                }
                // --- ^^^ 【核心新增逻辑结束】 ^^^ ---

            } else {
                message.value = '无法加载笔记数据，或数据格式不正确。';
            }
        });

        // --- 计算属性 ---
        const currentPageContent = computed(() => {
            if (!note.value) return '';
            const start = (currentPage.value - 1) * CHARS_PER_PAGE;
            const end = start + CHARS_PER_PAGE;
            return fullContent.value.substring(start, end);
        });

        // 计算阅读时间（假设每分钟阅读300字）
        watch(fullContent, (newContent) => {
            if (newContent) {
                const wordCount = newContent.length;
                readingTime.value = Math.ceil(wordCount / 300);
            }
        });

        // --- 方法 ---
        const updateUrl = (newPage) => {
            const url = new URL(window.location.href);
            url.searchParams.set('page', newPage);
            history.pushState({ page: newPage }, '', url.toString());
        };

        const changePage = (newPage) => {
            if (newPage >= 1 && newPage <= totalPages.value) {
                currentPage.value = newPage;
                const contentContainer = document.querySelector('.main-content-scrollable') || document.querySelector('.content-container');
                contentContainer?.scrollTo(0, 0);
                updateUrl(newPage);
            }
        };

        const prevPage = () => changePage(currentPage.value - 1);
        const nextPage = () => changePage(currentPage.value + 1);

        const editPageNumber = () => {
            isEditingPageNumber.value = true;
            pageInputNumber.value = currentPage.value;
            nextTick(() => { pageInputRef.value?.select(); });
        };

        const goToPage = () => {
            let targetPage = parseInt(pageInputNumber.value, 10);
            if (!isNaN(targetPage)) {
                changePage(targetPage);
            }
            isEditingPageNumber.value = false;
        };

        // 【新增】主题切换功能
        const toggleTheme = () => {
            currentTheme.value = currentTheme.value === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', currentTheme.value);
            localStorage.setItem('theme', currentTheme.value);
        };

        // 【新增】字体大小调整
        const adjustFontSize = () => {
            const sizes = ['small', 'medium', 'large'];
            const currentIndex = sizes.indexOf(currentFontSize.value);
            const nextIndex = (currentIndex + 1) % sizes.length;
            currentFontSize.value = sizes[nextIndex];
            
            const contentElement = document.querySelector('.article-content');
            if (contentElement) {
                contentElement.className = contentElement.className.replace(/font-size-\w+/, '');
                contentElement.classList.add(`font-size-${currentFontSize.value}`);
            }
            localStorage.setItem('fontSize', currentFontSize.value);
        };

        // 【新增】目录切换
        const toggleToc = () => {
            showToc.value = !showToc.value;
            
            // 第一次打开目录时提取标题
            if (showToc.value && headings.value.length === 0) {
                extractHeadings();
            }
        };

        // 【新增】提取文章标题
        const extractHeadings = () => {
            nextTick(() => {
                const contentElement = document.querySelector('.article-content');
                if (!contentElement) return;
                
                const headingElements = contentElement.querySelectorAll('h1, h2, h3, h4, h5, h6');
                headings.value = Array.from(headingElements).map((heading, index) => {
                    // 为标题添加ID（如果没有）
                    if (!heading.id) {
                        heading.id = `heading-${index}`;
                    }
                    return {
                        id: heading.id,
                        text: heading.textContent,
                        level: parseInt(heading.tagName.substring(1))
                    };
                });
            });
        };

        // 【新增】分享文章
        const shareArticle = async () => {
            const url = window.location.href;
            const title = note.value?.title || '分享文章';
            
            if (navigator.share) {
                try {
                    await navigator.share({
                        title: title,
                        url: url
                    });
                } catch (err) {
                    if (err.name !== 'AbortError') {
                        copyToClipboard(url);
                    }
                }
            } else {
                copyToClipboard(url);
            }
        };

        // 复制到剪贴板
        const copyToClipboard = (text) => {
            navigator.clipboard.writeText(text).then(() => {
                alert('链接已复制到剪贴板');
            }).catch(() => {
                // 备用方案
                const textarea = document.createElement('textarea');
                textarea.value = text;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                alert('链接已复制到剪贴板');
            });
        };

        // 【新增】监听滚动，高亮当前标题
        const handleScroll = () => {
            if (!showToc.value || headings.value.length === 0) return;
            
            const scrollPosition = window.scrollY + 100;
            
            for (let i = headings.value.length - 1; i >= 0; i--) {
                const heading = document.getElementById(headings.value[i].id);
                if (heading && heading.offsetTop <= scrollPosition) {
                    activeHeading.value = headings.value[i].id;
                    break;
                }
            }
        };

        // 初始化时加载保存的设置
        onMounted(() => {
            // 加载主题设置
            const savedTheme = localStorage.getItem('theme') || 'light';
            currentTheme.value = savedTheme;
            document.documentElement.setAttribute('data-theme', savedTheme);
            
            // 加载字体大小设置
            const savedFontSize = localStorage.getItem('fontSize') || 'medium';
            currentFontSize.value = savedFontSize;
            nextTick(() => {
                const contentElement = document.querySelector('.article-content');
                if (contentElement) {
                    contentElement.classList.add(`font-size-${savedFontSize}`);
                }
            });

            // 添加滚动监听
            window.addEventListener('scroll', handleScroll);
        });

        return {
            note,
            message,
            currentPage,
            totalPages,
            currentPageContent,
            previousNote,
            nextNote,
            prevPage,
            nextPage,
            isEditingPageNumber,
            pageInputNumber,
            pageInputRef,
            editPageNumber,
            goToPage,
            // 新增的工具栏功能
            showToc,
            headings,
            activeHeading,
            currentTheme,
            currentFontSize,
            readingTime,
            toggleTheme,
            adjustFontSize,
            toggleToc,
            shareArticle,
        };
    }
}).mount('#public-note-app');
