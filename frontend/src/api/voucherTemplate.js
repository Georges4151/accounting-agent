import request from './request'

/**
 * 凭证模板 API
 */

// 获取模板列表
export function getTemplates(params) {
  return request.get('/voucher-templates', { params })
}

// 获取单个模板详情
export function getTemplate(id) {
  return request.get(`/voucher-templates/${id}`)
}

// 创建模板
export function createTemplate(data) {
  return request.post('/voucher-templates', data)
}

// 更新模板
export function updateTemplate(id, data) {
  return request.put(`/voucher-templates/${id}`, data)
}

// 删除模板
export function deleteTemplate(id) {
  return request.delete(`/voucher-templates/${id}`)
}

// 应用模板创建凭证
export function applyTemplate(id, data) {
  return request.post(`/voucher-templates/${id}/apply`, data)
}