/**
 * NoteEditor 逻辑层
 * 处理 TinyMCE 编辑器初始化、加密笔记解密、内容编辑等功能
 */

import { ref, watch, nextTick, computed, onUnmounted } from 'vue'
import { useVaultEncryption } from '@/composables/useVaultEncryption'
import { useClientCrypto } from '@/composables/useClientCrypto'

export function useNoteEditor(props, emit, editorElRef) {
  // ==================== 状态管理 ====================
  let editorInstance = null
  let isEditorReady = false
  let isUserEditing = false
  let autoSaveTimer = null

  // 获取加密状态和解密工具
  const { isKeyValid, dek, tryRecoverKeyFromSession } = useVaultEncryption()
  const { decryptContent } = useClientCrypto()

  // 是否正在初始化
  const isInitializing = ref(false)

  // 解密状态
  const isDecrypting = ref(false)
  const decryptError = ref('')

  // 存储解密后的标题和内容
  const decryptedTitle = ref('')
  const decryptedContent = ref('')

  // 本地标题状态（避免光标跳转）
  const localTitle = ref('')

  // ==================== 计算属性 ====================
  const displayTitle = computed(() => {
    if (!props.isSecret) {
      return props.modelValue.title || ''
    }

    if (isKeyValid.value && decryptedTitle.value) {
      return decryptedTitle.value
    }

    return props.modelValue.title || ''
  })

  const displayContent = computed(() => {
    if (!props.isSecret) {
      return props.modelValue.content || ''
    }

    if (isKeyValid.value && decryptedContent.value) {
      return decryptedContent.value
    }

    return props.modelValue.content || ''
  })

  // ==================== 解密逻辑 ====================
  async function decryptNoteContent() {
    if (!props.isSecret) {
      return
    }

    if (!props.modelValue.id || (!props.modelValue.title && !props.modelValue.content)) {
      return
    }

    if (!isKeyValid.value || !dek.value) {
      decryptError.value = '未能获取解密密钥，请进行 2FA 验证'
      return
    }

    isDecrypting.value = true
    decryptError.value = ''

    try {
      if (props.modelValue.title) {
        try {
          decryptedTitle.value = await decryptContent(props.modelValue.title, dek.value)
          console.log('[Vault] Title decrypted successfully')
        } catch (e) {
          console.warn('[Vault] Failed to decrypt title (might be plaintext):', e)
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

      localTitle.value = decryptedTitle.value || props.modelValue.title || ''
    } catch (e) {
      console.error('[Vault] Decryption error in editor:', e)
      decryptError.value = '解密失败: ' + e.message
    } finally {
      isDecrypting.value = false
    }
  }

  // ==================== TinyMCE 配置 ====================
  const getTinyMCEConfig = () => ({
    license_key: 'gpl',
    language: 'zh_CN',
    toolbar_mode: 'wrap',

    plugins: [
      'advlist', 'autolink', 'lists', 'link', 'image', 'charmap', 'preview', 'anchor',
      'searchreplace', 'visualblocks', 'code', 'fullscreen', 'insertdatetime', 'media',
      'table', 'wordcount', 'codesample', 'emoticons', 'quickbars', 'help',
      'nonbreaking', 'pagebreak', 'visualchars'
    ].join(' '),

    toolbar: [
      'undo redo | blocks fontfamily fontsize | bold italic underline strikethrough | forecolor backcolor',
      'alignleft aligncenter alignright alignjustify | bullist numlist | outdent indent | link image media table',
      'codesample customtodo customhr | pagebreak nonbreaking visualchars | removeformat fullscreen preview code'
    ],

    quickbars_selection_toolbar: 'bold italic | quicklink h2 h3 blockquote',
    quickbars_insert_toolbar: 'quickimage quicktable',

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

    block_formats: '段落=p; 标题1=h1; 标题2=h2; 标题3=h3; 标题4=h4; 引用=blockquote; 代码=pre',

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

    height: '100%',
    min_height: 600,
    resize: true,
    menubar: false,
    statusbar: true,
    elementpath: true,
    branding: false,
    promotion: false,

    init_instance_callback: (editor) => {
      console.log('TinyMCE init_instance_callback 触发, editor id:', editor.id)
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

    skin: props.isLightTheme ? 'oxide' : 'oxide-dark',
    content_css: props.isLightTheme ? 'default' : 'dark',

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

      editor.ui.registry.addButton('customhr', {
        icon: 'horizontal-rule',
        tooltip: '水平分割线',
        onAction: () => {
          editor.insertContent('<hr />')
        }
      })

      editor.ui.registry.addButton('customtodo', {
        icon: 'checkmark',
        tooltip: '插入待办事项',
        onAction: () => {
          editor.insertContent('<ul style="list-style-type: none; padding-left: 20px;"><li><input type="checkbox" /> 待办事项</li><li><input type="checkbox" /> 已完成事项</li></ul><p>&nbsp;</p>')
        }
      })

      editor.on('init', () => {
        console.log('TinyMCE init 事件触发')

        const initializeContent = (retryCount = 0) => {
          const maxRetries = 5

          try {
            const content = displayContent.value || ''
            console.log('正在设置内容到编辑器，内容长度:', content.length, '(isSecret:', props.isSecret, ', hasDecrypted:', !!decryptedContent.value, ')')

            editor.setContent(content)
            editor.getBody().innerHTML = content || '<p><br></p>'
            editor.setDirty(false)

            setTimeout(() => {
              const actualContent = editor.getContent()
              const bodyContent = editor.getBody().innerHTML
              console.log('验证 - getContent 长度:', actualContent.length, 'body 内容长度:', bodyContent.length)

              if (content.length > 0 && actualContent.length < 10 && retryCount < maxRetries) {
                console.warn(`内容设置失败，第 ${retryCount + 1} 次重试...`)
                setTimeout(() => initializeContent(retryCount + 1), 300)
                return
              }

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

        setTimeout(() => initializeContent(), 200)
      })

      const handleContentChange = () => {
        if (!isEditorReady) {
          console.log('编辑器尚未准备好，忽略内容变化事件')
          return
        }
        isUserEditing = true
        emit('change', editor.getContent())
        clearTimeout(autoSaveTimer)
        autoSaveTimer = setTimeout(() => {
          const content = editor.getContent()
          localStorage.setItem(`note-draft-${props.modelValue.id || 'new'}`, content)
        }, 30000)
      }

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

  // ==================== 编辑器操作 ====================
  const initEditor = () => {
    if (!window.tinymce || !editorElRef.value) return

    window.tinymce.init({
      target: editorElRef.value,
      ...getTinyMCEConfig()
    })
  }

  const destroyEditor = () => {
    if (editorInstance) {
      editorInstance.remove()
      editorInstance = null
    }
  }

  const getContent = () => {
    return editorInstance ? editorInstance.getContent() : ''
  }

  const setContent = (content) => {
    if (editorInstance) {
      editorInstance.setContent(content || '')
    }
  }

  const getCurrentTitle = () => {
    return localTitle.value
  }

  const updateTitle = () => {
    emit('update:modelValue', {
      ...props.modelValue,
      title: localTitle.value
    })
    if (isEditorReady && editorInstance) {
      emit('change', editorInstance.getContent())
    }
  }

  // ==================== 监听器 ====================
  watch(() => props.modelValue.id, (newId, oldId) => {
    if (newId !== oldId && editorInstance) {
      isUserEditing = false
      decryptedContent.value = ''
      decryptedTitle.value = ''
      decryptError.value = ''

      if (props.isSecret && isKeyValid.value) {
        decryptNoteContent()
      } else {
        const content = props.modelValue.content || ''
        localTitle.value = props.modelValue.title || ''
        console.log('笔记切换，更新编辑器内容，新笔记 ID:', newId, '内容长度:', content.length)
        editorInstance.setContent(content)
        editorInstance.setDirty(false)
      }
    }
  })

  watch(() => isKeyValid.value, (valid) => {
    if (valid && isInitializing.value) {
      isInitializing.value = false
    }

    if (valid && props.isSecret && props.modelValue.content && !decryptedContent.value) {
      decryptNoteContent()
    }
  })

  watch(() => displayContent.value, (newContent) => {
    if (isUserEditing) {
      return
    }
    if (newContent && editorInstance && isEditorReady) {
      const currentContent = editorInstance.getContent()
      if (!currentContent || currentContent === props.modelValue.content) {
        console.log('[Vault] displayContent updated, setting decrypted content to editor', {
          newLength: newContent.length,
          currentLength: currentContent.length
        })
        editorInstance.setContent(newContent)
        editorInstance.setDirty(false)
      }
    }
  })

  watch(() => props.modelValue.content, (newContent, oldContent) => {
    if (editorInstance && newContent !== oldContent) {
      if (!isEditorReady) {
        console.log('编辑器尚未准备好，跳过 watch 更新')
        return
      }

      if (newContent && newContent.length > 0) {
        const currentEditorContent = editorInstance.getContent()
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

  watch(() => props.isLightTheme, (isLight) => {
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

  // ==================== 生命周期 ====================
  onUnmounted(() => {
    isEditorReady = false
    isInitializing.value = false
    destroyEditor()
  })

  // ==================== 返回 ====================
  return {
    isInitializing,
    isDecrypting,
    decryptError,
    localTitle,
    displayTitle,
    displayContent,
    isKeyValid,
    initEditor,
    destroyEditor,
    getContent,
    setContent,
    getCurrentTitle,
    updateTitle,
    decryptNoteContent
  }
}
