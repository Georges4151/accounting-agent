import request from './request'

/**
 * 期末结转 API
 */

// 执行期末结转
export function carryForward(data) {
  return request.post('/vouchers/period-close/carry-forward', data)
}