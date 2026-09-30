import request from './request'

/**
 * 多币种管理 API
 */

// ===== 币种管理 =====

export function getCurrencies() {
  return request.get('/currencies')
}

export function createCurrency(data) {
  return request.post('/currencies', data)
}

export function updateCurrency(id, data) {
  return request.put(`/currencies/${id}`, data)
}

export function deleteCurrency(id) {
  return request.delete(`/currencies/${id}`)
}

// ===== 汇率管理 =====

export function getExchangeRates(params) {
  return request.get('/exchange-rates', { params })
}

export function createExchangeRate(data) {
  return request.post('/exchange-rates', data)
}

export function batchImportRates(data) {
  return request.post('/exchange-rates/batch', data)
}

export function deleteExchangeRate(id) {
  return request.delete(`/exchange-rates/${id}`)
}

export function convertCurrency(params) {
  return request.get('/exchange-rates/convert', { params })
}

export function getProfitLoss(params) {
  return request.get('/exchange-rates/profit-loss', { params })
}