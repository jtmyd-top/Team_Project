<template>
  <div class="encrypted-note-content">
    <!-- 未验证提示 -->
    <el-alert
      v-if="showVerifyPrompt"
      title="需要验证身份"
      type="warning"
      description="此笔记是加密的，需要 2FA 验证后才能查看内容"
      closable
    />

    <!-- 解密中 -->
    <div v-if="isDecrypting" class="decrypting-state">
      <el-skeleton :rows="5" animated />
      <p style="text-align: center; color: #999; margin-top: 10px;">解密中...</p>
    </div>

    <!-- 已解密内容 -->
    <div v-else-if="decryptedContent" v-html="sanitizedDecryptedContent" class="note-content"></div>

    <!-- 错误信息 -->
    <el-alert
      v-if="decryptError"
      :title="decryptError"
      type="error"
      closable
      @close="clearDecryptError"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useEncryptedNoteContent } from '@/composables/useEncryptedNoteContent'
import { sanitizeHtml } from '@utils/sanitize'
import '@/assets/styles/components/encrypted-note-content.css'

const props = defineProps({
  noteId: {
    type: Number,
    required: true
  },
  encryptedContent: {
    type: String,
    required: true
  },
  isSecret: {
    type: Boolean,
    default: false
  }
})

const {
  decryptedContent,
  isDecrypting,
  decryptError,
  showVerifyPrompt,
  decryptContent,
  clearDecryptError
} = useEncryptedNoteContent(props)

const sanitizedDecryptedContent = computed(() => sanitizeHtml(decryptedContent.value || ''))

defineExpose({
  decryptContent
})
</script>
