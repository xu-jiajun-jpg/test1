import request from './request'

export function getStatsSummary() {
  return request.get('/api/stats/summary')
}

export function getRecentDecisions() {
  return request.get('/api/stats/recent')
}
