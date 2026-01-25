// static/JS/public_notes_list.js (最终注释版)

const { createApp, ref, computed, onMounted, onUnmounted, nextTick, watch } = Vue;

createApp({
    delimiters: ['[[', ']]'],
    setup() {
        // --- 1. 响应式状态定义 ---
        const allNotes = ref([]); // 存储从API获取的所有笔记
        const isLoading = ref(true); // 控制加载状态的显示
        const containerRef = ref(null); // 用于引用主内容容器的DOM元素
        const currentPage = ref(1); // 当前页码
        const notesPerPage = ref(4); // 每页显示的笔记数量 (这个值会被动态计算)
        const searchQuery = ref(''); // 绑定搜索框的输入值

        // --- 2. 计算属性 (根据状态自动变化) ---

        // 计算属性：根据搜索框内容过滤笔记
        const filteredNotes = computed(() => {
            if (!Array.isArray(allNotes.value)) return [];

            const query = searchQuery.value.trim().toLowerCase();
            if (!query) {
                return allNotes.value; // 如果搜索框为空，返回所有笔记
            }

            // 如果有搜索词，则过滤
            return allNotes.value.filter(note => {
                const titleMatch = note.title.toLowerCase().includes(query);
                const excerptMatch = note.excerpt.toLowerCase().includes(query);
                const tagsMatch = note.tags && note.tags.some(tag => tag.toLowerCase().includes(query));
                return titleMatch || excerptMatch || tagsMatch;
            });
        });

        // 计算属性：总页数 (依赖于过滤后的笔记数量)
        const totalPages = computed(() => {
            return Math.ceil(filteredNotes.value.length / notesPerPage.value) || 1;
        });

        // 计算属性：当前页应该显示的笔记 (依赖于过滤后的笔记和当前页码)
        const paginatedNotes = computed(() => {
            const start = (currentPage.value - 1) * notesPerPage.value;
            const end = start + notesPerPage.value;
            return filteredNotes.value.slice(start, end);
        });

        // --- 3. 监听器 ---

        // 监听搜索框的输入变化
        watch(searchQuery, () => {
            // 当用户开始搜索时，自动将页面重置到第一页
            currentPage.value = 1;
        });

        // --- 4. 方法 ---

        // 核心方法：动态计算每页应显示多少篇文章以撑满屏幕
        const calculateNotesPerPage = () => {
            nextTick(() => {
                if (!containerRef.value) return;

                // --- vvv 这里是您可以微调的地方 vvv ---
                // 我们估算单个文章卡片的高度。这个值越精确，布局就越完美。
                // 您可以在浏览器按F12，选中一个卡片，查看它的实际高度。
                const typicalNoteHeight = 220; // 估算值，单位：像素
                // --- ^^^ 您可以修改这个数字 ^^^ ---

                const containerHeight = containerRef.value.clientHeight;
                const count = Math.floor(containerHeight / typicalNoteHeight);
                notesPerPage.value = count > 0 ? count : 1;

                if (currentPage.value > totalPages.value) {
                    currentPage.value = totalPages.value;
                }
            });
        };

        // 从后端API获取数据
        const fetchData = async () => {
            try {
                const response = await fetch('/api/public-notes/');
                if (!response.ok) throw new Error('数据加载失败');
                allNotes.value = await response.json();
                calculateNotesPerPage(); // 数据加载后，计算分页
            } catch (error) {
                console.error(error);
            } finally {
                isLoading.value = false;
            }
        };

        // 翻页逻辑
        const changePage = (newPage) => {
            if (newPage >= 1 && newPage <= totalPages.value) {
                currentPage.value = newPage;
            }
        };
        const prevPage = () => changePage(currentPage.value - 1);
        const nextPage = () => changePage(currentPage.value + 1);
        // 【新增】导航到详情页前，保存当前列表状态
        const navigateToNote = (note) => {
            // 我们使用 filteredNotes，这样即使用户搜索了，顺序也是正确的
            const navigationList = filteredNotes.value.map(item => ({
                public_url: item.public_url,
                title: item.title,
                // 从 public_url 中提取 public_id，用于后续匹配
                public_id: item.public_url.split('/')[3]
            }));

            // 将这个包含顺序、标题和ID的列表存入 sessionStorage
            sessionStorage.setItem('noteNavigationList', JSON.stringify(navigationList));

            // 跳转到目标页面
            window.location.href = note.public_url;
        };
        // --- 5. 生命周期钩子 ---
        onMounted(() => {
            // 初始化主题管理器
            if (window.themeManager) {
                window.themeManager.initialize().catch(error => {
                    console.error('主题初始化失败:', error);
                });
            }

            fetchData();
            window.addEventListener('resize', calculateNotesPerPage); // 监听窗口大小变化
        });

        onUnmounted(() => {
            window.removeEventListener('resize', calculateNotesPerPage); // 销毁时移除监听
        });

        // --- 6. 返回暴露给模板的变量和方法 ---
        return {
            isLoading,
            searchQuery,
            filteredNotes,
            paginatedNotes,
            currentPage,
            totalPages,
            prevPage,
            allNotes,
            nextPage,
            containerRef,
            navigateToNote,
        };
    }
}).mount('#public-notes-app');