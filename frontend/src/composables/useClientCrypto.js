/**
 * 客户端加密/解密 Composable
 * 所有加密解密都在前端进行，后端只存储密文
 *
 * 加密算法: AES-256 (via crypto-js)
 * 加密模式: ECB (crypto-js默认)
 * 密钥: 用户的 masterKey (来自 2FA 验证)
 */

import CryptoJS from 'crypto-js'

export function useClientCrypto() {
  /**
   * 加密文本
   * @param {string} plaintext - 要加密的明文
   * @param {string} masterKey - 加密密钥(用户的masterKey)
   * @returns {string} Base64编码的密文
   */
  function encryptContent(plaintext, masterKey) {
    if (!plaintext || !masterKey) {
      throw new Error('加密失败: 缺少明文或密钥')
    }

    try {
      // 使用 AES 加密
      const encrypted = CryptoJS.AES.encrypt(plaintext, masterKey)

      // 返回 Base64 格式的密文
      return encrypted.toString()
    } catch (e) {
      console.error('客户端加密错误:', e)
      throw new Error('加密失败: ' + e.message)
    }
  }

  /**
   * 解密文本
   * @param {string} ciphertext - Base64编码的密文
   * @param {string} masterKey - 解密密钥(用户的masterKey)
   * @returns {string} 解密后的明文
   */
  function decryptContent(ciphertext, masterKey) {
    if (!ciphertext || !masterKey) {
      throw new Error('解密失败: 缺少密文或密钥')
    }

    try {
      // 使用 AES 解密
      const decrypted = CryptoJS.AES.decrypt(ciphertext, masterKey)

      // 转换为 UTF8 字符串
      const plaintext = decrypted.toString(CryptoJS.enc.Utf8)

      if (!plaintext) {
        throw new Error('解密结果为空，可能密钥错误或数据损坏')
      }

      return plaintext
    } catch (e) {
      console.error('客户端解密错误:', e)
      throw new Error('解密失败: ' + e.message)
    }
  }

  /**
   * 检查字符串是否看起来像密文
   * (简单启发式：检查是否是 Base64 格式并包含特定前缀)
   * @param {string} text - 要检查的文本
   * @returns {boolean} 是否可能是密文
   */
  function looksLikeEncrypted(text) {
    if (!text) return false

    // crypto-js 生成的密文通常以 "U2FsdGVkX1" (Salted__) 开头
    // 或者只是 Base64 格式的数据
    const base64Regex = /^[A-Za-z0-9+/]*={0,2}$/

    return text.length > 50 && base64Regex.test(text)
  }

  return {
    encryptContent,
    decryptContent,
    looksLikeEncrypted
  }
}
