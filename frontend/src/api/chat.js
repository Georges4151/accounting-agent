import { useAuthStore } from '@/stores/auth'
import request from './request'
import router from '@/router'

/**
 * AI 对话相关 API
 */

/**
 * 流式对话请求（SSE）
 * 使用 fetch 实现服务端推送事件流式读取
 * 内置 401 自动刷新 token 逻辑
 *
 * @param {string} message - 用户消息
 * @param {object} modelConfig - 模型配置 { mode, model, provider, enable_web_search }
 * @param {object} callbacks - 回调函数 { onToken(text), onDone(fullResponse), onError(error) }
 * @param {Array} history - 历史消息 [{role: 'user'|'assistant', content: '...'}]
 * @returns {Promise} - 返回一个 Promise，可用于取消请求
 */
export function chatStream(message, modelConfig = {}, callbacks = {}, history = []) {
  const { onToken, onDone, onError } = callbacks
  const authStore = useAuthStore()

  // 构建请求体
  const body = {
    message,
    history: history.slice(-20),  // 最多保留最近 20 条历史消息（10 轮对话）
    ...modelConfig
  }

  // 使用 AbortController 支持取消请求
  const controller = new AbortController()
  let retried = false

  function doFetch(token) {
    return fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(body),
      signal: controller.signal
    }).then(async (response) => {
      // 401 自动刷新 token 并重试
      if (response.status === 401 && !retried) {
        retried = true
        const success = await authStore.refreshAccessToken()
        if (success) {
          return doFetch(authStore.accessToken)
        } else {
          authStore.logout()
          router.push({ name: 'Login', query: { redirect: router.currentRoute?.value?.fullPath } })
          onError && onError(new Error('登录已过期，请重新登录'))
          return
        }
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        const error = new Error(errorData.detail || `请求失败 (${response.status})`)
        onError && onError(error)
        return
      }

      // 读取 SSE 流
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let fullResponse = ''
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        // 解码数据块
        buffer += decoder.decode(value, { stream: true })

        // 按行分割处理 SSE 事件
        const lines = buffer.split('\n')
        // 最后一个可能是不完整的行，保留到下次处理
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()

            // 流结束标记
            if (data === '[DONE]') {
              onDone && onDone(fullResponse)
              return
            }

            try {
              const parsed = JSON.parse(data)
              const token = parsed.token || parsed.content || ''
              fullResponse += token
              onToken && onToken(token)
            } catch (e) {
              // 不是 JSON 格式，直接作为文本处理
              fullResponse += data
              onToken && onToken(data)
            }
          }
        }
      }

      // 流读取完毕
      onDone && onDone(fullResponse)
    }).catch((error) => {
      // 忽略取消请求的错误
      if (error.name === 'AbortError') return
      onError && onError(error)
    })
  }

  doFetch(authStore.accessToken)

  // 返回取消函数
  return {
    cancel: () => controller.abort()
  }
}

/**
 * 获取可用模型列表
 */
export function getAvailableModels() {
  return request.get('/chat/models').then(res => res.data)
}