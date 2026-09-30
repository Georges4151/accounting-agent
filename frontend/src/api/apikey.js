import request from './request'

/**
 * API Key 管理 API
 */

// 获取所有 API Key
export function getKeys() {
  return request.get('/api-keys')
}

// 添加新的 API Key
export function addKey(data) {
  return request.post('/api-keys', data)
}

// 设为默认 Key
export function setDefaultKey(keyId) {
  return request.put(`/api-keys/${keyId}/default`)
}

// 启用/禁用 Key
export function toggleKey(keyId) {
  return request.put(`/api-keys/${keyId}/toggle`)
}

// 删除 API Key
export function deleteKey(keyId) {
  return request.delete(`/api-keys/${keyId}`)
}

// 获取支持的提供商列表
export function getProviders() {
  return request.get('/api-keys/providers')
}