import request from './request'

/**
 * 知识库管理 API
 */

// 上传文档（FormData需要浏览器自动设置Content-Type含boundary）
export function uploadDocument(formData) {
  return request.post('/knowledge/upload', formData, {
    transformRequest: [(data, headers) => {
      // 删除axios默认的application/json，让浏览器自动设置为multipart/form-data
      if (headers) {
        delete headers['Content-Type']
      }
      return data
    }]
  })
}

// 获取文档列表
export function getDocuments(params = {}) {
  return request.get('/knowledge/documents', { params })
}

// 删除文档
export function deleteDocument(docId) {
  return request.delete(`/knowledge/documents/${docId}`)
}

// 重建索引
export function rebuildIndex() {
  return request.post('/knowledge/rebuild')
}

// 获取索引统计
export function getKnowledgeStats() {
  return request.get('/knowledge/stats')
}

// 获取分类列表
export function getCategories() {
  return request.get('/knowledge/categories')
}

// 测试搜索
export function searchKnowledge(data) {
  return request.post('/knowledge/search', data)
}

// ===== 知识库自动更新调度 =====

// 手动触发更新
export function triggerSchedulerUpdate() {
  return request.post('/knowledge/scheduler/trigger')
}

// 获取调度器状态
export function getSchedulerStatus() {
  return request.get('/knowledge/scheduler/status')
}

// 获取更新日志
export function getSchedulerLogs(limit = 10) {
  return request.get('/knowledge/scheduler/logs', { params: { limit } })
}

// 仅获取政策更新
export function fetchPolicies() {
  return request.post('/knowledge/scheduler/fetch-policies')
}

// 检查文档过期
export function checkStaleness() {
  return request.post('/knowledge/scheduler/check-staleness')
}