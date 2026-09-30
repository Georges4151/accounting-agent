import request from './request'

/**
 * 往来管理 API
 */

// 获取应收应付列表
export function getReconciliations(params) {
  return request.get('/reconciliations', { params })
}

// 创建核销记录
export function createReconciliation(data) {
  return request.post('/reconciliations', data)
}

// 更新核销记录
export function updateReconciliation(id, data) {
  return request.put(`/reconciliations/${id}`, data)
}

// 删除核销记录
export function deleteReconciliation(id) {
  return request.delete(`/reconciliations/${id}`)
}

// 核销操作
export function writeOffReconciliation(id, data) {
  return request.post(`/reconciliations/${id}/write-off`, data)
}

// 批量核销
export function batchWriteOff(data) {
  return request.post('/reconciliations/batch-write-off', data)
}

// 账龄分析
export function getAgingAnalysis(params) {
  return request.get('/reconciliations/aging', { params })
}

// 客户/供应商对账单
export function getPartyStatement(partyType, partyName, params) {
  return request.get(`/reconciliations/statement/${partyType}/${encodeURIComponent(partyName)}`, { params })
}

// 获取往来方名称列表
export function getPartyNames(params) {
  return request.get('/reconciliations/party-names', { params })
}