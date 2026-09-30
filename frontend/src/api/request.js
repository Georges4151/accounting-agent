import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { useBookStore } from '@/stores/book'
import router from '@/router'
import { ElMessage } from 'element-plus'

/**
 * 创建 Axios 实例
 * 封装请求拦截、响应拦截、Token 刷新等逻辑
 */
const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 是否正在刷新 Token（防止并发刷新）
let isRefreshing = false
// 等待刷新 Token 的请求队列
let pendingRequests = []

/**
 * 处理等待队列中的请求
 * @param {string} newToken - 新的访问令牌
 */
function processPendingRequests(newToken) {
  pendingRequests.forEach(callback => callback(newToken))
  pendingRequests = []
}

/**
 * 请求拦截器：自动添加 Authorization 请求头
 */
request.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    if (authStore.accessToken) {
      config.headers.Authorization = `Bearer ${authStore.accessToken}`
    }
    const bookStore = useBookStore()
    if (bookStore.currentBookId) {
      config.headers['X-Book-ID'] = bookStore.currentBookId
    }
    // FormData 上传时删除默认的 Content-Type，让 axios 自动设置带 boundary 的 multipart/form-data
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type']
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

/**
 * 响应拦截器：处理 401 错误，自动刷新 Token
 */
request.interceptors.response.use(
  (response) => {
    return response
  },
  async (error) => {
    const originalRequest = error.config

    // 处理 401 未授权错误，自动尝试刷新 Token
    if (error.response?.status === 401 && !originalRequest._retry) {
      // 排除登录和刷新 Token 接口本身（避免死循环）
      const isAuthRequest = originalRequest.url.includes('/auth/login') ||
        originalRequest.url.includes('/auth/refresh')

      if (isAuthRequest) {
        return Promise.reject(error)
      }

      originalRequest._retry = true

      // 如果正在刷新 Token，将当前请求加入等待队列
      if (isRefreshing) {
        return new Promise((resolve) => {
          pendingRequests.push((newToken) => {
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            resolve(request(originalRequest))
          })
        })
      }

      isRefreshing = true
      const authStore = useAuthStore()

      try {
        const success = await authStore.refreshAccessToken()
        if (success) {
          // 刷新成功，更新原始请求的 Token 并重新发送
          originalRequest.headers.Authorization = `Bearer ${authStore.accessToken}`
          processPendingRequests(authStore.accessToken)
          return request(originalRequest)
        } else {
          // 刷新失败，跳转登录页
          authStore.logout()
          ElMessage.error('登录已过期，请重新登录')
          router.push({ name: 'Login', query: { redirect: router.currentRoute.value.fullPath } })
          return Promise.reject(error)
        }
      } finally {
        isRefreshing = false
      }
    }

    // 其他错误：显示错误提示
    if (error.response?.data) {
      const isConflict = error.response.status === 409
      // 处理 blob 响应类型的错误（需要读取 blob 文本）
      if (error.response.data instanceof Blob) {
        try {
          const text = await error.response.data.text()
          const json = JSON.parse(text)
          if (isConflict) {
            ElMessage.warning(json.detail || text)
          } else {
            ElMessage.error(json.detail || text)
          }
        } catch {
          ElMessage.error(error.message || '请求失败')
        }
      } else if (error.response.data?.detail) {
        if (isConflict) {
          ElMessage.warning(error.response.data.detail)
        } else {
          ElMessage.error(error.response.data.detail)
        }
      } else {
        ElMessage.error(error.message || '请求失败')
      }
    } else if (error.message) {
      ElMessage.error(error.message)
    }

    return Promise.reject(error)
  }
)

export default request