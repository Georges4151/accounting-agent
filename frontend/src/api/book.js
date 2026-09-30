import request from './request'

/**
 * 账套管理 API
 */

// 获取账套列表
export function getBooks(params) {
  return request.get('/books', { params })
}

// 创建账套
export function createBook(data) {
  return request.post('/books', data)
}

// 更新账套
export function updateBook(id, data) {
  return request.put(`/books/${id}`, data)
}

// 归档账套
export function deleteBook(id) {
  return request.delete(`/books/${id}`)
}

// 归档账套（需要密钥验证 token）
export function archiveBook(id, token) {
  return request.delete(`/books/${id}`, {
    headers: { 'X-Archive-Token': token },
  })
}

// 获取账套成员
export function getBookMembers(bookId) {
  return request.get(`/books/${bookId}/members`)
}

// 添加账套成员
export function addBookMember(bookId, data) {
  return request.post(`/books/${bookId}/members`, data)
}

// 移除账套成员
export function removeBookMember(bookId, userId) {
  return request.delete(`/books/${bookId}/members/${userId}`)
}

// 批量添加账套成员
export function batchAddBookMembers(bookId, data) {
  return request.post(`/books/${bookId}/members/batch`, data)
}

// 切换当前账套
export function switchBook(bookId) {
  return request.post(`/books/${bookId}/switch`)
}