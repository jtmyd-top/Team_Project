import { ref, watch, onMounted } from 'vue'
import { useVaultEncryption } from '@/composables/useVaultEncryption'

export function useEncryptedNoteContent(props) {
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

  function clearDecryptError() {
    decryptError.value = ''
  }

  return {
    decryptedContent,
    isDecrypting,
    decryptError,
    showVerifyPrompt,
    decryptContent,
    clearDecryptError
  }
}
