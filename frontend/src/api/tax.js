import request from './request'

/**
 * 税务管理 API
 */

// 获取税务记录列表
export function getTaxRecords(params) {
  return request.get('/tax/records', { params })
}

// 计算税费
export function calculateTax(data) {
  return request.post('/tax/calculate', data)
}

// 更新税务记录
export function updateTaxRecord(id, data) {
  return request.put(`/tax/records/${id}`, data)
}

// 标记已缴
export function payTax(id, data) {
  return request.post(`/tax/records/${id}/pay`, data)
}

// 获取税务汇总
export function getTaxSummary(period) {
  return request.get('/tax/summary', { params: { period } })
}

// 获取税负分析
export function getTaxAnalysis(year) {
  return request.get('/tax/analysis', { params: { year } })
}

// 获取截止提醒
export function getTaxDeadlines() {
  return request.get('/tax/deadlines')
}

// 添加截止提醒
export function addTaxDeadline(data) {
  return request.post('/tax/deadlines', data)
}