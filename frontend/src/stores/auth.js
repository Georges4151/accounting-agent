import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  login as apiLogin,
  refreshToken as apiRefreshToken,
  logout as apiLogout,
  getCurrentUser,
  getSessions as apiGetSessions,
  logoutAll as apiLogoutAll
} from '@/api/auth'

/**
 * 用户认证状态管理
 * 使用 pinia-plugin-persistedstate 持久化到 localStorage
 */
export const useAuthStore = defineStore('auth', () => {
  // ===== 状态 =====
  const accessToken = ref('')
  const refreshToken = ref('')
  const userInfo = ref(null)

  // ===== 计算属性 =====
  const isLoggedIn = computed(() => !!accessToken.value && !!userInfo.value)

  // ===== 操作方法 =====

  /**
   * 用户登录
   * @param {string} username - 用户名
   * @param {string} password - 密码
   */
  async function login(username, password) {
    try {
      const res = await apiLogin({ username, password })
      accessToken.value = res.data.access_token
      refreshToken.value = res.data.refresh_token
      userInfo.value = res.data.user
      return res.data
    } catch (error) {
      throw error
    }
  }

  /**
   * 退出登录
   */
  async function logout() {
    try {
      await apiLogout()
    } catch (e) {
      // 即使服务端退出失败，也清除本地状态
    } finally {
      accessToken.value = ''
      refreshToken.value = ''
      userInfo.value = null
    }
  }

  /**
   * 刷新访问令牌
   */
  async function refreshAccessToken() {
    try {
      const res = await apiRefreshToken(refreshToken.value)
      accessToken.value = res.data.access_token
      refreshToken.value = res.data.refresh_token
      return true
    } catch (error) {
      // 刷新失败，清除登录状态
      accessToken.value = ''
      refreshToken.value = ''
      userInfo.value = null
      return false
    }
  }

  /**
   * 获取当前用户信息
   */
  async function fetchUserInfo() {
    try {
      const res = await getCurrentUser()
      userInfo.value = res.data
    } catch (error) {
      throw error
    }
  }

  /**
   * 检查用户是否拥有指定权限
   * @param {string} permission - 权限标识（如 'admin', 'reviewer'）
   */
  function hasPermission(permission) {
    if (!userInfo.value) return false
    // 管理员拥有所有权限
    if (userInfo.value.role === 'admin') return true
    return userInfo.value.role === permission
  }

  /**
   * 获取活跃会话列表
   */
  async function getSessions() {
    try {
      const res = await apiGetSessions()
      return res.data
    } catch (error) {
      throw error
    }
  }

  /**
   * 登出所有设备
   */
  async function logoutAllDevices() {
    try {
      await apiLogoutAll()
      accessToken.value = ''
      refreshToken.value = ''
      userInfo.value = null
    } catch (error) {
      throw error
    }
  }

  return {
    // 状态
    accessToken,
    refreshToken,
    userInfo,
    // 计算属性
    isLoggedIn,
    // 操作方法
    login,
    logout,
    refreshAccessToken,
    fetchUserInfo,
    hasPermission,
    getSessions,
    logoutAllDevices
  }
}, {
  // 持久化配置：将关键状态保存到 localStorage
  persist: {
    key: 'auth-store',
    storage: localStorage,
    pick: ['accessToken', 'refreshToken', 'userInfo']
  }
})