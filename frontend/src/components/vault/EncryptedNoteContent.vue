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
    <div v-else-if="decryptedContent" v-html="decryptedContent" class="note-content"></div>

    <!-- 错误信息 -->
    <el-alert
      v-if="decryptError"
      :title="decryptError"
      type="error"
      closable
      @close="decryptError = ''"
    />
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useVaultEncryption } from '@/composables/useVaultEncryption'

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

const { isKeyValid, decryptNoteFromBackend } = useVaultEncryption()

const decryptedContent = ref('')
const isDecrypting = ref(false)
const decryptError = ref('')

const showVerifyPrompt = ref(false)

// 监听加密状态变化
watch(
  () => isKeyValid.value,
  async (valid) => {
    if (valid && props.isSecret && props.encryptedContent) {
      await decryptContent()
    } else if (!valid && props.isSecret) {
      showVerifyPrompt.value = true
    }
  }
)

// 挂载时检查
onMounted(async () => {
  if (!props.isSecret) {
    // 非加密笔记，直接显示
    decryptedContent.value = props.encryptedContent
    return
  }

  if (isKeyValid.value) {
    // 已有有效密钥，解密
    await decryptContent()
  } else {
    // 无效密钥，提示验证
    showVerifyPrompt.value = true
  }
})

async function decryptContent() {
  if (!props.encryptedContent) return

  isDecrypting.value = true
  decryptError.value = ''

  try {
    const result = await decryptNoteFromBackend(
      props.encryptedContent,
      props.noteId
    )

    decryptedContent.value = result
    showVerifyPrompt.value = false
  } catch (e) {
    console.error('Decryption error:', e)
    decryptError.value = e.message || '解密失败，请重试'
    showVerifyPrompt.value = true
  } finally {
    isDecrypting.value = false
  }
}

defineExpose({
  decryptContent
})
</script>

<style scoped>
.encrypted-note-content {
  width: 100%;
}

.decrypting-state {
  padding: 20px;
}

.note-content {
  padding: 10px;
  line-height: 1.6;
}
</style>
