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
    <template v-if="!isInitializing && (!isSecret || isKeyValid)">
      <input
        v-model="localTitle"
        @input="updateTitle"
        class="title-input"
        placeholder="笔记标题"
        :disabled="isSecret && isDecrypting"
      />
      <textarea ref="editorElRef"></textarea>
    </template>

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
import { ref, onMounted, nextTick } from 'vue'
import { Lock } from '@element-plus/icons-vue'
import { ElAlert, ElTag, ElIcon } from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/tag/style/css'
import 'element-plus/es/components/icon/style/css'
import { useNoteEditor } from '@composables/useNoteEditor'
import '@/assets/styles/components/note-editor.css'

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

const {
  isInitializing,
  isDecrypting,
  decryptError,
  localTitle,
  displayTitle,
  displayContent,
  isKeyValid,
  tryRecoverKeyFromSession,
  decryptedTitle,
  decryptedContent,
  initEditor,
  destroyEditor,
  getContent,
  setContent,
  getCurrentTitle,
  updateTitle,
  decryptNoteContent
} = useNoteEditor(props, emit, editorElRef)

onMounted(async () => {
  isInitializing.value = true

  localTitle.value = props.modelValue.title || ''

  try {
    if (props.isSecret) {
      console.log('[Vault] NoteEditor: Secret note detected, checking vault...', {
        isKeyValid: isKeyValid.value
      })

      if (!isKeyValid.value) {
        console.log('[Vault] NoteEditor: Vault locked, attempting to recover from session')
        const recovered = await tryRecoverKeyFromSession()
        console.log('[Vault] NoteEditor: Recovery attempt completed', {
          recovered,
          isKeyValidAfter: isKeyValid.value
        })
      }

      if (isKeyValid.value && props.modelValue.content) {
        console.log('[Vault] NoteEditor: Starting decryption...')
        await decryptNoteContent()
        console.log('[Vault] NoteEditor: Decryption completed', {
          decryptedTitleLength: decryptedTitle.value.length,
          decryptedContentLength: decryptedContent.value.length
        })
      } else {
        console.warn('[Vault] NoteEditor: Cannot decrypt - vault locked or no content', {
          isKeyValid: isKeyValid.value,
          hasContent: !!props.modelValue.content
        })
      }
    }
  } catch (e) {
    console.error('[Vault] NoteEditor onMounted error:', e)
  }

  const checkTinyMCE = () => {
    if (window.tinymce) {
      isInitializing.value = false
      // 等一帧让 <textarea v-if> 渲染出来，否则 editorElRef.value 还是 null，
      // initEditor 内部会因 !editorElRef.value 静默 return，编辑器不挂载
      nextTick(() => initEditor())
    } else {
      setTimeout(checkTinyMCE, 100)
    }
  }
  checkTinyMCE()
})

defineExpose({
  getContent,
  setContent,
  getEditor: () => editorInstance,
  getCurrentTitle
})
</script>
