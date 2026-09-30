import request from './request'

/**
 * 发票管理 API
 */

const BASE = '/invoices'

/**
 * 上传发票图片
 * @param {File} file - 图片文件
 * @param {string} docType - 票据类型: invoice/bank_receipt/expense_report
 * @returns {Promise<{id: number, message: string, image_path: string}>}
 */
export function uploadInvoice(file, docType = 'invoice') {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`${BASE}/upload?doc_type=${docType}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * AI 识别发票
 * @param {number} invoiceId - 发票 ID
 * @param {string} docType - 票据类型: invoice/bank_receipt/expense_report
 * @returns {Promise<{message: string, invoice: object}>}
 */
export function recognizeInvoice(invoiceId, docType = 'invoice') {
  return request.post(`${BASE}/${invoiceId}/recognize?doc_type=${docType}`)
}

/**
 * 获取发票列表
 * @param {object} params - { page, page_size, status }
 * @returns {Promise<{invoices: Array, total: number, page: number, page_size: number}>}
 */
export function getInvoiceList(params = {}) {
  return request.get(BASE, { params })
}

/**
 * 获取发票详情
 * @param {number} invoiceId
 * @returns {Promise<object>}
 */
export function getInvoiceDetail(invoiceId) {
  return request.get(`${BASE}/${invoiceId}`)
}

/**
 * 获取发票原始图片 URL
 * @param {number} invoiceId
 * @returns {string} 图片 URL
 */
export function getInvoiceImageUrl(invoiceId) {
  const authStore = useAuthStore?.()
  // 直接返回后端图片地址，浏览器会携带 cookie/token
  return `${import.meta.env.VITE_API_BASE_URL || ''}${BASE}/${invoiceId}/image`
}

/**
 * 更新发票信息
 * @param {number} invoiceId
 * @param {object} data - 更新的字段
 * @returns {Promise<{message: string, invoice: object}>}
 */
export function updateInvoice(invoiceId, data) {
  return request.put(`${BASE}/${invoiceId}`, data)
}

/**
 * 删除发票
 * @param {number} invoiceId
 * @returns {Promise<{message: string}>}
 */
export function deleteInvoice(invoiceId) {
  return request.delete(`${BASE}/${invoiceId}`)
}

/**
 * 从发票生成凭证
 * @param {number} invoiceId
 * @returns {Promise<{message: string, voucher_id: number, voucher_no: string}>}
 */
export function generateVoucherFromInvoice(invoiceId) {
  return request.post(`${BASE}/${invoiceId}/generate-voucher`)
}

// 需要 useAuthStore，但 import 会循环依赖，在函数内动态获取
import { useAuthStore } from '@/stores/auth'