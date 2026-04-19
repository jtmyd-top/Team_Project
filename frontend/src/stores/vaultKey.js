/**
 * vaultKey - 保密柜密钥闭包模块
 *
 * 持有 Web Crypto CryptoKey（extractable: false），不对外导出 key 引用。
 * 加解密数据格式：Base64(IV + ciphertext)，AES-256-CBC + PKCS7，与后端 utils/vault_crypto.py 兼容。
 *
 * 设计属性：
 *  - CryptoKey 存于模块作用域闭包，无响应式、无全局引用
 *  - extractable: false，即使被 XSS 拿到引用也无法导出原始字节
 *  - 订阅/发布：解锁/锁定时通知所有订阅者，便于 composable 清理明文缓存
 */

let cryptoKey = null
let expireTimestamp = null
const listeners = new Set()

// TTL 合理上限（秒）：保护性钳位，防止调用方把 Unix 时间戳当 TTL 传进来导致
// expireTimestamp 飞到几十年后、setTimeout 因数值溢出立即触发自动锁定
const MAX_TTL_SECONDS = 24 * 60 * 60

function sanitizeTtl(ttlSeconds) {
  const n = Number(ttlSeconds) || 0
  if (n <= 0) return 0
  if (n > MAX_TTL_SECONDS) {
    console.warn(`[vaultKey] ttlSeconds=${n} 超过 ${MAX_TTL_SECONDS}s 上限，已钳位（疑似 Unix 时间戳被当成 TTL 传入）`)
    return MAX_TTL_SECONDS
  }
  return n
}

function base64ToBytes(base64) {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes
}

function bytesToBase64(bytes) {
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

function concatBytes(a, b) {
  const out = new Uint8Array(a.length + b.length)
  out.set(a, 0)
  out.set(b, a.length)
  return out
}

function notify(state) {
  listeners.forEach(fn => {
    try { fn(state) } catch (e) { console.error('[vaultKey] listener error:', e) }
  })
}

export async function importDekBase64(base64, ttlSeconds) {
  if (!base64 || typeof base64 !== 'string') {
    throw new Error('importDekBase64: base64 is required')
  }
  const raw = base64ToBytes(base64)
  try {
    cryptoKey = await crypto.subtle.importKey(
      'raw',
      raw,
      { name: 'AES-CBC', length: raw.length * 8 },
      false,
      ['encrypt', 'decrypt']
    )
  } finally {
    raw.fill(0)
  }
  expireTimestamp = Date.now() + (ttlSeconds || 0) * 1000
  notify('unlock')
}

/**
 * 方案 C：开启 ECDH 握手。
 * 生成非导出 P-256 临时密钥对，返回客户端公钥（SPKI-DER base64）与私钥引用。
 * 私钥为非导出 CryptoKey，外部拿到引用也无法读出字节，仅能用于 deriveBits。
 */
export async function beginHandshake() {
  const keyPair = await crypto.subtle.generateKey(
    { name: 'ECDH', namedCurve: 'P-256' },
    false,
    ['deriveBits']
  )
  const spki = await crypto.subtle.exportKey('spki', keyPair.publicKey)
  const clientPubB64 = bytesToBase64(new Uint8Array(spki))
  return { clientPrivateKey: keyPair.privateKey, clientPubB64 }
}

/**
 * 方案 C：完成握手并将 DEK 导入为非导出 AES-CBC CryptoKey 写入模块闭包。
 * 步骤：ECDH 派生 shared → HKDF-SHA256(info="vault-dek-v1") → AES-256-GCM 解包 → importKey AES-CBC → 清零中间缓冲。
 */
export async function completeHandshakeImport({
  serverPubB64,
  ivB64,
  ctB64,
  clientPrivateKey,
  ttlSeconds
}) {
  if (!serverPubB64 || !ivB64 || !ctB64) {
    throw new Error('completeHandshakeImport: server_pub/iv/ct 必填')
  }
  if (!clientPrivateKey) {
    throw new Error('completeHandshakeImport: clientPrivateKey 必填')
  }

  const serverPubBytes = base64ToBytes(serverPubB64)
  const serverPubKey = await crypto.subtle.importKey(
    'spki',
    serverPubBytes,
    { name: 'ECDH', namedCurve: 'P-256' },
    false,
    []
  )

  const sharedBits = await crypto.subtle.deriveBits(
    { name: 'ECDH', public: serverPubKey },
    clientPrivateKey,
    256
  )
  const sharedBytes = new Uint8Array(sharedBits)

  let dekBuffer = null
  try {
    const sharedHkdfKey = await crypto.subtle.importKey(
      'raw',
      sharedBytes,
      { name: 'HKDF' },
      false,
      ['deriveKey']
    )
    const wrapKey = await crypto.subtle.deriveKey(
      {
        name: 'HKDF',
        hash: 'SHA-256',
        salt: new Uint8Array(),
        info: new TextEncoder().encode('vault-dek-v1')
      },
      sharedHkdfKey,
      { name: 'AES-GCM', length: 256 },
      false,
      ['decrypt']
    )

    const iv = base64ToBytes(ivB64)
    const ct = base64ToBytes(ctB64)
    dekBuffer = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      wrapKey,
      ct
    )
    const dekBytes = new Uint8Array(dekBuffer)
    try {
      cryptoKey = await crypto.subtle.importKey(
        'raw',
        dekBytes,
        { name: 'AES-CBC', length: dekBytes.length * 8 },
        false,
        ['encrypt', 'decrypt']
      )
    } finally {
      dekBytes.fill(0)
    }
  } finally {
    sharedBytes.fill(0)
  }

  expireTimestamp = Date.now() + sanitizeTtl(ttlSeconds) * 1000
  notify('unlock')
}

export function clearKey() {
  const wasUnlocked = cryptoKey !== null
  cryptoKey = null
  expireTimestamp = null
  if (wasUnlocked) notify('lock')
}

export function hasKey() {
  if (!cryptoKey) return false
  if (!expireTimestamp || expireTimestamp <= Date.now()) {
    clearKey()
    return false
  }
  return true
}

export function getExpireTime() {
  return expireTimestamp
}

/**
 * 延长密钥有效期（用于用户活动重置倒计时）
 */
export function extendExpire(ttlSeconds) {
  if (!cryptoKey) return false
  expireTimestamp = Date.now() + sanitizeTtl(ttlSeconds) * 1000
  return true
}

export async function encrypt(plaintext) {
  if (typeof plaintext !== 'string') {
    throw new Error('encrypt: plaintext must be a string')
  }
  if (!hasKey()) throw new Error('Vault locked')
  const iv = crypto.getRandomValues(new Uint8Array(16))
  const ctBuffer = await crypto.subtle.encrypt(
    { name: 'AES-CBC', iv },
    cryptoKey,
    new TextEncoder().encode(plaintext)
  )
  const combined = concatBytes(iv, new Uint8Array(ctBuffer))
  return bytesToBase64(combined)
}

export async function decrypt(base64) {
  if (typeof base64 !== 'string') {
    throw new Error('decrypt: base64 must be a string')
  }
  if (!hasKey()) throw new Error('Vault locked')
  const raw = base64ToBytes(base64)
  if (raw.length < 17) throw new Error('decrypt: ciphertext too short')
  const iv = raw.slice(0, 16)
  const ct = raw.slice(16)
  const ptBuffer = await crypto.subtle.decrypt(
    { name: 'AES-CBC', iv },
    cryptoKey,
    ct
  )
  return new TextDecoder().decode(ptBuffer)
}

/**
 * 订阅锁定状态变化。
 * @param {(state: 'lock' | 'unlock') => void} fn
 * @returns {() => void} 取消订阅函数
 */
export function onLockStateChange(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
