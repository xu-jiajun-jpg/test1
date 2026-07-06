import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useDashboardStore = defineStore('dashboard', () => {
  const stats = ref({
    total_processed: 0,
    success_count: 0,
    fail_count: 0,
    chute_stats: [],
    recent_decisions: [],
  })
  const connected = ref(false)

  function updateStats(data) {
    stats.value = { ...stats.value, ...data }
  }

  function addDecision(decision) {
    stats.value.recent_decisions.unshift(decision)
    if (stats.value.recent_decisions.length > 20) {
      stats.value.recent_decisions.pop()
    }
  }

  const successRate = computed(() => {
    if (stats.value.total_processed === 0) return 0
    return ((stats.value.success_count / stats.value.total_processed) * 100).toFixed(1)
  })

  return { stats, connected, updateStats, addDecision, successRate }
})
