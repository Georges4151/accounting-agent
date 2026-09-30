import request from './request'

/**
 * 对话管理 API
 */

/** 获取对话列表 */
export function getConversations() {
  return request.get('/conversations').then(res => res.data)
}

/** 创建新对话 */
export function createConversation(title = '新对话') {
  return request.post('/conversations', { title }).then(res => res.data)
}

/** 获取对话详情（含消息列表） */
export function getConversation(convId) {
  return request.get(`/conversations/${convId}`).then(res => res.data)
}

/** 更新对话标题 */
export function updateConversation(convId, title) {
  return request.put(`/conversations/${convId}`, { title }).then(res => res.data)
}

/** 删除对话 */
export function deleteConversation(convId) {
  return request.delete(`/conversations/${convId}`).then(res => res.data)
}

/** 添加消息到对话 */
export function addMessage(convId, role, content) {
  return request.post(`/conversations/${convId}/messages`, { role, content }).then(res => res.data)
}