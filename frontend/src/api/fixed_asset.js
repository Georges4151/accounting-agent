import request from './request'

/**
 * 固定资产 API
 */

export function getAssets(params) {
  return request.get('/fixed-assets', { params })
}

export function createAsset(data) {
  return request.post('/fixed-assets', data)
}

export function updateAsset(id, data) {
  return request.put(`/fixed-assets/${id}`, data)
}

export function deleteAsset(id) {
  return request.delete(`/fixed-assets/${id}`)
}

export function calculateDepreciation(period) {
  return request.post('/fixed-assets/depreciate', null, { params: { period } })
}

export function getDepreciationHistory(assetId) {
  return request.get(`/fixed-assets/${assetId}/depreciation-history`)
}