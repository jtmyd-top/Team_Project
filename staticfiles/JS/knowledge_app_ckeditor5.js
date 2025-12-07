/**
 * static/JS/knowledge_app.js
 * Knowledge Notes: CKEditor 5 升级版核心逻辑 - 侧边栏交互与状态持久化最终优化 (Focus on Sidebar State & Reactivity)
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
    const ckeditorConfig = initialData.ckeditor_config || {};
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

    // --- computed property for icon class ---
    const iconClass = computed(() => {
      return isSidebarCollapsed.value ? 'fas fa-chevron-left':'fas fa-chevron-right' ;
    });

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
      // 1. 更新 isSidebarCollapsed 的值
      isSidebarCollapsed.value = !isSidebarCollapsed.value;
      // 2. 保存到 localStorage
      localStorage.setItem('isSidebarCollapsed', isSidebarCollapsed.value);

      // 3. 处理编辑器和侧边栏折叠的联动
      if (isEditing.value) {
        // 使用 nextTick 确保 DOM 更新后再操作
        nextTick(() => {
          if (isSidebarCollapsed.value) {
            // 如果侧边栏被折叠了，且编辑器是打开的，销毁编辑器实例
            // 这是为了避免折叠后编辑器显示异常或占用资源

            if (editorInstance) {
              editorInstance.destroy().catch(() => {});
              // chevronElement.className = "fas fa-chevron-left";

              loadEditor();
            }
          } else {
            // chevronElement.className = "fas fa-chevron-right";
            // 如果侧边栏展开了，且编辑器不存在，则重新初始化
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

     // --- 【核心修改】在这里定义一个与 settings.py 完全一致的完整配置 ---
    const getFullCkeditorConfig = () => {
      // 从 settings.py 手动“翻译”过来的自定义颜色面板
      const customColorPalette = [
        { color: 'hsl(4, 90%, 58%)', label: 'Red' }, { color: 'hsl(340, 82%, 52%)', label: 'Pink' },
        { color: 'hsl(291, 64%, 42%)', label: 'Purple' }, { color: 'hsl(262, 52%, 47%)', label: 'Deep Purple' },
        { color: 'hsl(231, 48%, 48%)', label: 'Indigo' }, { color: 'hsl(207, 90%, 54%)', label: 'Blue' },
        { color: 'hsl(120, 73%, 45%)', label: 'Green' }, { color: 'hsl(50, 95%, 55%)', label: 'Yellow' },
        { color: 'hsl(25, 95%, 53%)', label: 'Orange' }, { color: 'hsl(0, 0%, 20%)', label: 'Dark Gray' },
        { color: 'hsl(0, 0%, 60%)', label: 'Light Gray' },
      ];
      return {
        language: 'zh-cn',
        //licenseKey:'eyJhbGciOiJFUzI1NiJ9.eyJleHAiOjE3NTYwNzk5OTksImp0aSI6Ijk4YTUyNzkzLTc4NTctNDU1MC04YjY1LTNmZmYzZTRmMDA5YSIsInVzYWdlRW5kcG9pbnQiOiJodHRwczovL3Byb3h5LWV2ZW50LmNrZWRpdG9yLmNvbSIsImRpc3RyaWJ1dGlvbkNoYW5uZWwiOlsiY2xvdWQiLCJkcnVwYWwiLCJzaCJdLCJ3aGl0ZUxhYmVsIjp0cnVlLCJsaWNlbnNlVHlwZSI6InRyaWFsIiwiZmVhdHVyZXMiOlsiKiJdLCJ2YyI6IjkzYjA1YWYxIn0.YVkqzGBtrO1ZJaX3JgkqQT5Xaz6ent1czzUoEMXGlaBJqnPLaIc3Id7U38EFCK2hQ4jOLnKXBUuhk4DnDMKq3A',
        licensekey:'GPL',
        toolbar: {
          items: [
            // 这次我们把所有按钮都加上
            'sourceEditing', '|', 'findAndReplace', 'selectAll', '|',
            'heading', '|', 'bold', 'italic', 'underline', 'strikethrough', 'removeFormat', '|',
            'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor', 'highlight', '|',
            'alignment', '|', 'outdent', 'indent', '|',
            'bulletedList', 'numberedList', 'todoList', 'blockQuote', '|',
            'link', 'imageUpload', 'insertTable', 'mediaEmbed', 'horizontalLine', 'specialCharacters', 'pageBreak'
          ],
          shouldNotGroupWhenFull: true
        },
        image: {
          toolbar: [ 'imageTextAlternative', '|', 'imageStyle:alignLeft', 'imageStyle:alignRight', 'imageStyle:alignCenter', 'imageStyle:side', '|', 'linkImage' ]
        },
        table: {
          contentToolbar: [ 'tableColumn', 'tableRow', 'mergeTableCells', 'tableProperties', 'tableCellProperties' ],
          // 为表格也应用颜色配置
          tableProperties: { borderColors: customColorPalette, backgroundColors: customColorPalette },
          tableCellProperties: { borderColors: customColorPalette, backgroundColors: customColorPalette }
        },
        heading: {
          options: [
            { model: 'paragraph', title: 'Paragraph', class: 'ck-heading_paragraph' },
            { model: 'heading1', view: 'h1', title: 'Heading 1', class: 'ck-heading_heading1' },
            { model: 'heading2', view: 'h2', title: 'Heading 2', class: 'ck-heading_heading2' },
            { model: 'heading3', view: 'h3', title: 'Heading 3', class: 'ck-heading_heading3' },
            { model: 'heading4', view: 'h4', title: 'Heading 4', class: 'ck-heading_heading4' },
          ]
        },
        // 添加字体颜色、背景色和对齐的详细配置
        fontColor: { colors: customColorPalette },
        fontBackgroundColor: { colors: customColorPalette },
        alignment: { options: ['left', 'right', 'center', 'justify'] },

        // 图片上传配置
        simpleUpload: {
          uploadUrl: '/ckeditor5/upload/', // 确保这个 URL 在你的项目中是可用的
          headers: { 'X-CSRFToken': csrfToken }
        }
      };
    };

     // --- CKEditor 加载函数 (保持不变) ---
    const loadEditor = async () => {
      // 检查 CDN 是否已加载 ClassicEditor
      if (typeof ClassicEditor === 'undefined') {
        // 如果你的 HTML 中确定已经包含了 CDN <script> 标签，这里就不应该触发
        console.error("ClassicEditor is not defined. Ensure the CKEditor 5 CDN script is loaded before this script runs.");
        // 你可以在这里添加一个用户提示
        return;
      }
      try {
        // 使用我们上面定义的、功能齐全的配置
        console.log(editorContainer.value)
        editorInstance = await ClassicEditor.create(editorContainer.value, getFullCkeditorConfig());

        if (selectedNote.value) {
          editorInstance.setData(selectedNote.value.content || '');
        }
      } catch (error) {
        console.error("CKEditor 5 initialization error:", error);
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
      isSidebarCollapsed, // <--- 确保 isSidebarCollapsed 被暴露
      initialHasNotes,
      editorContainer, // 暴露编辑器容器的 ref
      copyStatus,
      toast,
      confirmDialog,
      toggleSidebar,
      selectNote,
      searchNotes,
      updateNote,
      iconClass,
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