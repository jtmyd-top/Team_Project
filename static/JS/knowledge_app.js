/**
 * static/JS/knowledge_app.js
 * Knowledge Notes: TinyMCE 自托管版核心逻辑
 * (版本：修复了编辑器加载时序问题)
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
const { createApp, ref, watch, nextTick, onMounted, computed } = window.Vue;

createApp({
  setup() {
    // --- 状态变量 ---
    const editorElRef = ref(null); // 用于绑定 textarea 元素的 ref
    const initialDataElement = document.getElementById('initial-data');
    const initialData = JSON.parse((initialDataElement && initialDataElement.textContent) || '{}');
    const sidebarNotes = ref(initialData.sidebar_notes || []);
    const initialHasNotes = ref(initialData.has_notes || false);
    const csrfToken = initialData.csrf_token || '';
    const selectedNoteId = ref(null);
    const selectedNote = ref(null);
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

    const handleSearchClickWhenCollapsed = () => {
        if (isSidebarCollapsed.value) {
          // 如果侧边栏是收缩的，就展开它
          toggleSidebar();
          // 使用 nextTick 确保 DOM 更新后再聚焦
          nextTick(() => {
            document.querySelector('.sidebar-search input')?.focus();
          });
        }
      };
    // --- 辅助函数 ---
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

    // --- TinyMCE 初始化函数 (已按最佳实践修改) ---
    const loadTinyMCE = async () => {
      if (typeof tinymce === 'undefined') {
        console.error('TinyMCE 未加载');
        return;
      }
      destroyEditor();

      // [核心修改 1] 从 ref 获取真实的 DOM 元素
      const editorEl = editorElRef.value;
      if (!editorEl) {
        console.error('通过 ref 未能获取到编辑区域 DOM 元素。请确认模板中有 <textarea ref="editorElRef">');
        return;
      }

      tinymce.init({
        // [核心修改 2] 使用 target 直接对 DOM 节点初始化，而不是用 selector
        target: editorEl,
        language:'zh_CN',
        menubar:false,
        branding: false,
        min_height:400,
        max_height: 700,
        license_key: 'gpl',
        plugins: [
        'preview', 'searchreplace', 'autolink', 'fullscreen', 'image', 'link', 'media',
        'code', 'codesample', 'table', 'nonbreaking','charmap', 'pagebreak', 'anchor',
        'lists', 'textpattern', 'help', 'emoticons', 'autosave', 'wordcount',
        'axupimgs', 'upfile', 'attachment', 'tpImportword', 'tpIndent2em'
    ].join(' '),
    // --- V3 最终修复版工具栏 ---
    // 修正了 nonbreaking 命令，移除了无效按钮
    toolbar: [
        'undo redo | styles | bold italic underline strikethrough | forecolor backcolor | removeformat',
        'alignleft aligncenter alignright alignjustify | bullist numlist | outdent indent | tpIndent2em | lineheight | blockquote | subscript superscript',
        'link unlink anchor | image axupimgs media | upfile attachment | table | nonbreaking  | hr pagebreak |charmap emoticons | code codesample | tpImportword | searchreplace | preview fullscreen | wordcount | help'
    ],
    // 表格上下文菜单
        table_toolbar: 'tableprops tabledelete | tableinsertrowbefore tableinsertrowafter tabledeleterow | tableinsertcolbefore tableinsertcolafter tabledeletecol',
        table_grid: true, // 确保显示网格用于创建表格
        table_cell_advtab: true, // 开启单元格高级属性
        table_row_advtab: true,  // 开启行高级属性
        table_advtab: true,      // 开启表格高级属性
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

    // --- 核心数据处理函数 (保持不变) ---
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
        selectedNote.value = noteData;
        currentPage.value = noteData.pagination.current_page;
        totalPages.value = noteData.pagination.total_pages;
        if (fullNoteContentForEditing.value === '' || selectedNoteId.value !== noteId) {
          const fullContentUrl = `/api/notes/${noteId}/?full_content=true`;
          const fullContentResponse = await fetch(fullContentUrl);
          if (!fullContentResponse.ok) throw new Error('无法加载笔记完整内容');
          const fullNoteData = await fullContentResponse.json();
          fullNoteContentForEditing.value = fullNoteData.content;
        }
        selectedNoteId.value = noteId;
      } catch (error) {
        showToast(error.message, 'error');
        selectedNote.value = null;
      } finally {
        isLoading.value = false;
      }
    };
    const updateNote = async (isFullUpdate = true) => {
      if (!selectedNote.value) return;
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
        const updatedNoteData = await response.json();
        if (isEditing.value) {
          selectedNote.value = { ...updatedNoteData };
          fullNoteContentForEditing.value = body.content;
        } else {
          selectedNote.value.is_public = updatedNoteData.is_public;
        }
        const noteInSidebar = sidebarNotes.value.find(n => n.id === updatedNoteData.id);
        if (noteInSidebar) noteInSidebar.title = updatedNoteData.title;
        if (isFullUpdate) {
          isEditing.value = false;
          showToast('保存成功！');
        } else {
          showToast('设置已更新！');
        }
      } catch (error) { showToast(error.message, 'error'); }
    };
    const startEditing = async () => {
      if (!selectedNote.value) return;
      if (!fullNoteContentForEditing.value) {
        isLoading.value = true;
        try {
          const res = await fetch(`/api/notes/${selectedNote.value.id}/?full_content=true`);
          const data = await res.json();
          fullNoteContentForEditing.value = data.content;
        } catch (error) { showToast('加载编辑内容失败: ' + error.message, 'error'); return; }
        finally { isLoading.value = false; }
      }
      isEditing.value = true;
    };
    const cancelEditing = async () => { isEditing.value = false; destroyEditor(); };
    const prevPage = () => { if (currentPage.value > 1) { selectNote(selectedNoteId.value, currentPage.value - 1); } };
    const nextPage = () => { if (currentPage.value < totalPages.value) { selectNote(selectedNoteId.value, currentPage.value + 1); } };
    const toggleSidebar = () => { isSidebarCollapsed.value = !isSidebarCollapsed.value; localStorage.setItem('isSidebarCollapsed', isSidebarCollapsed.value); };

    // --- 页码跳转功能 (保持不变) ---
    const editPageNumber = () => {
      isEditingPageNumber.value = true;
      pageInputNumber.value = currentPage.value;
      nextTick(() => { pageInputRef.value?.focus(); });
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

    // --- 生命周期和侦听器 (保持不变) ---
    watch(isEditing, (isNowEditing) => { if (isNowEditing) { nextTick(() => { loadTinyMCE(); }); } else { destroyEditor(); } });
    onMounted(() => {
      const pathParts = window.location.pathname.split('/').filter(p => p);
      const noteIdFromUrl = (pathParts.length >= 2 && pathParts[0] === 'knowledge' && !isNaN(parseInt(pathParts[1], 10))) ? parseInt(pathParts[1], 10) : null;
      if (noteIdFromUrl) { selectNote(noteIdFromUrl); }
      else if (initialHasNotes.value && sidebarNotes.value.length > 0) { selectNote(sidebarNotes.value[0].id); }
    });

    // --- [核心修改 3] 返回给模板的对象 (增加了 editorElRef) ---
    return {
      sidebarNotes, selectedNoteId, selectedNote, searchQuery, isLoading, isEditing,
      isSidebarCollapsed, initialHasNotes, copyStatus, toast, confirmDialog,
      currentPage, totalPages, iconClass, toggleSidebar, selectNote, updateNote,
      startEditing, cancelEditing, prevPage, nextPage, isEditingPageNumber,
      pageInputNumber, pageInputRef, editPageNumber, goToPage,
      openNewNoteEditor: () => { showToast('此功能正在开发中...', 'info'); },
      searchNotes,
      editorElRef,

      handleSearchClickWhenCollapsed,
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
    openNewNoteEditor: () => { showToast('此功能正在开发中...', 'info'); }
  };// <-- 必须将 ref 暴露给模板

  },
  delimiters: ['[[', ']]']
}).mount('#knowledge-app');
function hasClassSubstring(element, substring) {
  return element.className.indexOf(substring) !== -1;
}
function test(){

			const chevronElement = document.getElementById("chevron");

            if (chevronElement.classList.contains('fa-chevron-right')){
                chevronElement.classList.remove('fa-chevron-right');
                chevronElement.classList.add("fa-chevron-left");
                // console.log(chevronElement.classList);
            }else{
                chevronElement.classList.remove('fa-chevron-left');
                chevronElement.classList.add("fa-chevron-right");
                // console.log(chevronElement.classList);

            }
		}