/**
 * static/JS/knowledge_app.js
 * Knowledge Notes: TinyMCE 自托管版核心逻辑 - 集成第三方插件库
 * (版本：修复加载顺序和插件缺失问题)
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
    // --- 初始化数据 ---
    const initialDataElement = document.getElementById('initial-data');
    const initialData = JSON.parse((initialDataElement && initialDataElement.textContent) || '{}');

    // ... 省略其他未改变的状态变量和函数定义 ...
    const sidebarNotes = ref(initialData.sidebar_notes || []);
    const initialHasNotes = ref(initialData.has_notes || false);
    const csrfToken = initialData.csrf_token || '';
    const selectedNoteId = ref(null);
    const selectedNote = ref(null);
    const isLoading = ref(false);
    const isEditing = ref(false);
    const isSidebarCollapsed = ref(localStorage.getItem('isSidebarCollapsed') === 'true');
    const searchQuery = ref('');
    let editorInstance = null;
    const editorContainer = ref(null);
    const iconClass = computed(() => {
      return isSidebarCollapsed.value ? 'fas fa-chevron-left' : 'fas fa-chevron-right';
    });
    const copyStatus = ref('copy');
    const toast = ref({ visible: false, message: '', type: 'success' });
    let toastTimer = null;
    const confirmDialog = ref({
      visible: false,
      message: '',
      onConfirm: null,
      onCancel: null
    });
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
    const destroyEditor = () => {
        if (editorInstance) {
            try {
                editorInstance.remove();
            } catch (e) {
                console.error("销毁编辑器时出错:", e);
            } finally {
                editorInstance = null;
            }
        }
    };


    // --- TinyMCE 初始化 ---
    const loadTinyMCE = async () => {
      if (typeof tinymce === 'undefined') {
        console.error('TinyMCE 未加载');
        return;
      }
      destroyEditor();

      const editorEl = document.getElementById('editor');
      if (!editorEl) {
        console.error('找不到编辑区域 #editor');
        return;
      }

      tinymce.init({
    selector: '#' + editorEl.id,
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

        file_picker_callback: function (succFun, value, meta) {
            var filetype = '.pdf, .txt, .zip, .rar, .7z, .doc, .docx, .xls, .xlsx, .ppt, .pptx, .mp3, .mp4';
            var input = document.createElement('input');
            input.setAttribute('type', 'file');
            input.setAttribute('accept', filetype);
            input.click();
            input.onchange = function () {
                var file = this.files[0];
                var formData = new FormData();
                formData.append("file", file);

                showToast('正在上传文件...', 'success');

                fetch('/api/upload-file/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken
                    },
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('网络响应错误');
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.code == 200 && data.data) {
                        succFun(data.data, { text: file.name });
                        showToast('文件上传成功！', 'success');
                    } else {
                        throw new Error(data.error || '上传失败，服务器返回错误');
                    }
                })
                .catch(error => {
                    showToast('上传失败: ' + error.message, 'error');
                });
            }
        },

        setup: (ed) => {
          ed.on('init', () => {
            editorInstance = ed;
            if (selectedNote.value && selectedNote.value.content) {
              ed.setContent(selectedNote.value.content);
            }
          });
        }
      });
    };

    // ... 省略其他所有未改变的函数 ...
    const selectNote = async (noteId) => {
      if (isEditing.value) {
        const confirmed = await showConfirm('您正在编辑，确定要切换到其他笔记吗？所有未保存的更改都将丢失。');
        if (!confirmed) return;
        isEditing.value = false;
      }
      if (isLoading.value || selectedNoteId.value === noteId) return;
      isLoading.value = true;
      selectedNoteId.value = noteId;
      copyStatus.value = 'copy';
      try {
        const response = await fetch(`/api/notes/${noteId}/`);
        if (!response.ok) throw new Error('笔记加载失败');
        selectedNote.value = await response.json();
      } catch (error) {
        showToast(error.message, 'error');
        selectedNote.value = null;
      } finally {
        isLoading.value = false;
      }
    };

    const updateNote = async (isFullUpdate = true) => {
      if (!selectedNote.value) return;
      const contentData = editorInstance ? editorInstance.getContent() : (selectedNote.value.content || '');
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
          const errorData = await response.json().catch(() => ({ detail: '未知错误' }));
          throw new Error(errorData.detail || '保存失败');
        }
        const updatedNote = await response.json();
        selectedNote.value = updatedNote;
        const noteInSidebar = sidebarNotes.value.find(n => n.id === updatedNote.id);
        if (noteInSidebar) noteInSidebar.title = updatedNote.title;

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

    const toggleSidebar = () => {
        isSidebarCollapsed.value = !isSidebarCollapsed.value;
        localStorage.setItem('isSidebarCollapsed', isSidebarCollapsed.value);
        if (isEditing.value) {
            nextTick(() => {
                destroyEditor();
                loadTinyMCE();
            });
        }
    };

    const startEditing = () => {
      if (selectedNote.value) {
        isEditing.value = true;
      }
    };

    const cancelEditing = async () => {
      const currentContent = editorInstance ? editorInstance.getContent() : (selectedNote.value?.content || '');
      const currentTitleInput = document.querySelector('.edit-header input[type=text]');
      const currentTitle = currentTitleInput ? currentTitleInput.value : (selectedNote.value?.title || '');
      if (selectedNote.value && (selectedNote.value.title !== currentTitle || selectedNote.value.content !== currentContent)) {
          const confirmed = await showConfirm('您确定要取消编辑吗？所有未保存的更改都将丢失。');
          if (!confirmed) return;
      }
      isEditing.value = false;
    };

    const copyPublicUrl = async () => {
      if (!selectedNote.value?.public_url) return;
      try {
        await navigator.clipboard.writeText(selectedNote.value.public_url);
        copyStatus.value = 'copied';
        showToast('公开链接已复制！');
        setTimeout(() => { copyStatus.value = 'copy'; }, 2000);
      } catch (err) {
        showToast('复制失败', 'error');
      }
    };

    const openNewNoteEditor = () => {
      if (isEditing.value) {
        showConfirm('您正在编辑笔记，切换到新建笔记会丢失当前更改。确定要继续吗？').then(confirmed => {
          if (!confirmed) return;
          isEditing.value = false;
          selectedNote.value = {
            id: null, title: '未命名笔记', content: '', is_public: false, project: null,
            created_at: new Date().toLocaleString(), author: { id: initialData.user_id, username: initialData.username }
          };
          isEditing.value = true;
        });
      } else {
        selectedNote.value = {
          id: null, title: '未命名笔记', content: '', is_public: false, project: null,
          created_at: new Date().toLocaleString(), author: { id: initialData.user_id, username: initialData.username }
        };
        isEditing.value = true;
      }
    };

    watch(isEditing, (isNowEditing) => {
        if (isNowEditing) {
            nextTick(() => {
                loadTinyMCE();
            });
        } else {
            destroyEditor();
        }
    });

    onMounted(() => {
      const pathParts = window.location.pathname.split('/').filter(p => p);
      const noteIdFromUrl = (pathParts.length >= 2 && pathParts[0] === 'knowledge' && !isNaN(parseInt(pathParts[1], 10)))
        ? parseInt(pathParts[1], 10) : null;
      if (noteIdFromUrl) {
        selectNote(noteIdFromUrl);
      } else if (initialHasNotes.value && sidebarNotes.value.length > 0) {
        selectNote(sidebarNotes.value[0].id);
      }
    });

    return {
      sidebarNotes, selectedNoteId, selectedNote, searchQuery, isLoading, isEditing,
      isSidebarCollapsed, initialHasNotes, editorContainer, copyStatus, toast, confirmDialog,
      toggleSidebar, selectNote, searchNotes, updateNote, iconClass, startEditing, cancelEditing,
      copyPublicUrl,
      handleSearchClickWhenCollapsed: () => {
        if (isSidebarCollapsed.value) toggleSidebar();
        nextTick(() => { document.querySelector('.sidebar-search input')?.focus(); });
      },
      openNewNoteEditor
    };
  },
  delimiters: ['[[', ']]']
}).mount('#knowledge-app');

// 辅助函数
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