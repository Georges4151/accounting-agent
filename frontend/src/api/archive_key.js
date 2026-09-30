import request from './request'

/**
 * 归档密钥 API
 */

// 查询密钥状态
export function getKeyStatus() {
  return request.get('/archive-key/status')
}

// 检测已连接的 USB 存储设备
export function detectUsbDrives() {
  return request.get('/archive-key/usb-drives')
}

// 生成密钥文件（返回二进制数据）
export function generateKey(label = '默认密钥', usbSerial = '') {
  return request.post('/archive-key/generate', null, {
    params: { key_label: label, usb_serial: usbSerial || null },
    responseType: 'blob',
  })
}

// 验证密钥文件（返回 token，USB 序列号由服务端自动检测）
export function verifyKey(keyFile, operation = 'archive', bookId = null) {
  const formData = new FormData()
  formData.append('key_file', keyFile)
  const params = { operation }
  if (bookId) params.book_id = bookId
  return request.post('/archive-key/verify', formData, {
    params,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}