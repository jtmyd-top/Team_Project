/**
 * useProofOfWork - Proof of Work 计算模块
 *
 * 用于防止脚本滥用接口，前端需要计算一个有效的 nonce，
 * 使得 SHA256(prefix + nonce) 的前 N 位为 0。
 */

import { ref } from 'vue'

/**
 * 纯 JS 实现的 SHA256（用于 HTTP 环境，因为 crypto.subtle 只在 HTTPS 可用）
 */
function sha256Sync(message) {
  // SHA256 常量
  const K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ])

  // 初始哈希值
  let H = new Uint32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
  ])

  // 将字符串转为字节数组
  const encoder = new TextEncoder()
  const data = encoder.encode(message)
  const bitLength = data.length * 8

  // 计算填充后的长度（512 位的倍数）
  const paddedLength = Math.ceil((data.length + 9) / 64) * 64
  const padded = new Uint8Array(paddedLength)
  padded.set(data)
  padded[data.length] = 0x80

  // 添加长度（大端序，64位）
  const view = new DataView(padded.buffer)
  view.setUint32(paddedLength - 4, bitLength, false)

  // 处理每个 512 位块
  const W = new Uint32Array(64)

  for (let offset = 0; offset < paddedLength; offset += 64) {
    // 准备消息调度数组
    for (let i = 0; i < 16; i++) {
      W[i] = view.getUint32(offset + i * 4, false)
    }

    for (let i = 16; i < 64; i++) {
      const s0 = ((W[i-15] >>> 7) | (W[i-15] << 25)) ^ ((W[i-15] >>> 18) | (W[i-15] << 14)) ^ (W[i-15] >>> 3)
      const s1 = ((W[i-2] >>> 17) | (W[i-2] << 15)) ^ ((W[i-2] >>> 19) | (W[i-2] << 13)) ^ (W[i-2] >>> 10)
      W[i] = (W[i-16] + s0 + W[i-7] + s1) >>> 0
    }

    // 工作变量
    let a = H[0], b = H[1], c = H[2], d = H[3]
    let e = H[4], f = H[5], g = H[6], h = H[7]

    // 主循环
    for (let i = 0; i < 64; i++) {
      const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))
      const ch = (e & f) ^ (~e & g)
      const temp1 = (h + S1 + ch + K[i] + W[i]) >>> 0
      const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))
      const maj = (a & b) ^ (a & c) ^ (b & c)
      const temp2 = (S0 + maj) >>> 0

      h = g; g = f; f = e
      e = (d + temp1) >>> 0
      d = c; c = b; b = a
      a = (temp1 + temp2) >>> 0
    }

    // 更新哈希值
    H[0] = (H[0] + a) >>> 0
    H[1] = (H[1] + b) >>> 0
    H[2] = (H[2] + c) >>> 0
    H[3] = (H[3] + d) >>> 0
    H[4] = (H[4] + e) >>> 0
    H[5] = (H[5] + f) >>> 0
    H[6] = (H[6] + g) >>> 0
    H[7] = (H[7] + h) >>> 0
  }

  // 转为十六进制字符串
  let hex = ''
  for (let i = 0; i < 8; i++) {
    hex += H[i].toString(16).padStart(8, '0')
  }
  return hex
}

/**
 * SHA256 - 优先使用 Web Crypto API，HTTP 环境下使用纯 JS 实现
 */
async function sha256(message) {
  // 检查是否支持 Web Crypto API（仅 HTTPS 可用）
  if (typeof crypto !== 'undefined' && crypto.subtle) {
    const msgBuffer = new TextEncoder().encode(message)
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
  }
  // HTTP 环境使用纯 JS 实现
  return sha256Sync(message)
}

/**
 * 计算 Proof of Work
 */
export async function solveProofOfWork(prefix, difficulty, onProgress = null, signal = null) {
  const target = '0'.repeat(difficulty)
  let nonce = 0
  const startTime = Date.now()
  const batchSize = 500

  // 检测环境
  const useWebCrypto = typeof crypto !== 'undefined' && crypto.subtle

  while (true) {
    if (signal && signal.aborted) {
      throw new Error('PoW calculation cancelled')
    }

    for (let i = 0; i < batchSize; i++) {
      const nonceStr = nonce.toString()
      const input = prefix + nonceStr

      // 根据环境选择计算方式
      const hash = useWebCrypto ? await sha256(input) : sha256Sync(input)

      if (hash.startsWith(target)) {
        return { nonce: nonceStr, hash, attempts: nonce + 1, duration: Date.now() - startTime }
      }
      nonce++
    }

    if (onProgress) {
      onProgress(nonce, nonce.toString())
    }

    // 让出控制权避免阻塞 UI
    await new Promise(resolve => setTimeout(resolve, 0))
  }
}

/**
 * useProofOfWork Composable
 */
export function useProofOfWork() {
  const isComputing = ref(false)
  const progress = ref(0)
  const error = ref(null)
  const abortController = ref(null)

  /**
   * 获取 PoW challenge 并计算 solution
   * @param {string} initUrl - 初始化接口 URL
   * @returns {Promise<string>} - init_token
   */
  const getInitToken = async (initUrl = '/api/captcha/init/') => {
    isComputing.value = true
    progress.value = 0
    error.value = null
    abortController.value = new AbortController()

    try {
      // 第一步：获取 challenge
      const challengeResponse = await fetch(initUrl, {
        method: 'GET',
        credentials: 'include'
      })

      if (!challengeResponse.ok) {
        throw new Error('获取 challenge 失败')
      }

      const challengeData = await challengeResponse.json()

      if (challengeData.status !== 'challenge') {
        throw new Error(challengeData.message || challengeData.error || '获取 challenge 失败')
      }

      const { prefix, difficulty } = challengeData

      // 第二步：计算 PoW
      const result = await solveProofOfWork(
        prefix,
        difficulty,
        (attempts) => {
          // 估算进度（难度 4 约 65536 次）
          const estimated = Math.pow(16, difficulty)
          progress.value = Math.min(99, Math.round((attempts / estimated) * 100))
        },
        abortController.value.signal
      )

      progress.value = 100

      // 第三步：提交 solution
      const verifyResponse = await fetch(initUrl, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ nonce: result.nonce })
      })

      if (!verifyResponse.ok) {
        const errData = await verifyResponse.json().catch(() => ({}))
        throw new Error(errData.message || errData.error || 'PoW 验证失败')
      }

      const tokenData = await verifyResponse.json()

      if (tokenData.status !== 'success' || !tokenData.init_token) {
        throw new Error(tokenData.message || tokenData.error || '获取 init_token 失败')
      }

      return tokenData.init_token

    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      isComputing.value = false
      abortController.value = null
    }
  }

  /**
   * 取消计算
   */
  const cancel = () => {
    if (abortController.value) {
      abortController.value.abort()
    }
  }

  /**
   * 重置状态
   */
  const reset = () => {
    isComputing.value = false
    progress.value = 0
    error.value = null
    cancel()
  }

  return {
    isComputing,
    progress,
    error,
    getInitToken,
    cancel,
    reset
  }
}

export default useProofOfWork
