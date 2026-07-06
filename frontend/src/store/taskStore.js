import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 任务状态管理 Store — 统一管理任务列表、状态转换、WebSocket事件
 * 覆盖管理员端和操作员端的两端任务状态同步
 */
export const useTaskStore = defineStore('task', () => {
  // ===== 状态 =====
  const taskStatusSummary = ref({
    pending: 0, dispatched: 0, accepted: 0, processing: 0,
    completed: 0, verified: 0, rejected: 0, stale: 0, failed: 0,
  })
  const operatorWorkload = ref([])
  const staleTasks = ref([])
  const totalTasks = ref(0)
  const connected = ref(false)

  // ===== 计算属性 =====
  const totalActive = computed(() =>
    taskStatusSummary.value.dispatched +
    taskStatusSummary.value.accepted +
    taskStatusSummary.value.processing
  )
  const totalPending = computed(() => taskStatusSummary.value.pending)
  const totalStale = computed(() => taskStatusSummary.value.stale)
  const totalCompleted = computed(() =>
    taskStatusSummary.value.completed + taskStatusSummary.value.verified
  )

  // ===== 状态颜色映射 =====
  const statusColors = {
    pending: '#909399',
    dispatched: '#409EFF',
    accepted: '#67C23A',
    processing: '#E6A23C',
    completed: '#67C23A',
    verified: '#8B5CF6',
    rejected: '#F56C6C',
    stale: '#EF4444',
    failed: '#F56C6C',
  }

  const statusLabels = {
    pending: '待派发',
    dispatched: '已派发',
    accepted: '已接收',
    processing: '执行中',
    completed: '已完成',
    verified: '已核验',
    rejected: '已拒收',
    stale: '超时滞留',
    failed: '异常暂停',
  }

  // ===== 操作 =====
  function updateSummary(data) {
    if (data.status_counts) {
      taskStatusSummary.value = { ...taskStatusSummary.value, ...data.status_counts }
    }
    if (data.total !== undefined) totalTasks.value = data.total
    if (data.operator_load) operatorWorkload.value = data.operator_load
  }

  function updateStaleTasks(tasks) {
    staleTasks.value = tasks || []
  }

  function incrementStatus(status) {
    if (taskStatusSummary.value[status] !== undefined) {
      taskStatusSummary.value[status]++
    }
  }

  function decrementStatus(status) {
    if (taskStatusSummary.value[status] !== undefined && taskStatusSummary.value[status] > 0) {
      taskStatusSummary.value[status]--
    }
  }

  function handleWebSocketEvent(data) {
    if (!data || !data.event) return
    const event = data.event
    const d = data.data || {}

    switch (event) {
      case 'task_dispatched':
        incrementStatus('dispatched')
        decrementStatus('pending')
        break
      case 'task_accepted':
        incrementStatus('accepted')
        decrementStatus('dispatched')
        break
      case 'task_rejected':
        incrementStatus('rejected')
        decrementStatus('dispatched')
        break
      case 'task_processing':
        incrementStatus('processing')
        decrementStatus('accepted')
        break
      case 'task_completed':
        incrementStatus('completed')
        decrementStatus('processing')
        break
      case 'task_verified':
        incrementStatus('verified')
        decrementStatus('completed')
        break
      case 'task_stale':
        incrementStatus('stale')
        if (d.decision_id && staleTasks.value) {
          staleTasks.value = [
            { decision_id: d.decision_id, chute: d.chute, overdue_minutes: d.overdue_minutes },
            ...staleTasks.value,
          ].slice(0, 50)
        }
        break
      case 'task_reassigned':
        // 改派不影响整体状态计数
        break
      case 'status_sync':
        if (d.status_counts) {
          taskStatusSummary.value = { ...taskStatusSummary.value, ...d.status_counts }
        }
        break
    }
  }

  return {
    taskStatusSummary, operatorWorkload, staleTasks, totalTasks, connected,
    totalActive, totalPending, totalStale, totalCompleted,
    statusColors, statusLabels,
    updateSummary, updateStaleTasks, handleWebSocketEvent,
    incrementStatus, decrementStatus,
  }
})
