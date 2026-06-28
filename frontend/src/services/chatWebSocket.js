export class ChatWebSocket {
  constructor({ path = '/ws/messages/', onStatusChange, onEvent, onMaxReconnectReached, onReconnectSuccess } = {}) {
    this.path = path
    this.onStatusChange = onStatusChange
    this.onEvent = onEvent
    this.onMaxReconnectReached = onMaxReconnectReached
    this.onReconnectSuccess = onReconnectSuccess
    this.ws = null
    this.heartbeatTimer = null
    this.reconnectTimer = null
    this.pongTimeoutTimer = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 8
    this.isManualClose = false
    this.isFirstConnection = true
    this.lastPongTime = null
    this.missedPongCount = 0
  }

  connect() {
    if (typeof window === 'undefined' || this.ws) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}${this.path}`
    this.isManualClose = false
    this.onStatusChange?.('connecting')
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      const wasReconnecting = this.reconnectAttempts > 0
      this.reconnectAttempts = 0
      this.missedPongCount = 0
      this.lastPongTime = Date.now()
      this.onStatusChange?.('connected')
      this.startHeartbeat()

      // 重连成功后触发回调，用于同步消息
      if (!this.isFirstConnection && wasReconnecting) {
        this.onReconnectSuccess?.()
      }
      this.isFirstConnection = false
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'pong') {
          this.lastPongTime = Date.now()
          this.missedPongCount = 0
          this.clearPongTimeout()
          return
        }
        this.onEvent?.(data)
      } catch (error) {
        console.warn('解析实时消息失败:', error)
      }
    }

    this.ws.onerror = () => {
      this.onStatusChange?.('error')
    }

    this.ws.onclose = () => {
      this.stopHeartbeat()
      this.clearPongTimeout()
      this.ws = null
      this.onStatusChange?.('disconnected')
      if (!this.isManualClose) {
        this.scheduleReconnect()
      }
    }
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.onMaxReconnectReached?.()
      return
    }
    this.reconnectAttempts += 1
    const delay = Math.min(1000 * 2 ** (this.reconnectAttempts - 1), 15000)
    clearTimeout(this.reconnectTimer)
    this.reconnectTimer = setTimeout(() => this.connect(), delay)
  }

  startHeartbeat() {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
        // 设置 pong 超时检测（10秒内未收到 pong 视为连接异常）
        this.setPongTimeout()
      }
    }, 25000)
  }

  setPongTimeout() {
    this.clearPongTimeout()
    this.pongTimeoutTimer = setTimeout(() => {
      this.missedPongCount++
      console.warn(`WebSocket pong 超时 (${this.missedPongCount}/3)`)

      // 连续3次未收到 pong，主动断开重连
      if (this.missedPongCount >= 3) {
        console.warn('WebSocket 心跳检测失败，主动断开重连')
        if (this.ws) {
          this.ws.close()
        }
      }
    }, 10000)
  }

  clearPongTimeout() {
    if (this.pongTimeoutTimer) {
      clearTimeout(this.pongTimeoutTimer)
      this.pongTimeoutTimer = null
    }
  }

  stopHeartbeat() {
    clearInterval(this.heartbeatTimer)
    this.heartbeatTimer = null
    this.clearPongTimeout()
  }

  send(payload) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false
    this.ws.send(JSON.stringify(payload))
    return true
  }

  close() {
    this.isManualClose = true
    clearTimeout(this.reconnectTimer)
    this.stopHeartbeat()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.isFirstConnection = true
  }

  // 获取连接状态信息（用于调试）
  getStatus() {
    return {
      readyState: this.ws?.readyState,
      reconnectAttempts: this.reconnectAttempts,
      lastPongTime: this.lastPongTime,
      missedPongCount: this.missedPongCount,
      isManualClose: this.isManualClose,
    }
  }
}
