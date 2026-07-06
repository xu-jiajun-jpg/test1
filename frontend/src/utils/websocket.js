const WS_URL = 'ws://127.0.0.1:8001/ws/dashboard'

export function createDashboardSocket({ onMessage, onOpen, onClose, onError }) {
  let ws = null
  let reconnectTimer = null
  let reconnectAttempts = 0
  let destroyed = false
  let heartbeatTimer = null
  const MAX_RECONNECT = 5
  const HEARTBEAT_INTERVAL = 30000

  function connect() {
    if (destroyed) return
    const token = localStorage.getItem('token')
    ws = new WebSocket(`${WS_URL}?token=${token || ''}`)

    ws.onopen = () => {
      if (destroyed) { ws.close(); return }
      console.log('[WS] Connected')
      reconnectAttempts = 0
      // 启动心跳
      clearInterval(heartbeatTimer)
      heartbeatTimer = setInterval(() => {
        try { ws.send(JSON.stringify({ event: 'ping' })) } catch { /* ignore */ }
      }, HEARTBEAT_INTERVAL)
      onOpen?.()
    }

    ws.onmessage = (event) => {
      if (destroyed) return
      try {
        const data = JSON.parse(event.data)
        onMessage?.(data)
      } catch (e) {
        console.error('[WS] Parse error:', e)
      }
    }

    ws.onclose = () => {
      console.log('[WS] Disconnected')
      clearInterval(heartbeatTimer)
      onClose?.()
      if (!destroyed && reconnectAttempts < MAX_RECONNECT) {
        reconnectTimer = setTimeout(() => {
          reconnectAttempts++
          connect()
        }, 2000)
      }
    }

    ws.onerror = (err) => {
      console.error('[WS] Error:', err)
      onError?.(err)
    }
  }

  function disconnect() {
    destroyed = true
    clearInterval(heartbeatTimer)
    clearTimeout(reconnectTimer)
    if (ws) {
      ws.onclose = null
      ws.close()
    }
  }

  connect()
  return { disconnect }
}
