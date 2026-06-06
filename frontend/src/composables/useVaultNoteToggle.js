import { getCsrfToken } from '@utils/csrf'

export function useVaultNoteToggle({ sidebarStore, vaultStore, decryptContent, encryptContent, tryRecoverKeyFromSession, ElMessage }) {
  function assertEncryptionSourceIntegrity(latestNoteData, sourceSnapshot) {
    const latestContent = latestNoteData?.content || ''
    const snapshotContent = sourceSnapshot?.content || ''

    if (!snapshotContent) return

    if (latestContent.length < snapshotContent.length) {
      throw new Error(
        `安全中止：待加密内容长度异常变短（当前${latestContent.length}，原始${snapshotContent.length}）。为避免笔记内容丢失，已取消纳入保密柜。`
      )
    }
  }

  async function performEncryption(note, sourceSnapshot = null) {
    if (!note || !note.id) {
      throw new Error('笔记对象无效')
    }

    if (!vaultStore.isUnlocked) {
      throw new Error('保密柜未解锁，无法加密')
    }

    const fetchResp = await fetch(`/api/notes/${note.id}/?full_content=true`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })

    if (!fetchResp.ok) {
      throw new Error('加载笔记数据失败')
    }

    const noteData = await fetchResp.json()
    let plainTitle = noteData.title || ''
    let plainContent = noteData.content || ''

    assertEncryptionSourceIntegrity(noteData, sourceSnapshot)

    if (!plainContent || plainContent.trim() === '') {
      throw new Error('笔记内容为空，无法加密')
    }

    if (!plainTitle || plainTitle.trim() === '') {
      throw new Error('笔记标题为空，无法加密')
    }

    const encryptedTitle = await encryptContent(plainTitle)
    const encryptedContent = await encryptContent(plainContent)

    const updateResponse = await fetch(`/api/notes/${note.id}/`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({
        title: encryptedTitle,
        content: encryptedContent,
        vault_source_content_length: plainContent.length,
        vault_original_content_length: (sourceSnapshot?.content || '').length || plainContent.length
      })
    })

    if (!updateResponse.ok) {
      const errorData = await updateResponse.json()
      throw new Error('保存加密内容失败: ' + (errorData.message || errorData.error || errorData.detail || '后端错误'))
    }
  }

  async function waitForUnlock(timeout = 5000) {
    return new Promise((resolve) => {
      if (vaultStore.isUnlocked) {
        resolve(true)
        return
      }

      const unsubscribe = vaultStore.onLockStateChange((state) => {
        if (state === 'unlock') {
          clearTimeout(timeoutHandle)
          unsubscribe()
          resolve(true)
        }
      })

      const timeoutHandle = setTimeout(() => {
        unsubscribe()
        resolve(false)
      }, timeout)
    })
  }

  async function revertSecretFlag(note) {
    try {
      await fetch(`/api/notes/${note.id}/toggle-secret/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/json'
        }
      })
    } catch (e) {
      console.warn('[Vault] Failed to revert is_secret flag:', e)
    }
  }

  async function refreshVaultData(note) {
    if (sidebarStore.activeModule === 'all-notes') {
      const index = sidebarStore.currentNotes.findIndex(n => n.id === note.id)
      if (index > -1) sidebarStore.currentNotes.splice(index, 1)
    } else {
      await sidebarStore.loadModuleData()
    }
  }

  async function executeEncryptAndSave(note, sourceSnapshot = null) {
    if (vaultStore.isUnlocked) {
      try {
        await performEncryption(note, sourceSnapshot)
        ElMessage.success('加入保密柜成功！内容已加密')
        await refreshVaultData(note)
      } catch (e) {
        ElMessage.error('加密失败: ' + e.message)
        await revertSecretFlag(note)
      }
    } else {
      await revertSecretFlag(note)

      const encryptOperation = async () => {
        const unlocked = await waitForUnlock()
        if (!unlocked) {
          throw new Error('未能获得有效的加密密钥')
        }

        const retoggleResp = await fetch(`/api/notes/${note.id}/toggle-secret/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json'
          }
        })

        if (!retoggleResp.ok) {
          throw new Error('重新标记为保密笔记失败')
        }

        await performEncryption(note, sourceSnapshot)
      }

      vaultStore.setPendingOperation(note.id, note.content, encryptOperation)
      sidebarStore.vaultVerifyDialogVisible = true
    }
  }

  async function handleToggleSecret(note, currentNote, propsActiveNoteId) {
    const csrfToken = getCsrfToken()

    const currentNoteResp = await fetch(`/api/notes/${note.id}/?full_content=true`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })

    if (!currentNoteResp.ok) {
      throw new Error('获取笔记数据失败')
    }

    const data = await currentNoteResp.json()
    const wasSecret = data.is_secret

    const response = await fetch(`/api/notes/${note.id}/toggle-secret/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      throw new Error('切换失败')
    }

    const toggledData = await response.json()

    if (!toggledData.is_secret) {
      if (wasSecret) {
        let decryptedTitle = data.title || ''
        let decryptedContent = data.content || ''

        if (!vaultStore.isUnlocked) {
          await tryRecoverKeyFromSession()
          if (!vaultStore.isUnlocked) {
            ElMessage.error('无法获取解密密钥，请先进行 2FA 验证')
            await fetch(`/api/notes/${note.id}/toggle-secret/`, {
              method: 'POST',
              headers: { 'X-CSRFToken': csrfToken }
            })
            return
          }
        }

        try {
          if (decryptedTitle) {
            try {
              decryptedTitle = await decryptContent(decryptedTitle)
            } catch {
              decryptedTitle = data.title || ''
            }
          }

          if (decryptedContent) {
            try {
              decryptedContent = await decryptContent(decryptedContent)
            } catch {
              decryptedContent = data.content || ''
            }
          }

          const saveResponse = await fetch(`/api/notes/${note.id}/`, {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
              title: decryptedTitle,
              content: decryptedContent
            })
          })

          if (!saveResponse.ok) {
            const errorData = await saveResponse.json()
            throw new Error('保存明文内容失败: ' + (errorData.message || errorData.error || '后端错误'))
          }
        } catch (e) {
          ElMessage.error('处理笔记内容时出错: ' + e.message)
          await fetch(`/api/notes/${note.id}/toggle-secret/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken }
          })
          return
        }
      }

      ElMessage.success('移出保密柜成功')
      window.dispatchEvent(new CustomEvent('note-moved-from-vault', { detail: { noteId: note.id } }))
      if (sidebarStore.activeModule === 'vault') {
        const index = sidebarStore.currentNotes.findIndex(n => n.id === note.id)
        if (index > -1) sidebarStore.currentNotes.splice(index, 1)
      } else {
        await sidebarStore.loadModuleData()
      }
    } else {
      await executeEncryptAndSave(note, currentNote)
      window.dispatchEvent(new CustomEvent('note-moved-to-vault', { detail: { noteId: note.id } }))
      ElMessage.success('加入保密柜成功')
    }

    if (propsActiveNoteId === note.id) {
      window.dispatchEvent(new CustomEvent('note-secret-toggled', {
        detail: {
          noteId: note.id,
          isSecret: toggledData.is_secret,
          isPublic: toggledData.is_public
        }
      }))
    }
  }

  return {
    handleToggleSecret
  }
}
