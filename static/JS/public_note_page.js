// static/JS/public_note_page.js

const { createApp, ref, computed, onMounted, nextTick, watch } = Vue;

// --- 全局常量配置 ---
// 每页的字符数
const CHARS_PER_PAGE = 2000;
// 当单页内容超过多少字符时，启用三列布局
const COLUMN_LAYOUT_THRESHOLD = 1500;
// 分成几列
const COLUMN_COUNT = 3;

createApp({
    delimiters: ['[[', ']]'],
    setup() {
        // --- 响应式状态定义 ---
        const note = ref(null);
        const fullContent = ref('');
        const message = ref('正在加载笔记...');

        const currentPage = ref(1);
        const totalPages = ref(1);

        const isEditingPageNumber = ref(false);
        const pageInputNumber = ref(1);
        const pageInputRef = ref(null);

        // 用于控制布局的状态
        const useColumnLayout = ref(false);

        // --- 数据初始化 ---
        onMounted(() => {
            // Helper function to safely parse JSON from script tags
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
                note.value = {
                    title: noteData.title,
                    author: noteData.author,
                    createdAt: noteData.created_at,
                };
                fullContent.value = contentData;

                // 计算总页数
                const totalLength = fullContent.value.length;
                totalPages.value = totalLength > 0 ? Math.ceil(totalLength / CHARS_PER_PAGE) : 1;

                // 【核心修复】从URL读取初始页码
                const urlParams = new URLSearchParams(window.location.search);
                let pageFromUrl = parseInt(urlParams.get('page'), 10);

                // 验证URL页码的有效性
                if (isNaN(pageFromUrl) || pageFromUrl < 1) {
                    pageFromUrl = 1;
                }
                if (pageFromUrl > totalPages.value) {
                    pageFromUrl = totalPages.value;
                }
                currentPage.value = pageFromUrl;

            } else {
                message.value = '无法加载笔记数据，或数据格式不正确。';
            }
        });

        // --- 计算属性 ---

        // 1. 计算出当前页应该显示的【原始内容】
        const currentPageContent = computed(() => {
            if (!note.value) return '';
            const start = (currentPage.value - 1) * CHARS_PER_PAGE;
            const end = start + CHARS_PER_PAGE;
            return fullContent.value.substring(start, end);
        });

        // 2. 【新增】根据当前页内容，计算出三列的【分列内容】
        const columnContents = computed(() => {
            if (!useColumnLayout.value) return [];

            const content = currentPageContent.value;
            const pageLength = content.length;
            const columnLength = Math.ceil(pageLength / COLUMN_COUNT);
            const columns = [];

            for (let i = 0; i < COLUMN_COUNT; i++) {
                const start = i * columnLength;
                const end = start + columnLength;
                columns.push(content.substring(start, end));
            }
            return columns;
        });


        // --- 监听器 ---

        // 【新增】监听`currentPageContent`的变化，自动决定是否启用三列布局
        watch(currentPageContent, (newContent) => {
            if (newContent.length > COLUMN_LAYOUT_THRESHOLD) {
                useColumnLayout.value = true;
            } else {
                useColumnLayout.value = false;
            }
        }, { immediate: true }); // immediate: true 保证初始化时也执行一次


        // --- 方法 ---

        // 更新浏览器URL（无刷新）
        const updateUrl = (newPage) => {
            const url = new URL(window.location.href);
            url.searchParams.set('page', newPage);
            history.pushState({ page: newPage }, '', url.toString());
        };

        const changePage = (newPage) => {
            if (newPage >= 1 && newPage <= totalPages.value) {
                currentPage.value = newPage;
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
            useColumnLayout,
            columnContents,
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