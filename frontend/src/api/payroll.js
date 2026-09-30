import request from './request'

/**
 * 工资管理 API
 */

// ===== 工资项目管理 =====

export function getSalaryItems() {
  return request.get('/salary-items')
}

export function createSalaryItem(data) {
  return request.post('/salary-items', data)
}

export function updateSalaryItem(id, data) {
  return request.put(`/salary-items/${id}`, data)
}

export function deleteSalaryItem(id) {
  return request.delete(`/salary-items/${id}`)
}

// ===== 工资记录管理 =====

export function getSalaryRecords(params) {
  return request.get('/salary-records', { params })
}

export function createSalaryRecord(data) {
  return request.post('/salary-records', data)
}

export function updateSalaryRecord(id, data) {
  return request.put(`/salary-records/${id}`, data)
}

export function batchImportSalary(data) {
  return request.post('/salary-records/batch', data)
}

export function confirmSalary(id) {
  return request.post(`/salary-records/${id}/confirm`)
}

export function generateSalaryVoucher(data) {
  return request.post('/salary-records/generate-voucher', data)
}