import request from './request'

/**
 * 一键生成模拟包裹
 * @param {number} count - 生成数量 1-40
 * @param {number} damageRate - 破损占比 0-1，默认0.15
 * @returns {Promise}
 */
export function demoGenerate(count = 10, damageRate = 0.15) {
  return request.post('/api/demo/generate', { count, damage_rate: damageRate }, { timeout: 120000 })
}
