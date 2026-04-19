import { ref, watch, onMounted } from 'vue'
import { useVaultStore } from '@/stores/vault'

export function useEncryptedNoteContent(props) {
  const vaultStore = useVaultStore()

  const decryptedContent = ref('')
  const isDecrypting = ref(false)
  const decryptError = ref('')
  const showVerifyPrompt = ref(false)

  // 监听 vault 解锁状态
  watch(
    () => vaultStore.isUnlocked,
    async (unlocked) => {
      if (unlocked && props.isSecret && props.encryptedContent) {
        await decryptContent()
      } else if (!unlocked && props.isSecret) {
        showVerifyPrompt.value = true
        decryptedContent.value = ''
      }
    }
  )

  onMounted(async () => {
    if (!props.isSecret) {
      decryptedContent.value = props.encryptedContent
      return
    }

    if (vaultStore.isUnlocked) {
      await decryptContent()
    } else {
      showVerifyPrompt.value = true
    }
  })

  let latestRequestId = 0
  async function decryptContent() {
    if (!props.encryptedContent) return
    if (!vaultStore.isUnlocked) {
      showVerifyPrompt.value = true
      return
    }

    const requestId = ++latestRequestId
    isDecrypting.value = true
    decryptError.value = ''

    try {
      const result = await vaultStore.decrypt(props.encryptedContent)
      if (requestId !== latestRequestId) return
      decryptedContent.value = result
      showVerifyPrompt.value = false
    } catch (e) {
      if (requestId !== latestRequestId) return
      console.error('Decryption error:', e)
      decryptError.value = e.message || '解密失败，请重试'
      showVerifyPrompt.value = true
    } finally {
      if (requestId === latestRequestId) {
        isDecrypting.value = false
      }
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
