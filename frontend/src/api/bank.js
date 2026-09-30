import request from './request'

/**
 * 银行对账 API
 */

// 获取银行对账单列表
export function getBankStatements(params) {
  return request.get('/bank/statements', { params })
}

// 导入银行对账单
export function importBankStatements(file, bankAccount) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/bank/statements/import', formData, {
    params: { bank_account: bankAccount },
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 自动匹配
export function autoMatchStatements(bankAccount, dateTolerance = 3, amountTolerance = 0.01) {
  return request.post('/bank/statements/auto-match', null, {
    params: {
      bank_account: bankAccount,
      date_tolerance: dateTolerance,
      amount_tolerance: amountTolerance,
    },
  })
}

// 删除单条记录
export function deleteBankStatement(id) {
  return request.delete(`/bank/statements/${id}`)
}

// 清空对账单
export function clearBankStatements(bankAccount) {
  return request.delete('/bank/statements', { params: { bank_account: bankAccount } })
}

// 获取对账报告
export function getReconciliationReport(params) {
  return request.get('/bank/reconciliation', { params })
}

// 手动匹配
export function manualMatchStatement(statementId, voucherItemId) {
  return request.post(`/bank/statements/${statementId}/match`, {
    voucher_item_id: voucherItemId,
  })
}

// 取消匹配
export function unmatchStatement(statementId) {
  return request.post(`/bank/statements/${statementId}/unmatch`)
}

// 手动添加银行流水
export function addManualStatement(data) {
  return request.post('/bank/statements/manual', data)
}

// 查询可匹配的凭证分录
export function listVoucherItems(params) {
  return request.get('/bank/voucher-items', { params })
}

// 导出对账结果
export function exportReconciliation(params) {
  return request.get('/bank/reconciliation/export', {
    params,
    responseType: 'blob',
  })
}