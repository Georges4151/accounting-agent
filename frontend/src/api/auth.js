import request from './request'

/**
 * 认证相关 API
 */
export function login(data) {
  return request.post('/auth/login', data)
}

export function refreshToken(refreshToken) {
  return request.post('/auth/refresh', { refresh_token: refreshToken })
}

export function logout() {
  return request.post('/auth/logout')
}

export function getCurrentUser() {
  return request.get('/auth/me')
}

export function changePassword(data) {
  return request.put('/auth/change-password', data)
}

export function getSessions() {
  return request.get('/auth/sessions')
}

export function logoutAll() {
  return request.post('/auth/logout-all')
}

export function checkPasswordStrength(password) {
  return request.post('/auth/check-password-strength', { password })
}