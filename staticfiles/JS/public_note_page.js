// static/JS/public_note_page.js (最终完整版)

const { createApp, ref, computed, onMounted, nextTick } = Vue;

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

        // --- 数据初始化 ---
        onMounted(() => {
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

        return {
            note,
            message,
            currentPage,
            totalPages,
            currentPageContent,
            previousNote, // <-- 暴露给模板
            nextNote,     // <-- 暴露给模板
            prevPage,
            nextPage,
            isEditingPageNumber,
            pageInputNumber,
            pageInputRef,
            editPageNumber,
            goToPage,
        };
    }
}).mount('#public-note-app');