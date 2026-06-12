<template>
  <!-- 加密笔记未解锁提示 -->
  <div v-if="props.isSecret && !isKeyValid" class="encrypted-prompt">
    <el-alert
      title="保密笔记"
      type="warning"
      description="此笔记已加密。请完成 2FA 验证后查看内容。"
      :closable="false"
    />
  </div>

  <!-- 加密笔记解密中 -->
  <div v-else-if="isDecrypting" class="decrypting-state">
    <el-skeleton :rows="5" animated />
    <p style="text-align: center; color: #999; margin-top: 10px;">解密中...</p>
  </div>

  <!-- 解密错误提示 -->
  <div v-else-if="decryptError" class="decrypt-error">
    <el-alert
      :title="decryptError"
      type="error"
      closable
      @close="decryptError = ''"
    />
  </div>

  <!-- 已解密或非加密笔记 -->
  <div v-else ref="contentRef" class="note-viewer note-prose"></div>
</template>

<script setup>
import { ElAlert, ElSkeleton } from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/skeleton/style/css'
import { useNoteViewer } from '@/composables/useNoteViewer'
import '@/assets/styles/components/note-viewer.css'

const props = defineProps({
  content: {
    type: String,
    default: ''
  },
  isSecret: {
    type: Boolean,
    default: false
  },
  noteId: {
    type: Number,
    default: null
  }
})

const {
  contentRef,
  isDecrypting,
  decryptError,
  isKeyValid
} = useNoteViewer(props)
</script>
