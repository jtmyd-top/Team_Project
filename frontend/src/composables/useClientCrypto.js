/**
 * 客户端加密/解密 Composable - Python 兼容模式
 *
 * 设计目标：与后端 vault_crypto.py 完全兼容
 *
 * 数据格式：Base64(IV + ciphertext)
 * - IV: 16字节随机数
 * - ciphertext: AES-256-CBC加密结果
 *
 * 这样既能解密旧的迁移数据，也能加密新数据，
 * 完全不需要后端参与，真正的前端E2E加密。
 */

export function useClientCrypto() {
  // 使用全局加载的 CryptoJS (通过 CDN 在 HTML 中加载)
  const CryptoJS = window.CryptoJS

  if (!CryptoJS) {
    throw new Error('CryptoJS library not available. Please ensure crypto-js CDN is loaded.')
  }
  /**
   * 生成随机字节（指定长度）
   * @param {number} length - 字节数
   * @returns {CryptoJS.lib.WordArray} 随机数据
   */
  function generateRandomBytes(length) {
    return CryptoJS.lib.WordArray.random(length)
  }

  /**
   * 将字节数组转换为Base64字符串
   * @param {CryptoJS.lib.WordArray} wordArray
   * @returns {string} Base64字符串
   */
  function toBase64(wordArray) {
    return CryptoJS.enc.Base64.stringify(wordArray)
  }

  /**
   * 将Base64字符串转换为字节数组
   * @param {string} base64String
   * @returns {CryptoJS.lib.WordArray} 字节数组
   */
  function fromBase64(base64String) {
    return CryptoJS.enc.Base64.parse(base64String)
  }

  /**
   * 加密文本 - Python 兼容模式
   *
   * 格式：Base64(IV + AES-256-CBC(plaintext, key))
   *
   * @param {string} plaintext - 待加密的明文
   * @param {string} key - 密钥（Base64编码的DEK）
   * @returns {string} Base64编码的密文
   * @throws {Error} 如果加密失败
   */
  function encryptContent(plaintext, key) {
    // 详细的参数检查
    if (!plaintext) {
      throw new Error('加密失败: 缺少明文')
    }

    if (!key) {
      throw new Error('加密失败: 缺少密钥')
    }

    if (typeof plaintext !== 'string' || typeof key !== 'string') {
      throw new Error('加密失败: 明文和密钥必须是字符串')
    }

    if (plaintext.trim() === '') {
      throw new Error('加密失败: 明文为空')
    }

    if (key.trim() === '') {
      throw new Error('加密失败: 密钥为空')
    }

    try {
      // 1. 解析密钥：DEK 是 Base64 编码的，需要先解码回原始字节
      let keyBytes
      try {
        keyBytes = fromBase64(key)  // 从 Base64 解码回 WordArray
      } catch (e) {
        throw new Error('密钥格式无效（应为 Base64 编码）: ' + e.message)
      }

      // 2. 生成随机16字节IV
      const iv = generateRandomBytes(16)

      // 3. 准备明文
      const plaintextBytes = CryptoJS.enc.Utf8.parse(plaintext)

      // 4. 使用AES-256-CBC加密
      // 关键：使用解码后的 keyBytes，而不是字符串形式的密钥
      const encrypted = CryptoJS.AES.encrypt(
        plaintextBytes,
        keyBytes,  // 【改进】使用 WordArray 格式的密钥
        {
          iv: iv,
          mode: CryptoJS.mode.CBC,
          padding: CryptoJS.pad.Pkcs7
        }
      )

      // 5. 手动拼接：IV + ciphertext
      // 这样格式完全兼容 Python 的 base64.b64encode(iv + ciphertext)
      const combined = iv.clone().concat(encrypted.ciphertext)

      // 6. 返回 Base64 编码
      const result = toBase64(combined)

      return result
    } catch (e) {
      console.error('[Vault] 客户端加密错误:', e)
      throw new Error('加密失败: ' + e.message)
    }
  }

  /**
   * 解密文本 - Python 兼容模式
   *
   * 格式识别：Base64(IV + ciphertext)
   * - 前16字节（4个Word）：IV
   * - 后续字节：ciphertext
   *
   * @param {string} encryptedBase64 - Base64编码的密文
   * @param {string} key - 密钥（Base64编码的DEK）
   * @returns {string} 解密后的明文
   * @throws {Error} 如果解密失败
   */
  function decryptContent(encryptedBase64, key) {
    // 详细的参数检查
    if (!encryptedBase64) {
      throw new Error('解密失败: 缺少密文')
    }

    if (!key) {
      throw new Error('解密失败: 缺少密钥')
    }

    if (typeof encryptedBase64 !== 'string' || typeof key !== 'string') {
      throw new Error('解密失败: 密文和密钥必须是字符串')
    }

    if (encryptedBase64.trim() === '') {
      throw new Error('解密失败: 密文为空')
    }

    if (key.trim() === '') {
      throw new Error('解密失败: 密钥为空')
    }

    try {
      // 1. Base64 解码密文
      const rawData = fromBase64(encryptedBase64)

      if (rawData.words.length < 5) {
        // 最少5个words: 4个(IV 16字节) + 1个(最少4字节的密文)
        throw new Error('加密数据无效（长度不足）')
      }

      // 2. 手动切分 IV 和 ciphertext
      // CryptoJS 中 1 Word = 4 字节，所以 16 字节 = 4 Words
      const ivWords = rawData.words.slice(0, 4)  // 前4个Word = IV (16字节)
      const ciphertextWords = rawData.words.slice(4)  // 后续Words = ciphertext

      const iv = CryptoJS.lib.WordArray.create(ivWords, 16)
      const ciphertextBody = CryptoJS.lib.WordArray.create(
        ciphertextWords,
        rawData.sigBytes - 16  // 总长度 - IV长度
      )

      // 3. 解析密钥：DEK 是 Base64 编码的，需要先解码回原始字节
      let keyBytes
      try {
        keyBytes = fromBase64(key)  // 从 Base64 解码回 WordArray
      } catch (e) {
        throw new Error('密钥格式无效（应为 Base64 编码）: ' + e.message)
      }

      // 4. 使用AES-256-CBC解密
      // 关键：使用解码后的 keyBytes，而不是字符串形式的密钥
      const decrypted = CryptoJS.AES.decrypt(
        {
          ciphertext: ciphertextBody
        },
        keyBytes,  // 【改进】使用 WordArray 格式的密钥
        {
          iv: iv,
          mode: CryptoJS.mode.CBC,
          padding: CryptoJS.pad.Pkcs7
        }
      )

      // 5. 转换为UTF-8字符串
      const plaintext = decrypted.toString(CryptoJS.enc.Utf8)

      if (!plaintext) {
        throw new Error('解密结果为空，可能密钥错误或数据损坏')
      }

      return plaintext
    } catch (e) {
      console.error('[Vault] 客户端解密错误:', e)
      throw new Error('解密失败: ' + e.message)
    }
  }

  /**
   * 检查字符串是否看起来像密文
   * （简单启发式：检查是否是有效的Base64格式且长度足够）
   *
   * @param {string} text - 要检查的文本
   * @returns {boolean} 是否可能是密文
   */
  function looksLikeEncrypted(text) {
    if (!text) return false

    // Base64 格式检查
    const base64Regex = /^[A-Za-z0-9+/]*={0,2}$/

    // 长度检查：加密数据包含 IV(16字节) + ciphertext(至少16字节) = 至少32字节
    // Base64 编码会增加约33%，所以至少需要约 43-44 字符
    // 设置阈值为 40 是相对安全的边界
    // - 允许较短的加密数据（如短标题）
    // - 防止普通短文本被当作密文
    return text.length >= 40 && base64Regex.test(text)
  }

  return {
    encryptContent,
    decryptContent,
    looksLikeEncrypted,
    // 导出工具函数供高级使用
    generateRandomBytes,
    toBase64,
    fromBase64
  }
}
