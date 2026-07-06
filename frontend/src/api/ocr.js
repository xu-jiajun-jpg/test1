import request from './request'

export function recognizeImage(fileId) {
  return request.post(`/api/ocr/recognize/${fileId}`)
}

export function getOcrResults(page = 1, pageSize = 20) {
  return request.get('/api/ocr/results', { params: { page, page_size: pageSize } })
}

export function getOcrResult(fileId) {
  return request.get(`/api/ocr/results/${fileId}`)
}
