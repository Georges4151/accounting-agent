import request from './request'

/**
 * 预算管理 API
 */

// 获取预算列表
export function getBudgets(params) {
  return request.get('/budgets', { params })
}

// 创建预算
export function createBudget(data) {
  return request.post('/budgets', data)
}

// 更新预算
export function updateBudget(id, data) {
  return request.put(`/budgets/${id}`, data)
}

// 删除预算
export function deleteBudget(id) {
  return request.delete(`/budgets/${id}`)
}

// 获取预算执行详情
export function getBudgetExecution(id) {
  return request.get(`/budgets/${id}/execution`)
}

// 获取预算预警列表
export function getBudgetAlerts(triggeredOnly = false) {
  return request.get('/budgets/alerts', { params: { triggered_only: triggeredOnly } })
}

// 创建预算预警
export function createBudgetAlert(budgetId, data) {
  return request.post(`/budgets/${budgetId}/alerts`, data)
}

// 删除预算预警
export function deleteBudgetAlert(alertId) {
  return request.delete(`/budgets/alerts/${alertId}`)
}

// 获取预算汇总
export function getBudgetSummary(year) {
  return request.get('/budgets/summary', { params: { year } })
}

// 添加预算备注
export function createBudgetNote(budgetId, data) {
  return request.post(`/budgets/${budgetId}/notes`, data)
}

// 获取预算备注
export function getBudgetNotes(budgetId) {
  return request.get(`/budgets/${budgetId}/notes`)
}