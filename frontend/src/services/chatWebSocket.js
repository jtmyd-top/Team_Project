export class ChatWebSocket {
  constructor({ path = '/ws/messages/', onStatusChange, onEvent, onMaxReconnectReached } = {}) {
    this.path = path
    this.onStatusChange = onStatusChange
    this.onEvent = onEvent
    this.onMaxReconnectReached = onMaxReconnectReached
    this.ws = null
    this.heartbeatTimer = null
    this.reconnectTimer = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 8
    this.isManualClose = false
  }

  connect() {
    if (typeof window === 'undefined' || this.ws) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}${this.path}`
    this.isManualClose = false
    this.onStatusChange?.('connecting')
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.onStatusChange?.('connected')
      this.startHeartbeat()
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'pong') return
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
      }
    }, 25000)
  }

  stopHeartbeat() {
    clearInterval(this.heartbeatTimer)
    this.heartbeatTimer = null
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
  }
}
