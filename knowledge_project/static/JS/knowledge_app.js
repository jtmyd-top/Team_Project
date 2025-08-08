/**
 * static/JS/knowledge_app.js
 * Knowledge Notes: CKEditor 5 升级版核心逻辑 - 侧边栏交互与编辑器状态优化
 */

// 启用/禁用生产日志输出
const IS_PRODUCTION = false;
if (IS_PRODUCTION) {
  console.log = function() {};
  console.warn = function() {};
  console.error = function() {};
  console.info = function() {};
}

// 使用 Vue 3 的组合式 API
const { createApp, ref, watch, nextTick, onMounted } = window.Vue;

createApp({
  setup() {
    // --- 初始化数据 ---
    const initialDataElement = document.getElementById('initial-data');
    const initialData = JSON.parse((initialDataElement && initialDataElement.textContent) || '{}');

    // 状态变量
    const sidebarNotes = ref(initialData.sidebar_notes || []);
    const initialHasNotes = ref(initialData.has_notes || false);
    const csrfToken = initialData.csrf_token || '';

    const selectedNoteId = ref(null);
    const selectedNote = ref(null);
    const isLoading = ref(false);
    const isEditing = ref(false);
    // 读取 localStorage 中的侧边栏折叠状态，如果不存在则默认为 false
    const isSidebarCollapsed = ref(localStorage.getItem('isSidebarCollapsed') === 'true');
    const searchQuery = ref('');

    // 编辑器相关
    const editorContainer = ref(null); // CKEditor 5 容器引用
    let editorInstance = null;          // CKEditor 5 实例

    // 上传/提示/确认框
    const copyStatus = ref('copy');
    const toast = ref({ visible: false, message: '', type: 'success' });
    let toastTimer = null;
    const confirmDialog = ref({
      visible: false,
      message: '',
      onConfirm: null,
      onCancel: null
    });

    // --- 工具方法 ---
    const showToast = (message, type = 'success', duration = 3000) => {
      if (toastTimer) clearTimeout(toastTimer);
      toast.value = { message, type, visible: true };
      toastTimer = setTimeout(() => { toast.value.visible = false; }, duration);
    };

    const showConfirm = (message) => {
      return new Promise((resolve) => {
        confirmDialog.value = {
          message,
          visible: true,
          onConfirm: () => { resolve(true); confirmDialog.value.visible = false; },
          onCancel: () => { resolve(false); confirmDialog.value.visible = false; }
        };
      });
    };

    // --- 侧边栏操作 ---
    const toggleSidebar = () => {
      isSidebarCollapsed.value = !isSidebarCollapsed.value;
      // 保存侧边栏折叠状态到 localStorage
      localStorage.setItem('isSidebarCollapsed', isSidebarCollapsed.value);

      // 侧边栏状态改变时，如果编辑器是打开的，需要处理
      if (isEditing.value) {
        // 延迟执行，确保 DOM 更新完成
        nextTick(() => {
          if (isSidebarCollapsed.value) {
            // 如果侧边栏被折叠了，且编辑器是打开的，我们不销毁它，而是让它可能被 CSS 隐藏
            // 如果需要，可以在这里做一些清理工作，但通常不销毁实例
          } else {
            // 如果侧边栏展开了，且编辑器是关闭状态，重新初始化编辑器
            if (!editorInstance && editorContainer.value) {
              loadEditor(); // 重新加载编辑器
            }
          }
        });
      }
    };

    // --- 笔记操作 ---
    const selectNote = async (noteId) => {
      // 如果当前正在编辑，切换笔记前先进行确认
      if (isEditing.value) {
        const confirmed = await showConfirm('您正在编辑，确定要切换到其他笔记吗？所有未保存的更改都将丢失。');
        if (!confirmed) return; // 如果用户取消，则不执行切换

        // 退出编辑模式，并销毁编辑器实例
        isEditing.value = false;
        if (editorInstance) {
          editorInstance.destroy().catch(() => {});
          editorInstance = null;
        }
      }

      // 防止重复加载或加载过程中再次点击
      if (isLoading.value || selectedNoteId.value === noteId) return;

      isLoading.value = true;
      selectedNoteId.value = noteId;
      copyStatus.value = 'copy'; // 重置复制状态

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

    // --- 编辑器初始化与切换 ---
    watch(isEditing, (isNowEditing) => {
      if (isNowEditing) {
        nextTick(async () => { // 等待 DOM 更新
          // 创建 CKEditor 5 实例
          if (!editorInstance && editorContainer.value) {
            await loadEditor();
          } else if (editorInstance && selectedNote.value) {
            // 如果编辑器已存在，则更新内容
            editorInstance.setData(selectedNote.value.content || '');
          }
        });
      } else {
        // 退出编辑，销毁编辑器实例
        if (editorInstance) {
          editorInstance.destroy().catch(() => {});
          editorInstance = null;
        }
      }
    });

    // CKEditor 5 加载函数
    const loadEditor = async () => {
      try {
        editorInstance = await ClassicEditor.create(editorContainer.value, {
          language: 'zh-cn', // 设置语言
          toolbar: [ // 定义工具栏按钮
            'heading', 'bold', 'italic', 'link',
            'bulletedList', 'numberedList', 'blockQuote',
            'insertTable', 'codeBlock', 'imageUpload', // imageUpload 需要后端支持
            'undo', 'redo'
          ],
          simpleUpload: {
            uploadUrl: '/ckeditor5/upload/', // 使用 django_ckeditor_5 提供的上传端点
            headers: { 'X-CSRFToken': csrfToken } // 传递 CSRF Token
          },
          image: {
            toolbar: ['imageStyle:inline','imageStyle:block','imageStyle:side','|','imageTextAlternative']
          },
          table: {
            contentToolbar: ['tableColumn', 'tableRow', 'mergeTableCells']
          }
        });
        // 给编辑器注入初始内容
        if (selectedNote.value) {
          editorInstance.setData(selectedNote.value.content || '');
        }
      } catch (error) {
        console.error("CKEditor 5 initialization error:", error);
        showToast("编辑器初始化失败，请检查浏览器控制台。", "error");
      }
    };

    // 取消编辑
    const cancelEditing = async () => {
      // 只有在内容有变动时才提示
      const currentContent = editorInstance ? editorInstance.getData() : (selectedNote.value?.content || '');
      const currentTitleInput = document.querySelector('.edit-header input[type=text]');
      const currentTitle = currentTitleInput ? currentTitleInput.value : (selectedNote.value?.title || '');

      if (selectedNote.value && (selectedNote.value.title !== currentTitle || selectedNote.value.content !== currentContent)) {
          const confirmed = await showConfirm('您确定要取消编辑吗？所有未保存的更改都将丢失。');
          if (!confirmed) return;
      }
      isEditing.value = false; // 退出编辑模式
    };

    // 复制公开链接
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
        setTimeout(() => { copyStatus.value = 'copy'; }, 2000); // 2秒后重置状态
      } catch (err) {
        showToast('复制失败，请检查浏览器权限', 'error');
      }
    };

    // 更新笔记（保存）
    const updateNote = async (isFullUpdate = true) => {
      if (!selectedNote.value) return;

      // 获取编辑器内容（如果是编辑模式），否则使用当前选中的笔记内容
      const contentData = editorInstance ? editorInstance.getData() : (selectedNote.value.content || '');
      // 获取当前标题（如果是编辑模式）
      const currentTitleInput = document.querySelector('.edit-header input[type=text]');
      const currentTitle = currentTitleInput ? currentTitleInput.value : selectedNote.value.title;

      try {
        const response = await fetch(`/api/notes/${selectedNote.value.id}/`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify({
            title: currentTitle,
            content: contentData,
            is_public: selectedNote.value.is_public
          })
        });

        if (!response.ok) {
          // 尝试解析错误信息
          const errorData = await response.json().catch(() => ({ detail: '未知错误' }));
          throw new Error(errorData.detail || '保存失败');
        }

        // 保存成功
        const updatedNote = await response.json();
        selectedNote.value = updatedNote; // 更新选中的笔记数据

        // 更新侧边栏的笔记标题
        const noteInSidebar = sidebarNotes.value.find(n => n.id === updatedNote.id);
        if (noteInSidebar) {
          noteInSidebar.title = updatedNote.title;
        }

        if (isFullUpdate) {
          isEditing.value = false; // 退出编辑模式
          showToast('保存成功！');
        } else {
          showToast('设置已更新！'); // 例如，只是更新了 is_public
        }
      } catch (error) {
        showToast(error.message, 'error');
      }
    };

    // 搜索笔记
    const searchNotes = async () => {
      const query = searchQuery.value.trim();
      // 如果搜索框失去焦点，并且侧边栏是展开状态，则执行搜索
      // 如果搜索框被点击（即使折叠），我们希望展开侧边栏
      const url = query ? `/api/notes/search/?q=${encodeURIComponent(query)}` : '/api/notes/all/';
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('搜索失败');
        sidebarNotes.value = await response.json();
      } catch (error) {
        showToast(error.message, 'error');
      }
    };

    // --- 页面加载时初始化 ---
    onMounted(() => {
      const pathParts = window.location.pathname.split('/').filter(p => p); // 分割路径并过滤空字符串

      // 尝试从 URL 中解析出笔记 ID，格式如 /knowledge/{note_id}/
      const noteIdFromUrl = (pathParts.length >= 2 && pathParts[0] === 'knowledge' && !isNaN(parseInt(pathParts[1], 10)))
        ? parseInt(pathParts[1], 10) // parseInt 确保转换成数字
        : null;

      if (noteIdFromUrl) {
        selectNote(noteIdFromUrl); // 如果 URL 中有 ID，则直接打开该笔记
      } else if (initialHasNotes.value && sidebarNotes.value.length > 0) {
        // 如果没有 ID，且有笔记，则打开第一条笔记
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
      editorContainer, // 暴露编辑器容器的 ref
      copyStatus,
      toast,
      confirmDialog,
      toggleSidebar,
      selectNote,
      searchNotes,
      updateNote,
      startEditing: () => { if (selectedNote.value) isEditing.value = true; }, // 只有选中笔记后才能编辑
      cancelEditing,
      copyPublicUrl,
      // 新增：处理折叠状态下点击搜索框的逻辑
      handleSearchClickWhenCollapsed: () => {
        if (isSidebarCollapsed.value) {
          toggleSidebar(); // 展开侧边栏
        }
        // 无论是否折叠，都尝试聚焦搜索输入框
        // 使用 nextTick 确保 DOM 已经更新，input 元素可用
        nextTick(() => {
          const searchInput = document.querySelector('.sidebar-search input');
          if (searchInput) {
            searchInput.focus();
          }
        });
      },
      openNewNoteEditor: () => { // 新建笔记的逻辑
        // 检查是否在编辑状态，如果正在编辑，先提示用户
        if (isEditing.value) {
          showConfirm('您正在编辑笔记，切换到新建笔记会丢失当前更改。确定要继续吗？').then(confirmed => {
            if (confirmed) {
              isEditing.value = false; // 退出编辑模式
              // 确保编辑器被销毁
              if (editorInstance) {
                editorInstance.destroy().catch(() => {});
                editorInstance = null;
              }
              // 模拟新建笔记
              selectedNote.value = {
                id: null, // null 表示新建
                title: '未命名笔记',
                content: '',
                is_public: false,
                project: null, // 默认无项目
                created_at: new Date().toLocaleString(), // 当前时间
                // 假设 initialData 里有当前用户信息
                author: { id: initialData.user_id, username: initialData.username }
              };
              isEditing.value = true; // 进入编辑模式
            }
          });
        } else {
          // 如果不在编辑状态，直接处理新建逻辑
          selectedNote.value = {
            id: null,
            title: '未命名笔记',
            content: '',
            is_public: false,
            project: null,
            created_at: new Date().toLocaleString(),
            author: { id: initialData.user_id, username: initialData.username }
          };
          isEditing.value = true;
        }
      }
    };
  },
  delimiters: ['[[', ']]'] // Vue 模板使用的分隔符
}).mount('#knowledge-app');