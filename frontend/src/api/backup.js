import request from './request'

/**
 * 数据备份与恢复 API
 */

// 创建备份
export function createBackup() {
  return request.post('/backup/create')
}

// 获取备份列表
export function getBackupList() {
  return request.get('/backup/list')
}

// 下载备份文件
export function downloadBackup(filename) {
  return request.get(`/backup/download/${encodeURIComponent(filename)}`, {
    responseType: 'blob'
  })
}

// 上传备份文件恢复数据
export function restoreBackup(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/backup/restore', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 删除备份
export function deleteBackup(filename) {
  return request.delete(`/backup/${encodeURIComponent(filename)}`)
}