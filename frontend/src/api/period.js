import request from './request'

/**
 * 会计期间 API
 */

// 获取会计期间列表
export function getPeriods(params) {
  return request.get('/period/periods', { params })
}

// 检查是否可以结账
export function checkPeriod(periodYear, periodMonth, params) {
  return request.get(`/period/periods/${periodYear}/${periodMonth}/check`, { params })
}

// 结账
export function closePeriod(periodYear, periodMonth, params) {
  return request.post(`/period/periods/${periodYear}/${periodMonth}/close`, null, { params })
}

// 反结账
export function reopenPeriod(periodYear, periodMonth, params) {
  return request.post(`/period/periods/${periodYear}/${periodMonth}/reopen`, null, { params })
}