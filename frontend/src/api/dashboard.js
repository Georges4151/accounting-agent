import request from './request'

/**
 * 数据看板 API
 */

// 关键指标概览
export function getOverview(period) {
  return request.get('/dashboard/overview', { params: { period } })
}

// 收支趋势
export function getTrends(months = 6) {
  return request.get('/dashboard/trends', { params: { months } })
}

// 科目占比分析
export function getCategoryBreakdown(period) {
  return request.get('/dashboard/category-breakdown', { params: { period } })
}

// 月度对比
export function getMonthlyComparison(period) {
  return request.get('/dashboard/monthly-comparison', { params: { period } })
}

// 财务健康评分
export function getHealthScore(period) {
  return request.get('/dashboard/health-score', { params: { period } })
}

// 最近凭证
export function getRecentVouchers(limit = 5) {
  return request.get('/dashboard/recent-vouchers', { params: { limit } })
}

// 异常检测
export function getAnomalies(params) {
  return request.get('/anomalies', { params })
}

// 工作看板
export function getWorkbench() {
  return request.get('/dashboard/workbench')
}