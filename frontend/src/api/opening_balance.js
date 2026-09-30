import request from './request'

/**
 * 期初余额 API
 */

// 获取期初余额列表
export function getOpeningBalances(bookId, fiscalYear) {
  return request.get(`/books/${bookId}/opening-balances`, {
    params: { fiscal_year: fiscalYear }
  })
}

// 批量保存期初余额
export function saveOpeningBalances(bookId, data) {
  return request.post(`/books/${bookId}/opening-balances`, data)
}

// 试算平衡检查
export function checkTrialBalance(bookId, fiscalYear) {
  return request.get(`/books/${bookId}/opening-balances/trial-balance`, {
    params: { fiscal_year: fiscalYear }
  })
}