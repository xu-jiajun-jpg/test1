import request from './request'

export function uploadSingle(file, onProgress) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/api/upload/single', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    },
  })
}

export function uploadBatch(files) {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f))
  return request.post('/api/upload/batch', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getUploadRecords(page = 1, pageSize = 20) {
  return request.get('/api/upload/records', { params: { page, page_size: pageSize } })
}
