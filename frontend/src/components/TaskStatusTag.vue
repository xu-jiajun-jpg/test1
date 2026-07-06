<template>
  <el-tag
    :type="tagType"
    :class="['task-status-tag', { 'pulse-warning': status === 'stale', 'pulse-processing': status === 'processing' }]"
    size="small"
    effect="dark"
  >
    <span v-if="status === 'dispatched'">📤</span>
    <span v-else-if="status === 'accepted'">📥</span>
    <span v-else-if="status === 'processing'">⚙️</span>
    <span v-else-if="status === 'completed'">✅</span>
    <span v-else-if="status === 'verified'">🔍</span>
    <span v-else-if="status === 'rejected'">⛔</span>
    <span v-else-if="status === 'stale'">⚠️</span>
    <span v-else-if="status === 'failed'">❌</span>
    <span v-else>📋</span>
    {{ label }}
  </el-tag>
</template>

<script setup>
/* global defineProps */
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: 'pending' },
})

const statusMap = {
  pending:      { type: 'info', label: '待派发' },
  dispatched:   { type: 'primary', label: '已派发' },
  accepted:     { type: 'success', label: '已接收' },
  processing:   { type: 'warning', label: '执行中' },
  completed:    { type: 'success', label: '已完成' },
  verified:     { type: '', label: '已核验' },
  rejected:     { type: 'danger', label: '已拒收' },
  stale:        { type: 'danger', label: '超时滞留' },
  failed:       { type: 'danger', label: '异常暂停' },
}

const tagType = computed(() => statusMap[props.status]?.type || 'info')
const label = computed(() => statusMap[props.status]?.label || props.status)
</script>

<style scoped>
.task-status-tag {
  min-width: 80px;
  text-align: center;
  transition: all 0.3s;
}
.pulse-warning {
  animation: pulse-red 1.5s infinite;
}
.pulse-processing {
  animation: pulse-orange 2s infinite;
}
@keyframes pulse-red {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
}
@keyframes pulse-orange {
  0%, 100% { box-shadow: 0 0 0 0 rgba(230, 162, 60, 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(230, 162, 60, 0); }
}
</style>
