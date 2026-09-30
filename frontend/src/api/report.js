import request from './request'

/**
 * 财务报表 API
 */

// 资产负债表
export function getBalanceSheet(params) {
  return request.get('/reports/balance-sheet', { params })
}

// 利润表
export function getIncomeStatement(params) {
  return request.get('/reports/income-statement', { params })
}

// 现金流量表
export function getCashFlow(params) {
  return request.get('/reports/cash-flow', { params })
}

// 科目余额表
export function getAccountLedger(params) {
  return request.get('/reports/account-ledger', { params })
}

// 科目余额表（v2，含科目类型和余额方向）
export function getTrialBalance(params) {
  return request.get('/reports/trial-balance', { params })
}

// 试算平衡表
export function getTrialBalanceSummary(params) {
  return request.get('/reports/trial-balance-summary', { params })
}

// 多期间对比报表
export function getComparison(reportType, periods, compareType = 'monthly') {
  return request.get('/reports/comparison', {
    params: {
      report_type: reportType,
      periods: periods,
      compare_type: compareType
    }
  })
}

// 总账
export function getGeneralLedger(params) {
  return request.get('/reports/general-ledger', { params })
}

// 明细账
export function getSubsidiaryLedger(params) {
  return request.get('/reports/subsidiary-ledger', { params })
}

// 日记账
export function getJournal(params) {
  return request.get('/reports/journal', { params })
}

// 导出报表（返回文件 blob）
export function exportReport(type, params) {
  return request.get(`/reports/export/${type}`, {
    params,
    responseType: 'blob'
  })
}

// 财务指标分析
export function getFinancialRatios(params) {
  return request.get('/reports/financial-ratios', { params })
}