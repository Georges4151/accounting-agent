import request from './request'

/**
 * 数据导入导出 API
 */

// 导入凭证 (multipart form)
export function importVouchers(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/import/vouchers', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 导入科目 (multipart form)
export function importAccounts(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/import/accounts', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 导出凭证列表 (返回 blob)
export function exportVouchers(params) {
  return request.get('/export/vouchers', {
    params,
    responseType: 'blob'
  })
}

// 导出报表为 Excel (返回 blob)
export function exportReport(reportType, params) {
  return request.get(`/export/report/${reportType}`, {
    params,
    responseType: 'blob'
  })
}

// 数据库备份 (返回 blob)
export function downloadBackup() {
  return request.get('/export/backup', {
    responseType: 'blob'
  })
}

// 从备份恢复 (multipart form)
export function restoreBackup(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/import/restore', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 预览凭证导入数据
export function previewVoucherImport(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/import/vouchers/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 下载凭证导入模板
export function downloadVoucherTemplate() {
  return request.get('/templates/voucher-import', {
    responseType: 'blob'
  })
}

// 下载导入模板 (返回 blob)
export function downloadTemplate(type) {
  return request.get(`/templates/${type}`, {
    responseType: 'blob'
  })
}