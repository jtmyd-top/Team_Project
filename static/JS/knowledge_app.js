/**
 * static/JS/knowledge_app.js
 * Knowledge Notes: TinyMCE 自托管版核心逻辑
 * (版本：修复了分页和数据同步问题)
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
const { createApp, ref, watch, nextTick, onMounted, onUnmounted, computed } = window.Vue;
createApp({
  setup() {
    // --- 状态变量 ---
    const editorElRef = ref(null);
    const initialDataElement = document.getElementById('initial-data');
    const initialData = JSON.parse((initialDataElement && initialDataElement.textContent) || '{}');
    const sidebarNotes = ref(initialData.sidebar_notes || []);
    const initialHasNotes = ref(initialData.has_notes || false);
    const csrfToken = initialData.csrf_token || '';
    const selectedNoteId = ref(null);
    const notes = ref([]);// 新增一个 notes 数组来存储提示信息
    const selectedNote = ref({ // 确保这里有完整的初始值
      id: null,
      title: '',
      content: '',
      is_public: false,
      public_url: '',
      project: null,
      created_at: '',
      author: null,
      updated_at: '',
      last_modified_by: null,
      pagination: {
        current_page: 1,
        total_pages: 1,
        has_next: false,
        has_previous: false
      },
      tags: [] // <--- 确保有 tags 数组，即使为空
    });
    const fullNoteContentForEditing = ref('');
    const isLoading = ref(false);
    const isEditing = ref(false);
    const isSidebarCollapsed = ref(localStorage.getItem('isSidebarCollapsed') === 'true');
    const searchQuery = ref('');
    let editorInstance = null;
    const copyStatus = ref('copy');
    const toast = ref({ visible: false, message: '', type: 'success' });
    let toastTimer = null;
    const confirmDialog = ref({ visible: false, message: '', onConfirm: null, onCancel: null });
    const currentPage = ref(1);
    const totalPages = ref(1);
    const isEditingPageNumber = ref(false);
    const pageInputNumber = ref(1);
    const pageInputRef = ref(null);
    const iconClass = computed(() => isSidebarCollapsed.value ? 'fas fa-chevron-right' : 'fas fa-chevron-left');

    // --- 辅助函数 ---
    const hasNotes = computed(() => sidebarNotes.value.length > 0);
    const setupInactivityTimer = () => {
      let inactivityTimer;
      const timeoutDuration = 3 * 60 * 60 * 1000;
      const warningDuration = 2 * 60 * 1000;
      const logoutUser = () => { window.location.href = '/accounts/logout/'; };
      const showWarning = () => {
        clearTimeout(inactivityTimer);
        showConfirm('您已长时间未活动，为保障您的账户安全，系统将在2分钟后自动登出。点击“确定”以继续保持登录。').then(confirmed => {
          if (confirmed) resetTimer(); else logoutUser();
        });
        inactivityTimer = setTimeout(logoutUser, warningDuration);
      };
      const resetTimer = () => {
        clearTimeout(inactivityTimer);
        inactivityTimer = setTimeout(showWarning, timeoutDuration - warningDuration);
      };
      window.addEventListener('load', resetTimer);
      document.addEventListener('mousemove', resetTimer);
      document.addEventListener('mousedown', resetTimer);
      document.addEventListener('keypress', resetTimer);
      document.addEventListener('touchmove', resetTimer);
      document.addEventListener('scroll', resetTimer);
    };

    const handleSearchClickWhenCollapsed = () => {
      if (isSidebarCollapsed.value) {
        toggleSidebar();
        nextTick(() => {
          document.querySelector('.sidebar-search input')?.focus();
        });
      }
    };

    const showToast = (message, type = 'success', duration = 3000) => {
      if (toastTimer) clearTimeout(toastTimer);
      toast.value = { message, type, visible: true };
      toastTimer = setTimeout(() => { toast.value.visible = false; }, duration);
    };

    const showConfirm = (message) => new Promise((resolve) => {
      confirmDialog.value = { message, visible: true, onConfirm: () => { resolve(true); confirmDialog.value.visible = false; }, onCancel: () => { resolve(false); confirmDialog.value.visible = false; } };
    });

    const destroyEditor = () => {
      if (editorInstance) {
        try { editorInstance.remove(); } catch (e) { console.error("销毁编辑器时出错:", e); }
        finally { editorInstance = null; }
      }
    };

    // --- 核心函数 ---
    const loadTinyMCE = async () => {
      if (typeof tinymce === 'undefined') {
        console.error('TinyMCE 未加载');
        return;
      }
      destroyEditor();
      const editorEl = editorElRef.value;
      if (!editorEl) {
        console.error('通过 ref 未能获取到编辑区域 DOM 元素。请确认模板中有 <textarea ref="editorElRef">');
        return;
      }
      tinymce.init({
        target: editorEl,
        language: 'zh_CN',
        relative_urls: false,
        remove_script_host: false,
        convert_urls: false,
        menubar: false,
        branding: false,
        min_height: 400,
        max_height: 700,
        license_key: 'gpl',
        // 禁用license key manager插件自动加载
        plugin_base_urls: {},
        // 显式禁用不需要的插件
        forced_plugins: [],
        plugins: ['preview', 'searchreplace', 'autolink', 'fullscreen', 'image', 'link', 'media', 'code', 'codesample', 'table', 'nonbreaking', 'charmap', 'pagebreak', 'anchor', 'lists', 'textpattern', 'help', 'emoticons', 'autosave', 'wordcount', 'tpImportword', 'tpIndent2em'].join(' '),
        toolbar: ['undo redo | styles | bold italic underline strikethrough | forecolor backcolor | removeformat', 'alignleft aligncenter alignright alignjustify | bullist numlist | outdent indent | tpIndent2em | lineheight | blockquote | subscript superscript', 'link unlink anchor |image media | table | nonbreaking | hr pagebreak |charmap emoticons | code codesample | tpImportword | searchreplace | preview fullscreen | wordcount | help'],
        automatic_uploads: true,
        images_upload_handler: (blobInfo, progress) => new Promise((resolve, reject) => {
          const formData = new FormData();
          formData.append('file', blobInfo.blob(), blobInfo.filename());
          fetch('/api/upload/image/', { method: 'POST', headers: { 'X-CSRFToken': csrfToken }, body: formData })
            .then(response => {
              if (!response.ok) {
                response.json().then(errData => { reject(errData.error || `HTTP error: ${response.status}`); }).catch(() => { reject(`HTTP error: ${response.status}`); });
                return;
              }
              return response.json();
            })
            .then(data => {
              if (!data || typeof data.location !== 'string') {
                reject('从服务器返回了无效的 JSON 格式');
                return;
              }
              resolve(data.location);
            })
            .catch(error => { reject('图片上传失败: ' + error); });
        }),
        table_toolbar: 'tableprops tabledelete | tableinsertrowbefore tableinsertrowafter tabledeleterow | tableinsertcolbefore tableinsertcolafter tabledeletecol',
        table_grid: true,
        table_cell_advtab: true,
        table_row_advtab: true,
        table_advtab: true,
        fontsize_formats: '12px 14px 16px 18px 24px 36px 48px 56px 72px',
        font_formats: '微软雅黑=Microsoft YaHei,Helvetica Neue,PingFang SC,sans-serif;苹果苹方=PingFang SC,Microsoft YaHei,sans-serif;宋体=simsun,serif;仿宋体=FangSong,serif;黑体=SimHei,sans-serif;Arial=arial,helvetica,sans-serif;Symbol=symbol;',
        paste_data_images: true,
        setup: (ed) => {
          ed.on('init', () => {
            editorInstance = ed;
            if (isEditing.value) {
              ed.setContent(fullNoteContentForEditing.value);
            }
          });
        }
      });
    };

    const selectNote = async (noteId, page = 1) => {
        if (isEditing.value) {
          const confirmed = await showConfirm('您正在编辑，确定要切换到其他笔记吗？所有未保存的更改都将丢失。');
          if (!confirmed) return;
          isEditing.value = false;
          destroyEditor();
        }

        isLoading.value = true;
        try {
          const previewUrl = `/api/notes/${noteId}/?page=${page}`;
          const previewResponse = await fetch(previewUrl);
          if (!previewResponse.ok) throw new Error('笔记加载失败');
          const noteData = await previewResponse.json();

          // 更新分页信息
          selectedNote.value = {
            ...noteData,
            content: noteData.content,
            tags: noteData.tags || [],
            updated_at: noteData.updated_at,
            last_modified_by: noteData.last_modified_by,
            pagination: noteData.pagination  // 确保分页信息被正确设置
          };

          // 更新分页状态
          currentPage.value = noteData.pagination.current_page;
          totalPages.value = noteData.pagination.total_pages;
          selectedNoteId.value = noteId;

        } catch (error) {
          console.error("selectNote 错误:", error);
          showToast(error.message, 'error');
          selectedNote.value = null;
        } finally {
          isLoading.value = false;
        }
      };

    const updateNote = async (isFullUpdate = true) => {
      if (!selectedNote.value) return;
      isLoading.value = true; // 开始保存时显示加载状态
      const currentTitleInput = document.querySelector('.edit-header input[type=text]');
      const currentTitle = currentTitleInput ? currentTitleInput.value : selectedNote.value.title;
      const body = { title: currentTitle, is_public: selectedNote.value.is_public };
      if (isEditing.value) {
        body.content = editorInstance ? editorInstance.getContent() : fullNoteContentForEditing.value;
      }
      try {
        const response = await fetch(`/api/notes/${selectedNote.value.id}/`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify(body)
        });
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: '未知错误' }));
          throw new Error(errorData.detail || '保存失败');
        }

        const noteInSidebar = sidebarNotes.value.find(n => n.id === selectedNote.value.id);
        if (noteInSidebar) noteInSidebar.title = currentTitle;

        if (isFullUpdate) {
          isEditing.value = false;
          await selectNote(selectedNote.value.id, 1);
          showToast('保存成功！');
        } else {
          await selectNote(selectedNote.value.id, currentPage.value);
          showToast('设置已更新！');
        }
      } catch (error) {
        showToast(error.message, 'error');
      } finally {
        isLoading.value = false;
      }
    };

    const startEditing = async () => {
      if (!selectedNote.value) return;
      // 每次编辑前，都获取最新的完整内容，防止多人协作时内容冲突
      isLoading.value = true;
      try {
        const res = await fetch(`/api/notes/${selectedNote.value.id}/?full_content=true`);
        const data = await res.json();
        fullNoteContentForEditing.value = data.content;
        selectedNote.value.updated_at = data.updated_at;
        selectedNote.value.last_modified_by = data.last_modified_by;
        isEditing.value = true;
      } catch (error) {
        showToast('加载编辑内容失败: ' + error.message, 'error');
      } finally {
        isLoading.value = false;
      }
    };

    const cancelEditing = async () => {
      // 检查编辑器内容是否有变化
      const currentContent = editorInstance ? editorInstance.getContent() : fullNoteContentForEditing.value;
      const hasUnsavedChanges = currentContent !== fullNoteContentForEditing.value;

      if (hasUnsavedChanges) {
        const confirmed = await showConfirm('您有未保存的更改，确定要放弃吗？');
        if (!confirmed) return;  // 用户点了取消，就不退出编辑
      }

      isEditing.value = false;
      destroyEditor();
    };

    const prevPage = () => {
      if (currentPage.value > 1) {
        selectNote(selectedNoteId.value, currentPage.value - 1);
      }
    };

    const nextPage = () => {
      if (currentPage.value < totalPages.value) {
        selectNote(selectedNoteId.value, currentPage.value + 1);
      }
    };

    const toggleSidebar = () => {
      isSidebarCollapsed.value = !isSidebarCollapsed.value;
      localStorage.setItem('isSidebarCollapsed', isSidebarCollapsed.value);
    };

    const editPageNumber = () => {
      isEditingPageNumber.value = true;
      pageInputNumber.value = currentPage.value;
      nextTick(() => {
        pageInputRef.value?.focus();
      });
    };

    const goToPage = () => {
      const targetPage = parseInt(pageInputNumber.value, 10);
      isEditingPageNumber.value = false;
      if (isNaN(targetPage) || targetPage < 1) {
        showToast('请输入一个有效的页码。', 'error');
        return;
      }
      if (targetPage > totalPages.value) {
        showToast(`页码不能超过总页数 ${totalPages.value}。`, 'error');
        return;
      }
      if (targetPage === currentPage.value) {
        showToast('您已在当前页面。', 'info');
        return;
      }
      selectNote(selectedNoteId.value, targetPage);
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

    const deleteNote = async () => {
      const noteToDelete = selectedNote.value;
      if (!noteToDelete) return;
      const confirmed = await showConfirm('此操作无法恢复，您确定要永久删除这篇笔记吗？');
      if (!confirmed) {
        showToast('操作已取消', 'info');
        return;
      }
      isLoading.value = true;
      try {
        const response = await fetch(`/api/notes/${noteToDelete.id}/`, { method: 'DELETE', headers: { 'X-CSRFToken': csrfToken } });
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: '删除失败，请重试' }));
          throw new Error(errorData.detail || '删除失败');
        }
        showToast('笔记已成功删除。', 'success');
        const deletedNoteId = noteToDelete.id;
        sidebarNotes.value = sidebarNotes.value.filter(n => n.id !== deletedNoteId);
        selectedNote.value = null;
        selectedNoteId.value = null;
        isEditing.value = false;
        if (sidebarNotes.value.length > 0) {
          await selectNote(sidebarNotes.value[0].id);
        } else {
          initialHasNotes.value = false;
        }
      } catch (error) {
        showToast(error.message, 'error');
      } finally {
        isLoading.value = false;
      }
    };

    const openNewNoteEditor = async () => {
      if (isEditing.value) {
        const confirmed = await showConfirm('您正在编辑一篇笔记。要放弃当前更改并创建新笔记吗？');
        if (!confirmed) return;

        // ✅ 在这里就把编辑状态清掉，避免 selectNote 再次弹窗
        isEditing.value = false;
        destroyEditor();
        fullNoteContentForEditing.value = "";
      }

      isLoading.value = true;
      try {
        const response = await fetch('/api/notes/create/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || '创建笔记失败');
        }
        const newNote = await response.json();
        sidebarNotes.value.unshift({id: newNote.id, title: newNote.title});
        initialHasNotes.value = true;

        await selectNote(newNote.id, 1);
        fullNoteContentForEditing.value = "";
        isEditing.value = true;

        showToast('新笔记已创建！', 'success');
      } catch (error) {
        showToast(error.message, 'error');
      } finally {
        isLoading.value = false;
      }
    };

    const handleKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'n') {
        event.preventDefault();
        openNewNoteEditor();
      }
    };

    // --- 生命周期钩子和侦听器 ---
    watch(isEditing, (isNowEditing) => {
      if (isNowEditing) {
        nextTick(() => { loadTinyMCE(); });
      } else {
        destroyEditor();
      }
    });

    onMounted(() => {
      document.addEventListener('keydown', handleKeyDown);

      // 初始化主题管理器
      if (window.themeManager) {
        window.themeManager.initialize().catch(error => {
          console.error('主题初始化失败:', error);
        });
      }

      const pathParts = window.location.pathname.split('/').filter(p => p);
      const noteIdFromUrl = (pathParts.length >= 2 && pathParts[0] === 'knowledge' && !isNaN(parseInt(pathParts[1], 10))) ? parseInt(pathParts[1], 10) : null;
      if (noteIdFromUrl) {
        selectNote(noteIdFromUrl);
      } else if (initialHasNotes.value && sidebarNotes.value.length > 0) {
        selectNote(sidebarNotes.value[0].id);
      }
      setupInactivityTimer();
    });

    onUnmounted(() => {
      document.removeEventListener('keydown', handleKeyDown);
    });

    return {
      sidebarNotes, selectedNoteId, selectedNote, searchQuery, isLoading, isEditing,
      isSidebarCollapsed, initialHasNotes, copyStatus, toast, confirmDialog,
      currentPage, totalPages, iconClass, toggleSidebar, selectNote, updateNote,
      startEditing, cancelEditing, prevPage, nextPage, isEditingPageNumber,
      pageInputNumber, pageInputRef, editPageNumber, goToPage,
      searchNotes, editorElRef, handleSearchClickWhenCollapsed,notes,hasNotes,
      openNewNoteEditor, deleteNote,
      copyPublicUrl: () => {
        if (!selectedNote.value?.public_url) return;
        try {
          navigator.clipboard.writeText(selectedNote.value.public_url);
          copyStatus.value = 'copied';
          showToast('公开链接已复制！');
          setTimeout(() => { copyStatus.value = 'copy'; }, 2000);
        } catch (err) {
          showToast('复制失败', 'error');
        }
      },
    };
  },
  delimiters: ['[[', ']]']
}).mount('#knowledge-app');

function hasClassSubstring(element, substring) {
  return element.className.indexOf(substring) !== -1;
}
const CHEVRON_RIGHT = 'fa-chevron-right';
const CHEVRON_LEFT = 'fa-chevron-left';
function test() {
  const el = document.getElementById("chevron");
  if (!el) return;
  el.classList.toggle(CHEVRON_RIGHT);
  el.classList.toggle(CHEVRON_LEFT);
}