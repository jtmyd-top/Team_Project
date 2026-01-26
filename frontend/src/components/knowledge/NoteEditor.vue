<template>
  <div class="note-editor">
    <!-- 加密状态指示器 -->
    <div v-if="isSecret" class="encryption-indicator">
      <el-tag type="success">
        <el-icon>
          <Lock />
        </el-icon>
        加密笔记
      </el-tag>
      <span class="indicator-text">
        {{ isKeyValid ? '已解锁，可编辑' : '未解锁，请先进行 2FA 验证' }}
      </span>
    </div>

    <!-- 解密错误提示 -->
    <div v-if="decryptError" class="decrypt-error">
      <el-alert
        :title="decryptError"
        type="error"
        closable
        @close="decryptError = ''"
        style="margin-bottom: 15px;"
      />
    </div>

    <!-- 解密中的加载状态 -->
    <div v-if="isSecret && isDecrypting" class="decrypting-prompt">
      <el-alert
        title="解密中"
        type="info"
        description="正在解密笔记内容，请稍候..."
        :closable="false"
        style="margin-bottom: 15px;"
      />
    </div>

    <!-- 编辑器初始化中 -->
    <div v-if="isInitializing" class="decrypting-prompt">
      <el-alert
        title="编辑器初始化中"
        type="info"
        description="正在加载编辑器，请稍候..."
        :closable="false"
        style="margin-bottom: 15px;"
      />
    </div>

    <!-- 编辑器（已解密或非加密笔记时显示） -->
    <div v-if="!isInitializing && (!isSecret || isKeyValid)" class="editor-content">
      <input
        :value="displayTitle"
        @input="updateTitle"
        class="title-input"
        placeholder="笔记标题"
        :disabled="isSecret && isDecrypting"
      />
      <div class="editor-wrapper">
        <textarea ref="editorElRef"></textarea>
      </div>
    </div>

    <!-- 加密笔记未解锁提示 -->
    <div v-else-if="isSecret && !isKeyValid && !isInitializing" class="locked-prompt">
      <el-alert
        title="笔记已加密"
        type="warning"
        description="此笔记已加密。请完成 2FA 验证后编辑内容。"
        :closable="false"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import { Lock } from '@element-plus/icons-vue'
import { ElTag, ElIcon } from 'element-plus'
import { useVaultEncryption } from '@/composables/useVaultEncryption'
import { useClientCrypto } from '@/composables/useClientCrypto'

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
  },
  isSecret: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'ready', 'change'])

const editorElRef = ref(null)
let editorInstance = null
let isEditorReady = false

// 获取加密状态和解密工具
const { isKeyValid, dek, tryRecoverKeyFromSession } = useVaultEncryption()
const { decryptContent } = useClientCrypto()

// 是否正在初始化
const isInitializing = ref(false)

// 存储解密后的标题和内容
const decryptedTitle = ref('')
const decryptedContent = ref('')

/**
 * 计算属性：响应式解密后的标题
 */
const displayTitle = computed(() => {
  if (!props.isSecret) {
    return props.modelValue.title || ''
  }

  if (isKeyValid.value && decryptedTitle.value) {
    return decryptedTitle.value
  }

  return props.modelValue.title || ''
})

/**
 * 计算属性：响应式解密后的内容
 */
const displayContent = computed(() => {
  if (!props.isSecret) {
    return props.modelValue.content || ''
  }

  if (isKeyValid.value && decryptedContent.value) {
    return decryptedContent.value
  }

  return props.modelValue.content || ''
})

/**
 * 解密加密笔记的标题和内容
 */
async function decryptNoteContent() {
  if (!props.isSecret) {
    return
  }

  // 检查是否有必要的信息
  if (!props.modelValue.id || (!props.modelValue.title && !props.modelValue.content)) {
    return
  }

  // 如果没有有效的 DEK，不能解密
  if (!isKeyValid.value || !dek.value) {
    decryptError.value = '未能获取解密密钥，请进行 2FA 验证'
    return
  }

  isDecrypting.value = true
  decryptError.value = ''

  try {
    // 【新增】同时解密 title 和 content
    if (props.modelValue.title) {
      try {
        decryptedTitle.value = await decryptContent(props.modelValue.title, dek.value)
        console.log('[Vault] Title decrypted successfully')
      } catch (e) {
        console.warn('[Vault] Failed to decrypt title (might be plaintext):', e)
        // title 可能是明文，不是错误
        decryptedTitle.value = props.modelValue.title
      }
    }

    if (props.modelValue.content) {
      try {
        decryptedContent.value = await decryptContent(props.modelValue.content, dek.value)
        console.log('[Vault] Content decrypted successfully')
      } catch (e) {
        console.error('[Vault] Failed to decrypt content:', e)
        decryptError.value = '解密失败，无法编辑此加密笔记'
        throw e
      }
    }
  } catch (e) {
    console.error('[Vault] Decryption error in editor:', e)
    decryptError.value = '解密失败: ' + e.message
  } finally {
    isDecrypting.value = false
  }
}

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
    // 笔记切换，重置解密状态
    decryptedContent.value = ''
    decryptError.value = ''

    // 如果新笔记是加密的，需要重新解密
    if (props.isSecret && isKeyValid.value) {
      decryptNoteContent()
    } else {
      // 普通笔记或未解锁的加密笔记
      const content = props.modelValue.content || ''
      console.log('笔记切换，更新编辑器内容，新笔记 ID:', newId, '内容长度:', content.length)
      editorInstance.setContent(content)
      editorInstance.setDirty(false)
    }
  }
})

/**
 * 监听 isKeyValid 变化：
 * 当保险柜解锁时（从 false 变为 true），
 * 如果当前编辑的是加密笔记，立即解密
 */
watch(() => isKeyValid.value, (valid) => {
  // 如果密钥刚刚变有效，停止初始化加载
  if (valid && isInitializing.value) {
    isInitializing.value = false
  }

  if (valid && props.isSecret && props.modelValue.content && !decryptedContent.value) {
    // 密钥刚刚变有效，解密当前笔记
    decryptNoteContent()
  }
})

/**
 * 监听 displayContent 变化，当解密完成时更新编辑器
 */
watch(() => displayContent.value, (newContent) => {
  if (newContent && editorInstance && isEditorReady) {
    const currentContent = editorInstance.getContent()
    // 只在编辑器内容为空或与原加密内容相同时更新
    if (!currentContent || currentContent === props.modelValue.content) {
      console.log('解密完成，更新编辑器内容，长度:', newContent.length)
      editorInstance.setContent(newContent)
      editorInstance.setDirty(false)
    }
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

onMounted(async () => {
  isInitializing.value = true

  // 如果是加密笔记但 DEK 不可用，尝试从 session 恢复
  if (props.isSecret && !isKeyValid.value && !dek.value) {
    console.log('[Vault] NoteEditor: DEK not available, attempting to recover from session')
    const recovered = await tryRecoverKeyFromSession()
    if (recovered) {
      console.log('[Vault] NoteEditor: DEK recovered from session')
    } else {
      console.warn('[Vault] NoteEditor: Failed to recover DEK from session')
    }
  }

  // 等待 TinyMCE 加载完成
  const checkTinyMCE = () => {
    if (window.tinymce) {
      isInitializing.value = false
      initEditor()
      // 编辑器初始化完成后，如果是加密笔记且已解锁，立即解密
      setTimeout(() => {
        if (props.isSecret && isKeyValid.value && props.modelValue.content) {
          decryptNoteContent()
        }
      }, 500)
    } else {
      setTimeout(checkTinyMCE, 100)
    }
  }
  checkTinyMCE()
})

onUnmounted(() => {
  // 重置标志，确保下次挂载时正确初始化
  isEditorReady = false
  isInitializing.value = false
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

.encryption-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 15px;
  background-color: #f0f9ff;
  border: 1px solid #b3d8ff;
  border-radius: 4px;
  margin-bottom: 15px;
  font-size: 13px;
  color: #0084f4;
}

.encryption-indicator :deep(.el-tag) {
  background-color: transparent;
  border-color: #b3d8ff;
  color: #0084f4;
}

.encryption-indicator :deep(.el-icon) {
  margin-right: 5px;
}

.indicator-text {
  color: #0084f4;
  font-size: 12px;
  opacity: 0.8;
}

.decrypt-error {
  margin-bottom: 15px;
}

.decrypting-prompt {
  margin-bottom: 15px;
}

.locked-prompt {
  padding: 20px;
  text-align: center;
}

.editor-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 600px;
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
