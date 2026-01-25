<template>
  <div class="note-editor">
    <input
      :value="modelValue.title"
      @input="updateTitle"
      class="title-input"
      placeholder="笔记标题"
    />
    <div class="editor-wrapper">
      <textarea ref="editorElRef"></textarea>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
    default: () => ({ title: '', content: '' })
  },
  isLightTheme: {
    type: Boolean,
    default: true
  },
  csrfToken: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'ready', 'change'])

const editorElRef = ref(null)
let editorInstance = null
let isEditorReady = false  // 标记编辑器是否已完成初始化并设置了内容

// 获取 TinyMCE 配置
const getTinyMCEConfig = () => ({
  license_key: 'gpl',
  language: 'zh_CN',
  toolbar_mode: 'wrap',

  // 插件配置
  plugins: [
    'advlist',
    'autolink',
    'lists',
    'link',
    'image',
    'charmap',
    'preview',
    'anchor',
    'searchreplace',
    'visualblocks',
    'code',
    'fullscreen',
    'insertdatetime',
    'media',
    'table',
    'wordcount',
    'codesample',
    'emoticons',
    'quickbars',
    'help',
    'nonbreaking',
    'pagebreak',
    'visualchars'
  ].join(' '),

  // 工具栏配置 - 三行布局
  toolbar: [
    'undo redo | blocks fontfamily fontsize | bold italic underline strikethrough | forecolor backcolor',
    'alignleft aligncenter alignright alignjustify | bullist numlist | outdent indent | link image media table',
    'codesample customtodo customhr | pagebreak nonbreaking visualchars | removeformat fullscreen preview code'
  ],

  // 快速工具栏
  quickbars_selection_toolbar: 'bold italic | quicklink h2 h3 blockquote',
  quickbars_insert_toolbar: 'quickimage quicktable',

  // 代码示例支持的语言
  codesample_languages: [
    { text: 'HTML/XML', value: 'markup' },
    { text: 'JavaScript', value: 'javascript' },
    { text: 'CSS', value: 'css' },
    { text: 'Python', value: 'python' },
    { text: 'Java', value: 'java' },
    { text: 'C/C++', value: 'c' },
    { text: 'SQL', value: 'sql' },
    { text: 'Bash', value: 'bash' },
    { text: 'JSON', value: 'json' },
    { text: 'TypeScript', value: 'typescript' }
  ],

  // 格式选项
  block_formats: '段落=p; 标题1=h1; 标题2=h2; 标题3=h3; 标题4=h4; 引用=blockquote; 代码=pre',

  // 字体选项
  font_family_formats: `
    系统默认=-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    微软雅黑="Microsoft YaHei","Helvetica Neue","PingFang SC",sans-serif;
    苹方="PingFang SC","Helvetica Neue",sans-serif;
    思源黑体="Source Han Sans CN","Noto Sans CJK SC",sans-serif;
    宋体=SimSun,serif;
    思源宋体="Source Han Serif CN","Noto Serif CJK SC",serif;
    黑体=SimHei,sans-serif;
    楷体=KaiTi,STKaiti,serif;
    仿宋=FangSong,STFangsong,serif;
    Arial=arial,helvetica,sans-serif;
    Helvetica=helvetica,arial,sans-serif;
    Times New Times=times new roman,times,serif;
    Georgia=georgia,palatino,serif;
    Courier New=courier new,courier,monospace;
    Monaco=monaco,consolas,courier new,monospace;
    Consolas=consolas,courier new,monospace;
    字体 Awesome=Font Awesome 6 Free,fa-solid
  `.replace(/\s+/g, ''),

  // 图片上传配置
  images_upload_url: '/api/upload/image/',
  automatic_uploads: true,
  file_picker_types: 'image',
  images_upload_handler: (blobInfo, progress) => new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/upload/image/')

    const csrfToken = props.csrfToken ||
      document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
    xhr.setRequestHeader('X-CSRFToken', csrfToken)

    xhr.upload.onprogress = (e) => {
      progress(e.loaded / e.total * 100)
    }

    xhr.onload = () => {
      if (xhr.status === 403) {
        reject({ message: '请先登录', remove: true })
        return
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        reject('图片上传失败: ' + xhr.status)
        return
      }
      const json = JSON.parse(xhr.responseText)
      if (!json || !json.location) {
        reject('无效的响应: ' + xhr.responseText)
        return
      }
      resolve(json.location)
    }

    xhr.onerror = () => {
      reject('网络错误，图片上传失败')
    }

    const formData = new FormData()
    formData.append('file', blobInfo.blob(), blobInfo.filename())
    xhr.send(formData)
  }),

  // 其他配置
  height: '100%',
  min_height: 600,
  resize: true,
  menubar: false,
  statusbar: true,
  elementpath: true,
  branding: false,
  promotion: false,

  // 初始化完成回调 - 作为备用初始化方法
  init_instance_callback: (editor) => {
    console.log('TinyMCE init_instance_callback 触发, editor id:', editor.id)
    // 如果 init 事件没有正确设置内容，这里作为备用
    setTimeout(() => {
      if (!isEditorReady) {
        console.log('init_instance_callback: isEditorReady 仍为 false，尝试设置内容')
        const content = props.modelValue.content || ''
        if (content) {
          editor.setContent(content)
          editor.getBody().innerHTML = content
          editor.setDirty(false)
          isEditorReady = true
          emit('ready', editor)
        }
      }
    }, 500)
  },

  // 主题适配
  skin: props.isLightTheme ? 'oxide' : 'oxide-dark',
  content_css: props.isLightTheme ? 'default' : 'dark',

  // 内容样式
  content_style: `
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 16px;
      line-height: 1.6;
      padding: 16px;
    }
    pre { background: #f4f4f4; padding: 12px; border-radius: 6px; overflow-x: auto; }
    code { background: #f0f0f0; padding: 2px 6px; border-radius: 4px; font-family: monospace; }
    blockquote { border-left: 4px solid #ddd; margin: 16px 0; padding-left: 16px; color: #666; }
    table { border-collapse: collapse; width: 100%; }
    table td, table th { border: 1px solid #ddd; padding: 8px; }
    img { max-width: 100%; height: auto; border-radius: 8px; }
  `,

  setup: (editor) => {
    editorInstance = editor

    // 添加自定义分割线按钮
    editor.ui.registry.addButton('customhr', {
      icon: 'horizontal-rule',
      tooltip: '水平分割线',
      onAction: () => {
        editor.insertContent('<hr />')
      }
    })

    // 添加自定义待办清单按钮
    editor.ui.registry.addButton('customtodo', {
      icon: 'checkmark',
      tooltip: '插入待办事项',
      onAction: () => {
        editor.insertContent('<ul style="list-style-type: none; padding-left: 20px;"><li><input type="checkbox" /> 待办事项</li><li><input type="checkbox" /> 已完成事项</li></ul><p>&nbsp;</p>')
      }
    })

    // 使用 init 事件确保编辑器完全准备好后再设置内容
    // init 比 PostRender 更可靠，在编辑器完全可用时触发
    editor.on('init', () => {
      console.log('TinyMCE init 事件触发')

      // 内容初始化函数
      const initializeContent = (retryCount = 0) => {
        const maxRetries = 5

        try {
          // 在回调中重新读取 props.modelValue.content，确保获取最新值
          const content = props.modelValue.content || ''
          console.log('正在设置内容到编辑器，内容长度:', content.length)

          // 使用 setContent 设置内容
          editor.setContent(content)

          // 强制刷新编辑器视图
          editor.getBody().innerHTML = content || '<p><br></p>'

          // 重置脏状态
          editor.setDirty(false)

          // 延迟验证内容是否正确设置
          setTimeout(() => {
            const actualContent = editor.getContent()
            const bodyContent = editor.getBody().innerHTML
            console.log('验证 - getContent 长度:', actualContent.length, 'body 内容长度:', bodyContent.length)

            // 如果内容设置失败（有内容但编辑器为空），重试
            if (content.length > 0 && actualContent.length < 10 && retryCount < maxRetries) {
              console.warn(`内容设置失败，第 ${retryCount + 1} 次重试...`)
              setTimeout(() => initializeContent(retryCount + 1), 300)
              return
            }

            // 标记编辑器已准备好
            isEditorReady = true
            console.log('编辑器初始化完成，isEditorReady =', isEditorReady)
            emit('ready', editor)
          }, 100)
        } catch (e) {
          console.error('设置编辑器内容时出错:', e)
          if (retryCount < maxRetries) {
            setTimeout(() => initializeContent(retryCount + 1), 300)
          }
        }
      }

      // 延迟初始化，确保编辑器 DOM 完全渲染
      setTimeout(() => initializeContent(), 200)
    })

    // 内容变化时通知父组件 - 监听多种事件确保捕获所有变化
    let autoSaveTimer = null
    const handleContentChange = () => {
      // 只有在编辑器完全准备好后才发出变化事件
      // 防止初始化期间的事件触发导致内容被覆盖
      if (!isEditorReady) {
        console.log('编辑器尚未准备好，忽略内容变化事件')
        return
      }
      emit('change', editor.getContent())
      clearTimeout(autoSaveTimer)
      autoSaveTimer = setTimeout(() => {
        const content = editor.getContent()
        localStorage.setItem(`note-draft-${props.modelValue.id || 'new'}`, content)
      }, 30000)
    }

    // 监听多种事件以确保捕获所有内容变化
    // dirty 事件是 TinyMCE 最可靠的内容变化检测
    editor.on('dirty', handleContentChange)
    editor.on('input', handleContentChange)
    editor.on('change', handleContentChange)
    editor.on('keyup', handleContentChange)
    editor.on('keydown', handleContentChange)
    editor.on('paste', handleContentChange)
    editor.on('cut', handleContentChange)
    editor.on('undo', handleContentChange)
    editor.on('redo', handleContentChange)
    editor.on('ExecCommand', handleContentChange)
  }
})

// 初始化编辑器
const initEditor = () => {
  if (!window.tinymce || !editorElRef.value) return

  window.tinymce.init({
    target: editorElRef.value,
    ...getTinyMCEConfig()
  })
}

// 销毁编辑器
const destroyEditor = () => {
  if (editorInstance) {
    editorInstance.remove()
    editorInstance = null
  }
}

// 获取编辑器内容
const getContent = () => {
  return editorInstance ? editorInstance.getContent() : ''
}

// 设置编辑器内容
const setContent = (content) => {
  if (editorInstance) {
    editorInstance.setContent(content || '')
  }
}

// 更新标题
const updateTitle = (e) => {
  emit('update:modelValue', {
    ...props.modelValue,
    title: e.target.value
  })
  // 标题变化也触发 change 事件，但需要检查编辑器是否准备好
  if (isEditorReady && editorInstance) {
    emit('change', editorInstance.getContent())
  }
}

// 监听笔记 ID 变化，当切换笔记时更新编辑器内容
watch(() => props.modelValue.id, (newId, oldId) => {
  if (newId !== oldId && editorInstance) {
    // 笔记切换，更新编辑器内容
    const content = props.modelValue.content || ''
    console.log('笔记切换，更新编辑器内容，新笔记 ID:', newId, '内容长度:', content.length)
    editorInstance.setContent(content)
    // 强制刷新 DOM
    if (editorInstance.getBody()) {
      editorInstance.getBody().innerHTML = content || '<p><br></p>'
    }
    editorInstance.setDirty(false)
  }
})

// 监听内容变化（从外部更新时同步到编辑器）
// 这个 watch 确保在数据异步加载完成后能够更新编辑器
watch(() => props.modelValue.content, (newContent, oldContent) => {
  // 只在内容确实变化且编辑器存在时更新
  if (editorInstance && newContent !== oldContent) {
    // 如果编辑器还没准备好，不要更新（PostRender 会处理）
    if (!isEditorReady) {
      console.log('编辑器尚未准备好，跳过 watch 更新')
      return
    }

    // 重要：不要用空内容覆盖已有内容
    // 只有当新内容非空时才更新
    if (newContent && newContent.length > 0) {
      const currentEditorContent = editorInstance.getContent()
      // 只有当编辑器内容为空或与旧内容相同时才更新
      // 避免覆盖用户正在编辑的内容
      if (!currentEditorContent || currentEditorContent === oldContent || currentEditorContent === '') {
        console.log('外部内容更新，同步到编辑器，新内容长度:', newContent.length)
        editorInstance.setContent(newContent)
        editorInstance.setDirty(false)
      }
    } else {
      console.log('忽略空内容更新，保持编辑器现有内容')
    }
  }
})

// 监听主题变化
watch(() => props.isLightTheme, (isLight) => {
  // 主题变化需要重新初始化编辑器才能生效
  const currentContent = getContent()
  destroyEditor()
  nextTick(() => {
    initEditor()
    if (currentContent) {
      nextTick(() => {
        setContent(currentContent)
      })
    }
  })
})

onMounted(() => {
  // 等待 TinyMCE 加载完成
  const checkTinyMCE = () => {
    if (window.tinymce) {
      initEditor()
    } else {
      setTimeout(checkTinyMCE, 100)
    }
  }
  checkTinyMCE()
})

onUnmounted(() => {
  // 重置标志，确保下次挂载时正确初始化
  isEditorReady = false
  destroyEditor()
})

defineExpose({
  getContent,
  setContent,
  getEditor: () => editorInstance
})
</script>

<style scoped>
.note-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.title-input {
  width: 100%;
  font-size: 32px;
  font-weight: 700;
  border: none;
  background: transparent;
  color: var(--k-text, #1a1a1a);
  margin-bottom: 20px;
  outline: none;
  padding: 0;
}

.title-input::placeholder {
  color: var(--k-text-sec, #666);
  opacity: 0.5;
}

.editor-wrapper {
  flex: 1;
  min-height: 600px;
  border: 1px solid var(--k-border, #e0e0e0);
  border-radius: 8px;
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
}

/* 修复 TinyMCE iframe 的 position: absolute 导致的高度塌陷 */
.editor-wrapper :deep(.tox-tinymce) {
  height: 100% !important;
  min-height: 600px;
  display: flex !important;
  flex-direction: column !important;
}

.editor-wrapper :deep(.tox-editor-container) {
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
}

.editor-wrapper :deep(.tox-sidebar-wrap) {
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
}

.editor-wrapper :deep(.tox-edit-area) {
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
}

.editor-wrapper :deep(.tox-edit-area__iframe) {
  position: static !important; /* 覆盖 skin.min.css 的 position: absolute */
  flex: 1 !important;
}
</style>
