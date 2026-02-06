<template>
  <div class="encrypted-note-editor">
    <!-- 加密状态指示器 -->
    <div v-if="props.isSecret" class="encryption-badge">
      <el-icon><Lock /></el-icon>
      <span>此笔记已加密</span>
    </div>

    <!-- 加密切换对话框 -->
    <el-dialog
      title="加密笔记"
      v-model="showEncryptionDialog"
      width="500px"
    >
      <el-alert
        title="确认加密"
        type="warning"
        description="将此笔记加入保险柜后，内容将被加密存储。您必须通过 2FA 验证才能查看。"
        closable
        :closable="false"
      />

      <div style="margin-top: 20px; color: #666;">
        <p>
          <el-checkbox v-model="rememberChoice">记住我的选择</el-checkbox>
        </p>
      </div>

      <template #footer>
        <el-button @click="closeEncryptionDialog">取消</el-button>
        <el-button type="primary" @click="confirmEncryption">
          加入保险柜
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { Lock } from '@element-plus/icons-vue'
import { useEncryptedNoteEditor } from '@/composables/useEncryptedNoteEditor'
import '@/assets/styles/components/encrypted-note-editor.css'

const props = defineProps({
  noteId: {
    type: Number,
    required: true
  },
  isSecret: {
    type: Boolean,
    default: false
  },
  content: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['toggle-success'])

const {
  showEncryptionDialog,
  rememberChoice,
  handleToggleSecret,
  confirmEncryption,
  closeEncryptionDialog
} = useEncryptedNoteEditor(props, emit)

defineExpose({
  handleToggleSecret
})
</script>
