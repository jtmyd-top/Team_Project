/**
 * useClientCrypto - 过渡期 thin wrapper
 *
 * 所有加解密转发到 vaultStore（内部使用 Web Crypto + 非导出 CryptoKey）。
 * 原先的 key 参数保留以保持签名兼容，但实际忽略。
 *
 * 注意：encryptContent / decryptContent 现在返回 Promise。consumer 必须使用 await。
 */

import { useVaultStore } from '@/stores/vault'

export function useClientCrypto() {
  const vaultStore = useVaultStore()

  /**
   * 加密文本（返回 Promise<string> 的 Base64 密文）
   * @param {string} plaintext
   * @param {string} [_unusedKey] - 已废弃，仅为兼容旧签名保留
   */
  async function encryptContent(plaintext, _unusedKey) {
    if (typeof plaintext !== 'string' || plaintext.trim() === '') {
      throw new Error('加密失败: 明文为空或格式错误')
    }
    try {
      return await vaultStore.encrypt(plaintext)
    } catch (e) {
      console.error('[Vault] 客户端加密错误:', e)
      throw new Error('加密失败: ' + e.message)
    }
  }

  /**
   * 解密文本（返回 Promise<string> 的明文）
   * @param {string} encryptedBase64
   * @param {string} [_unusedKey] - 已废弃
   */
  async function decryptContent(encryptedBase64, _unusedKey) {
    if (typeof encryptedBase64 !== 'string' || encryptedBase64.trim() === '') {
      throw new Error('解密失败: 密文为空')
    }
    if (!looksLikeEncrypted(encryptedBase64)) {
      return encryptedBase64
    }
    try {
      return await vaultStore.decrypt(encryptedBase64)
    } catch (e) {
      console.error('[Vault] 客户端解密错误:', e)
      throw new Error('解密失败: ' + e.message)
    }
  }

  /**
   * 检查字符串是否像 Base64 密文（纯启发式）
   */
  function looksLikeEncrypted(text) {
    if (!text) return false
    const base64Regex = /^[A-Za-z0-9+/]*={0,2}$/
    return text.length >= 40 && base64Regex.test(text)
  }

  return {
    encryptContent,
    decryptContent,
    looksLikeEncrypted
  }
}
