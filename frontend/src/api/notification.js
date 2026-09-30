import request from './request'

/**
 * 通知 API
 */

// 获取通知列表
export function getNotifications(params) {
  return request.get('/notifications', { params })
}

// 获取未读通知数量
export function getUnreadCount() {
  return request.get('/notifications/unread-count')
}

// 标记单条通知为已读
export function markAsRead(id) {
  return request.post(`/notifications/${id}/read`)
}

// 全部标记为已读
export function markAllAsRead() {
  return request.post('/notifications/read-all')
}

// 管理员发送通知
export function sendNotification(data) {
  return request.post('/notifications/send', data)
}