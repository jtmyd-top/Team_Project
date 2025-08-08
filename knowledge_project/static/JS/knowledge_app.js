/**
 * static/JS/knowledge_app.js
 * 知识笔记应用的核心Vue逻辑
 */

// 在生产环境中禁用控制台输出
const IS_PRODUCTION = false; // 在部署时改为 true
if (IS_PRODUCTION) {
    console.log = function() {};
    console.warn = function() {};
    console.error = function() {};
    console.info = function() {};
}

const { createApp, ref, watch, nextTick, onMounted } = window.Vue;

createApp({
    setup() {
        // --- 响应式状态定义 ---
        const initialDataElement = document.getElementById('initial-data');
        const initialData = JSON.parse(initialDataElement.textContent);

        const sidebarNotes = ref(initialData.sidebar_notes || []);
        const initialHasNotes = ref(initialData.has_notes || false);
        const csrfToken = initialData.csrf_token || '';

        const selectedNoteId = ref(null);
        const selectedNote = ref(null);
        const isLoading = ref(false);
        const isEditing = ref(false);
        const isSidebarCollapsed = ref(false);
        const searchQuery = ref('');

        const editorTextarea = ref(null);
        let ckeditorInstance = null;

        const copyStatus = ref('copy');
        const toast = ref({ visible: false, message: '', type: 'success' });
        let toastTimer = null; // Toast 自动隐藏定时器

        // 【新增】用于自定义确认框的状态
        const confirmDialog = ref({
            visible: false,
            message: '',
            onConfirm: null, // 确认时的回调函数
            onCancel: null   // 取消时的回调函数
        });

        // --- 方法定义 ---

        /**
         * 显示一个自动消失的提示框 (Toast)
         */
        const showToast = (message, type = 'success', duration = 3000) => {
            if (toastTimer) clearTimeout(toastTimer);
            toast.value = { message, type, visible: true };
            toastTimer = setTimeout(() => { toast.value.visible = false; }, duration);
        };

        /**
         * 显示一个自定义的确认对话框
         * @param {string} message - 确认框的消息
         * @returns {Promise<boolean>} - 返回一个 Promise，解析为用户选择的结果 (true for confirm, false for cancel)
         */
        const showConfirm = (message) => {
            return new Promise((resolve) => {
                confirmDialog.value = {
                    message,
                    visible: true,
                    onConfirm: () => {
                        resolve(true);
                        confirmDialog.value.visible = false;
                    },
                    onCancel: () => {
                        resolve(false);
                        confirmDialog.value.visible = false;
                    }
                };
            });
        };

        const toggleSidebar = () => isSidebarCollapsed.value = !isSidebarCollapsed.value;
        const handleSearchClick = () => {};

        const selectNote = async (noteId) => {
            if (isLoading.value || (selectedNoteId.value === noteId && !isEditing.value)) return;
            if (isEditing.value) {
                isEditing.value = false;
            }
            isLoading.value = true;
            selectedNoteId.value = noteId;
            copyStatus.value = 'copy';
            try {
                const response = await fetch(`/api/notes/${noteId}/`);
                if (!response.ok) throw new Error('笔记加载失败，请重试');
                selectedNote.value = await response.json();
            } catch (error) {
                showToast(error.message, 'error');
                selectedNote.value = null;
            } finally {
                isLoading.value = false;
            }
        };

        watch(isEditing, (isNowEditing) => {
            if (isNowEditing) {
                nextTick(() => {
                    if (editorTextarea.value && !ckeditorInstance) {
                        ckeditorInstance = CKEDITOR.replace(editorTextarea.value, {
                            language: 'zh-cn',
                            height: '100%',
                            removePlugins: 'pastefromword,elementspath',
                        });
                        ckeditorInstance.on('instanceReady', function(event) {
                            event.editor.setData(selectedNote.value.content || '');
                        });
                    }
                });
            } else {
                if (ckeditorInstance) {
                    ckeditorInstance.destroy();
                    ckeditorInstance = null;
                }
            }
        });

        const startEditing = () => {
            if (!selectedNote.value || isLoading.value) return;
            isEditing.value = true;
        };

        // 【修改】使用自定义的确认对话框
        const cancelEditing = async () => {
            // showConfirm 返回一个 Promise，我们用 await 来等待用户操作
            const confirmed = await showConfirm('您确定要取消编辑吗？所有未保存的更改都将丢失。');
            if (confirmed) {
                isEditing.value = false;
            }
        };

        const copyPublicUrl = async () => {
            if (!selectedNote.value?.public_url) return;
            if (!navigator.clipboard) {
                showToast('您的浏览器不支持自动复制', 'error');
                return;
            }
            try {
                await navigator.clipboard.writeText(selectedNote.value.public_url);
                copyStatus.value = 'copied';
                showToast('公开链接已复制！');
                setTimeout(() => { copyStatus.value = 'copy'; }, 2000);
            } catch (err) {
                showToast('复制失败，请检查浏览器权限', 'error');
            }
        };

        const updateNote = async (isFullUpdate = true) => {
            if (!selectedNote.value) return;
            const contentData = isFullUpdate && ckeditorInstance ? ckeditorInstance.getData() : selectedNote.value.content;
            try {
                const response = await fetch(`/api/notes/${selectedNote.value.id}/`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                    body: JSON.stringify({
                        title: selectedNote.value.title,
                        content: contentData,
                        is_public: selectedNote.value.is_public
                    })
                });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: '未知错误' }));
                    throw new Error(errorData.detail || '保存失败');
                }
                const updatedNote = await response.json();
                selectedNote.value = updatedNote;
                const noteInSidebar = sidebarNotes.value.find(n => n.id === updatedNote.id);
                if (noteInSidebar) {
                    noteInSidebar.title = updatedNote.title;
                }
                if (isFullUpdate) {
                    isEditing.value = false;
                    showToast('保存成功！');
                } else {
                    showToast('设置已更新！');
                }
            } catch (error) {
                showToast(error.message, 'error');
            }
        };

        const searchNotes = async () => {
            const query = searchQuery.value.trim();
            const url = query ? `/api/notes/search/?q=${encodeURIComponent(query)}` : '/api/notes/all/';
            try {
                const response = await fetch(url);
                if (!response.ok) throw new Error('搜索失败');
                sidebarNotes.value = await response.json();
            } catch (error) {
                showToast(error.message, 'error');
            }
        };

        onMounted(() => {
            const pathParts = window.location.pathname.split('/').filter(p => p);
            const noteIdFromUrl = (pathParts.length >= 2 && pathParts[0] === 'knowledge' && !isNaN(parseInt(pathParts[1])))
                ? parseInt(pathParts[1])
                : null;
            if (noteIdFromUrl) {
                selectNote(noteIdFromUrl);
            } else if (initialHasNotes.value && sidebarNotes.value.length > 0) {
                selectNote(sidebarNotes.value[0].id);
            }
        });

        // --- 暴露给模板使用的数据和方法 ---
        return {
            sidebarNotes,
            selectedNoteId,
            selectedNote,
            searchQuery,
            isLoading,
            isEditing,
            isSidebarCollapsed,
            initialHasNotes,
            editorTextarea,
            copyStatus,
            toast,
            confirmDialog, // 暴露确认框的状态和方法
            toggleSidebar,
            selectNote,
            searchNotes,
            updateNote,
            startEditing,
            cancelEditing,
            copyPublicUrl,
            handleSearchClick,
        };
    },
    delimiters: ['[[', ']]']
}).mount('#knowledge-app');