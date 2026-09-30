import request from './request'

/**
 * 记账凭证 API
 */

// 获取科目列表
export function getAccounts() {
  return request.get('/vouchers/accounts')
}

// 获取凭证列表（支持分页和筛选）
export function getVouchers(params) {
  return request.get('/vouchers', { params })
}

// 获取单个凭证详情
export function getVoucher(id) {
  return request.get(`/vouchers/${id}`)
}

// 创建凭证
export function createVoucher(data) {
  return request.post('/vouchers', data)
}

// 更新凭证
export function updateVoucher(id, data) {
  return request.put(`/vouchers/${id}`, data)
}

// 删除凭证
export function deleteVoucher(id) {
  return request.delete(`/vouchers/${id}`)
}

// 提交审核
export function submitVoucher(id) {
  return request.post(`/vouchers/${id}/submit`)
}

// 审核通过
export function reviewVoucher(id, comment) {
  return request.post(`/vouchers/${id}/review`, { comment: comment || null })
}

// 审核驳回
export function rejectVoucher(id, comment) {
  return request.post(`/vouchers/${id}/reject`, { comment: comment || null })
}

// 审批通过
export function approveVoucher(id, comment) {
  return request.post(`/vouchers/${id}/approve`, { comment: comment || null })
}

// 驳回至草稿
export function rejectToDraft(id, comment) {
  return request.post(`/vouchers/${id}/reject-to-draft`, { comment: comment || null })
}

// AI 生成凭证
export function aiGenerateVoucher(data) {
  return request.post('/vouchers/ai-generate', data)
}

// 红字冲销
export function reverseVoucher(id) {
  return request.post(`/vouchers/${id}/reverse`)
}

// 出纳复核
export function cashierReviewVoucher(id) {
  return request.post(`/vouchers/${id}/cashier-review`)
}

// 取消出纳复核
export function cashierUnreviewVoucher(id) {
  return request.post(`/vouchers/${id}/cashier-unreview`)
}

// 上传附件
export function uploadAttachments(id, files) {
  const formData = new FormData()
  files.forEach(file => {
    formData.append('files', file)
  })
  return request.post(`/vouchers/${id}/attachments`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 获取附件列表
export function getAttachments(id) {
  return request.get(`/vouchers/${id}/attachments`)
}

// 删除附件
export function deleteAttachment(voucherId, filename) {
  return request.delete(`/vouchers/${voucherId}/attachments/${filename}`)
}

// 获取附件下载链接
export function getAttachmentUrl(voucherId, filename) {
  return `/api/vouchers/${voucherId}/attachments/${encodeURIComponent(filename)}`
}

// 下载附件
export async function downloadAttachment(voucherId, filename) {
  const response = await request.get(`/vouchers/${voucherId}/attachments/${encodeURIComponent(filename)}`, {
    responseType: 'arraybuffer'
  })
  const blob = new Blob([response.data])
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  setTimeout(() => {
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }, 200)
}

// ===== 批量操作 =====

// 批量提交审核
export function batchSubmitVouchers(voucherIds) {
  return request.post('/vouchers/batch-submit', { voucher_ids: voucherIds })
}

// 批量审核通过
export function batchReviewVouchers(voucherIds, comment) {
  return request.post('/vouchers/batch-review', { voucher_ids: voucherIds, comment: comment || null })
}

// 批量驳回
export function batchRejectVouchers(voucherIds, comment) {
  return request.post('/vouchers/batch-reject', { voucher_ids: voucherIds, comment: comment || null })
}

// 批量审批通过
export function batchApproveVouchers(voucherIds, comment) {
  return request.post('/vouchers/batch-approve', { voucher_ids: voucherIds, comment: comment || null })
}

// 批量过账
export function batchPostVouchers(voucherIds) {
  return request.post('/vouchers/batch-post', { voucher_ids: voucherIds })
}

// 批量删除
export function batchDeleteVouchers(voucherIds) {
  return request.post('/vouchers/batch-delete', { voucher_ids: voucherIds })
}

// 复制凭证
export function copyVoucher(id) {
  return request.post(`/vouchers/${id}/copy`)
}

// 批量更新状态
export function batchUpdateStatus(voucherIds, targetStatus) {
  return request.post('/vouchers/batch-status', { voucher_ids: voucherIds, target_status: targetStatus })
}

// 预览批量操作状态
export function getBatchStatus(voucherIds) {
  return request.get('/vouchers/batch-status', {
    params: { voucher_ids: voucherIds.join(',') }
  })
}