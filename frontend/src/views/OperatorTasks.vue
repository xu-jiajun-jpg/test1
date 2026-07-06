<template>
  <div class="page">
    <!-- 工作台状态栏 -->
    <div class="header-bar">
      <div>
        <h2>📦 {{ operatorName }} 的工作台</h2>
        <div style="display:flex;gap:8px;margin-top:6px;align-items:center">
          <el-tag size="small" type="warning" effect="dark">{{ shiftLabel }}</el-tag>
          <el-tag v-for="ch in chutes" :key="ch" size="small" type="primary" effect="plain">{{ ch }}</el-tag>
        </div>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <span style="font-size:13px;color:#909399">今日处理: <b style="color:#67C23A">{{ todayCompleted }}</b> 件</span>
        <el-button size="small" @click="fetchTasks" :loading="loading">🔄 刷新</el-button>
      </div>
    </div>

    <!-- 超时预警条 -->
    <div v-if="overdueTasks.length" class="overdue-bar" :class="overdueBarClass">
      <span>⚠️</span>
      <span><b>{{ overdueTasks.length }}</b> 个任务{{ hasCriticalOverdue ? '已超时' : '即将超时' }}</span>
      <span class="overdue-countdown">{{ nearestDeadline }}</span>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="12" style="margin-bottom:16px">
      <el-col :span="6"><el-card shadow="hover" class="stat stat-orange"><div class="num">{{ processingCount }}</div><div class="lab">⚙️ 执行中</div></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover" class="stat stat-green"><div class="num">{{ doneCount }}</div><div class="lab">✅ 已完成</div></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover" class="stat stat-red"><div class="num">{{ rejectedTasks.length + failedTasks.length }}</div><div class="lab">⛔ 异常</div></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover" class="stat stat-blue"><div class="num">{{ batchSelected.length }}</div><div class="lab">📋 已选</div></el-card></el-col>
    </el-row>

    <!-- 批量操作栏 -->
    <div class="batch-bar" :class="{ 'batch-ready': batchSelected.length >= 1 }">
      <div class="batch-left">
        <el-checkbox v-if="activeTaskCount" :model-value="isAllSelected" :indeterminate="isIndeterminate" @change="toggleSelectAll">
          全选执行中 ({{ activeTaskCount }})
        </el-checkbox>
        <span v-if="batchSelected.length" class="batch-count">已选 <b>{{ batchSelected.length }}</b> 件</span>
      </div>
      <div class="batch-right">
        <el-button v-if="batchSelected.length" size="small" @click="clearBatch">取消</el-button>
        <el-button type="primary" size="small" @click="batchSubmit" :loading="batchLoading" :disabled="batchSelected.length < 1">
          📦 申请发车（装车优化）
        </el-button>
      </div>
    </div>

    <!-- 快速筛选标签 -->
    <div class="filter-tabs">
      <el-radio-group v-model="activeFilter" size="small">
        <el-radio-button value="all">全部 <el-tag size="mini" round>{{ taskList.length }}</el-tag></el-radio-button>
        <el-radio-button value="active">执行中 <el-tag v-if="processingCount" size="mini" round type="warning">{{ processingCount }}</el-tag></el-radio-button>
        <el-radio-button value="completed">已完成 <el-tag v-if="doneCount" size="mini" round type="success">{{ doneCount }}</el-tag></el-radio-button>
        <el-radio-button value="stale">超时 <el-tag v-if="overdueCount" size="mini" round type="danger">{{ overdueCount }}</el-tag></el-radio-button>
      </el-radio-group>
    </div>

    <!-- 优先级任务队列（卡片列表） -->
    <div class="task-queue">
      <el-empty v-if="!filteredTasks.length" description="暂无任务" :image-size="60" />

      <div v-for="task in filteredTasks" :key="task.file_id || task.decision_id"
           class="task-card"
           :class="[
             'priority-' + taskPriority(task),
             { 'task-accepting': task._accepting, 'task-processing': task.status === 'processing',
               'task-selected': isSelected(task), 'task-done': isDone(task) }
           ]">
        <!-- 批量选择框（仅活跃任务可勾选） -->
        <el-checkbox v-if="!isDone(task)" class="batch-check" :model-value="isSelected(task)" @click.stop @change="toggleSelect(task)" />

        <!-- 紧急度色条 -->
        <div class="priority-bar" :class="'bar-' + taskPriority(task)" />

        <!-- 任务信息 -->
        <div class="task-content">
          <div class="task-top">
            <div class="task-tracking">{{ task.tracking_number || task.file_id?.slice(0,12) || '未知' }}</div>
            <div class="task-actions">
              <!-- 已完成 -->
              <template v-if="task.status === 'completed' || task.status === 'verified'">
                <el-tag size="small" :type="task.status === 'verified' ? '' : 'success'">
                  {{ task.status === 'verified' ? '核验' : '已完成' }}
                </el-tag>
                <span v-if="task.handled_by_name" style="font-size:11px;color:#909399;margin-left:4px">{{ task.handled_by_name }}</span>
              </template>
            </div>
          </div>

          <div class="task-meta">
            <el-tag size="small" type="primary" effect="plain">{{ task.target_chute }}</el-tag>
            <el-tag v-if="isActive(task)" size="small" type="warning">执行中</el-tag>
            <span class="meta-text" v-if="task.district">{{ task.district }} / {{ task.city || '' }}</span>
            <span class="meta-text" v-if="task.receiver_name">{{ task.receiver_name }}</span>
          </div>

          <div class="task-bottom">
            <span class="time-text">🕐 {{ timeAgo(task.decision_time) }}</span>
            <!-- 超时倒计时 -->
            <span v-if="task.status === 'dispatched' || task.status === 'accepted' || task.status === 'processing'"
                  class="countdown-text" :class="countdownClass(task)">
              {{ countdownDisplay(task) }}
            </span>
            <span v-if="task.urge_count" class="urge-text">📣 已被催办 {{ task.urge_count }}次</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部统计条 -->
    <div class="bottom-bar">
      <span>今日统计:</span>
      <span>📥 接收 {{ acceptedCount }}</span>
      <span>✅ 完成 {{ doneCount }}</span>
      <span>⚠️ 异常 {{ exceptionCount }}</span>
      <span>⛔ 拒收 {{ rejectedCount }}</span>
    </div>

    <!-- 拒收弹窗 -->
    <el-dialog v-model="rejectDialog" title="⛔ 拒收任务" width="420px">
      <el-form label-width="70px" size="small">
        <el-form-item label="运单号"><b>{{ rejectRow?.tracking_number || '-' }}</b></el-form-item>
        <el-form-item label="原因">
          <el-radio-group v-model="rejectReason">
            <el-radio value="too_busy">当前任务过多</el-radio>
            <el-radio value="wrong_chute">分拣口分配错误</el-radio>
            <el-radio value="not_my_area">不属于我的区域</el-radio>
            <el-radio value="other">其他</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="rejectNote" type="textarea" :rows="2" placeholder="补充说明（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialog=false">取消</el-button>
        <el-button type="danger" :loading="rejecting" @click="doReject">确认拒收</el-button>
      </template>
    </el-dialog>

    <!-- 完成弹窗（支持分流） -->
    <el-dialog v-model="completeDialog" title="✅ 确认分拣完成" width="420px">
      <el-form label-width="90px" size="small">
        <el-form-item label="运单号"><b>{{ completeRow?.tracking_number || '-' }}</b></el-form-item>
        <el-form-item label="默认分拣口"><el-tag>{{ completeRow?.target_chute }}</el-tag></el-form-item>
        <el-form-item label="分流到（可选）">
          <el-select v-model="completeTargetChute" placeholder="不改则默认" clearable style="width:100%">
            <el-option v-for="ch in chutes" :key="ch" :label="ch" :value="ch" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeDialog=false">取消</el-button>
        <el-button type="success" :loading="completing" @click="doComplete">确认完成</el-button>
      </template>
    </el-dialog>

    <!-- 异常上报弹窗 -->
    <el-dialog v-model="exceptionDialog" title="⚠️ 异常上报" width="420px">
      <el-form label-width="90px" size="small">
        <el-form-item label="运单号"><b>{{ exceptionRow?.tracking_number || '-' }}</b></el-form-item>
        <el-form-item label="异常类型">
          <el-radio-group v-model="exceptionType">
            <el-radio value="damage">🪫 破损/渗漏</el-radio>
            <el-radio value="barcode_unreadable">🔍 条码无法识别</el-radio>
            <el-radio value="district_mismatch">🗺️ 分区不匹配</el-radio>
            <el-radio value="oversized">📦 包裹超规</el-radio>
            <el-radio value="other">⋯ 其他</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="exceptionNote" type="textarea" :rows="2" placeholder="补充说明（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="exceptionDialog=false">取消</el-button>
        <el-button type="danger" :loading="exceptionSubmitting" @click="submitException">确认上报</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { useTaskStore } from '@/store/taskStore'
import request from '@/api/request'
import { createDashboardSocket } from '@/utils/websocket'
import { ElMessage, ElNotification } from 'element-plus'

const authStore = useAuthStore()
// eslint-disable-next-line no-unused-vars
const taskStore = useTaskStore()

// ===== 状态 =====
const tasks = ref([])
const chutes = ref([])
const operatorName = ref('')
const shiftLabel = ref('')
const loading = ref(false)
const activeFilter = ref('all')
const batchSelected = ref([])   // [{file_id, decision_id, tracking_number, ...}]
const batchLoading = ref(false)
let wsHandle = null

function isSelected(task) { return batchSelected.value.some(s => (s.decision_id || s.file_id) === (task.decision_id || task.file_id)) }
function toggleSelect(task) {
  const idx = batchSelected.value.findIndex(s => (s.decision_id || s.file_id) === (task.decision_id || task.file_id))
  if (idx >= 0) batchSelected.value.splice(idx, 1)
  else batchSelected.value.push(task)
}
function clearBatch() { batchSelected.value = [] }

const router = useRouter()

async function batchSubmit() {
  if (batchSelected.value.length < 1) {
    ElMessage.warning('至少选择1个包裹')
    return
  }
  // 不直接调API，先跳装车路径页，让操作员跑ACO确认后再提交
  const ids = batchSelected.value.map(t => t.decision_id || t.file_id)
  sessionStorage.setItem('pending_dispatch_ids', JSON.stringify(ids))
  clearBatch()
  router.push('/operator/logistics')
}

// 拒收
const rejectDialog = ref(false)
const rejectRow = ref(null)
const rejectReason = ref('too_busy')
const rejectNote = ref('')
const rejecting = ref(false)

// 完成
const completeDialog = ref(false)
const completeRow = ref(null)
const completeTargetChute = ref('')
const completing = ref(false)

// 异常
const exceptionDialog = ref(false)
const exceptionRow = ref(null)
const exceptionType = ref('damage')
const exceptionNote = ref('')
const exceptionSubmitting = ref(false)

// ===== 计算属性 =====
const taskList = computed(() => tasks.value || [])

const isActive = (t) => ['pending','dispatched','accepted'].includes(t.status)
const isDone = (t) => ['completed','verified'].includes(t.status)
const processingCount = computed(() => taskList.value.filter(t => isActive(t) || t.status === 'processing').length)
const doneCount = computed(() => taskList.value.filter(t => isDone(t)).length)
const rejectedTasks = computed(() => taskList.value.filter(t => t.status === 'rejected'))
const failedTasks = computed(() => taskList.value.filter(t => t.status === 'failed'))
const todayCompleted = computed(() => doneCount.value)

// 全选逻辑
const activeTaskCount = computed(() => taskList.value.filter(t => !isDone(t)).length)
const isAllSelected = computed(() => activeTaskCount.value > 0 && batchSelected.value.length >= activeTaskCount.value)
const isIndeterminate = computed(() => batchSelected.value.length > 0 && batchSelected.value.length < activeTaskCount.value)
function toggleSelectAll(val) {
  if (val) {
    // 全选所有活跃任务
    const currentIds = new Set(batchSelected.value.map(s => s.decision_id || s.file_id))
    taskList.value.filter(t => !isDone(t)).forEach(t => {
      const id = t.decision_id || t.file_id
      if (!currentIds.has(id)) batchSelected.value.push(t)
    })
  } else {
    clearBatch()
  }
}

// 超时相关
const overdueTasks = computed(() => taskList.value.filter(t => t.status === 'stale'))
const overdueCount = computed(() => overdueTasks.value.length)
const hasCriticalOverdue = computed(() => overdueTasks.value.length > 0)
const nearestDeadline = computed(() => {
  if (!overdueTasks.value.length) return ''
  return `最早超时: ${overdueTasks.value[0]?.tracking_number || ''}`
})
const overdueBarClass = computed(() => hasCriticalOverdue.value ? 'overdue-critical-bar' : 'overdue-warn-bar')

// 筛选后的任务
const filteredTasks = computed(() => {
  let list = taskList.value
  if (activeFilter.value === 'active') {
    list = list.filter(t => isActive(t) || t.status === 'processing')
  } else if (activeFilter.value === 'completed') {
    list = list.filter(t => isDone(t))
  } else if (activeFilter.value !== 'all') {
    list = list.filter(t => t.status === activeFilter.value)
  }
  // 活跃优先，已完成沉底
  return [...list].sort((a, b) => {
    const prio = { stale: 0, pending: 1, dispatched: 2, accepted: 3, processing: 4, completed: 5, verified: 6, rejected: 7, failed: 8 }
    return (prio[a.status] || 99) - (prio[b.status] || 99)
  })
})

// ===== 工具函数 =====
function timeAgo(timeStr) {
  if (!timeStr) return '-'
  const t = new Date(timeStr)
  const now = new Date()
  const diff = Math.floor((now - t) / 60000)
  if (diff < 1) return '刚刚'
  if (diff < 60) return `${diff}分钟前`
  const h = Math.floor(diff / 60)
  return `${h}小时${diff % 60}分钟前`
}

function taskPriority(task) {
  if (task.status === 'stale') return 'critical'
  if (task.status === 'dispatched') return 'high'
  if (task.status === 'accepted') return 'medium'
  if (task.status === 'processing') return 'normal'
  return 'low'
}

function countdownDisplay(task) {
  if (task.status === 'stale') return '⚠️ 已超时'
  if (task.sla_deadline) {
    const deadline = new Date(task.sla_deadline)
    const now = new Date()
    const diff = Math.max(0, Math.floor((deadline - now) / 1000))
    if (diff <= 0) return '⚠️ 即将超时'
    const m = Math.floor(diff / 60)
    const s = diff % 60
    return `⏱ ${m}:${String(s).padStart(2, '0')}`
  }
  return ''
}

function countdownClass(task) {
  if (task.status === 'stale') return 'cd-critical'
  if (task.sla_deadline) {
    const deadline = new Date(task.sla_deadline)
    const now = new Date()
    const diff = Math.floor((deadline - now) / 60000)
    if (diff < 5) return 'cd-critical'
    if (diff < 15) return 'cd-warn'
    return 'cd-normal'
  }
  return ''
}

// ===== API调用 =====
async function fetchTasks() {
  loading.value = true
  try {
    const res = await request.get('/api/operators/my/tasks')
    const d = res.data || {}
    // 保留正在进行的加载状态
    const oldMap = {}
    tasks.value.forEach(t => { oldMap[t.decision_id || t.file_id] = { _processing: t._processing, _completing: t._completing } })
    tasks.value = (d.tasks || []).map(t => ({
      ...t,
      _accepting: false, _starting: false,
      _processing: oldMap[t.decision_id || t.file_id]?._processing || false,
      _completing: oldMap[t.decision_id || t.file_id]?._completing || false,
    }))
    chutes.value = d.chutes || []
    operatorName.value = d.operator_name || authStore.user?.display_name || ''
    shiftLabel.value = d.shift || ''
  } catch { /* ignore */ }
  loading.value = false
}

// --- 以下函数保留兼容，前端已不再展示个体操作按钮 ---
/* eslint-disable no-unused-vars */
async function acceptTask(task) {
  task._accepting = true
  try {
    await request.post('/api/tasks/accept', { decision_id: task.decision_id || task.file_id })
    task.status = 'accepted'
    ElMessage.success('✅ 已接收任务')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '接收失败')
  }
  task._accepting = false
}

// 开始执行（保留兼容）
async function startTask(task) {
  task._starting = true
  try {
    await request.post('/api/tasks/start', { decision_id: task.decision_id || task.file_id })
    task.status = 'processing'
    ElMessage.success('⚙️ 开始执行')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
  task._starting = false
}

// 拒收
function openRejectDialog(task) {
  rejectRow.value = task
  rejectReason.value = 'too_busy'
  rejectNote.value = ''
  rejectDialog.value = true
}

async function doReject() {
  rejecting.value = true
  try {
    await request.post('/api/tasks/reject', {
      decision_id: rejectRow.value.decision_id || rejectRow.value.file_id,
      reason: `${rejectReason.value}: ${rejectNote.value}`,
    })
    ElMessage.success('已拒收，等待管理员处理')
    tasks.value = tasks.value.filter(t => t.file_id !== rejectRow.value.file_id)
    rejectDialog.value = false
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '拒收失败')
  }
  rejecting.value = false
}

// 完成
function openCompleteDialog(task) {
  completeRow.value = task
  completeTargetChute.value = ''
  completeDialog.value = true
}

async function doComplete() {
  completing.value = true
  try {
    await request.post('/api/tasks/complete', {
      decision_id: completeRow.value.decision_id || completeRow.value.file_id,
      target_chute: completeTargetChute.value || '',
    })
    ElMessage.success('✅ 分拣完成')
    completeRow.value.status = 'completed'
    completeDialog.value = false
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
  completing.value = false
}

// 异常上报
function openExceptionDialog(task) {
  exceptionRow.value = task
  exceptionType.value = 'damage'
  exceptionNote.value = ''
  exceptionDialog.value = true
}
/* eslint-enable no-unused-vars */

async function submitException() {
  exceptionSubmitting.value = true
  try {
    await request.post('/api/operators/tasks/exception', {
      file_id: exceptionRow.value.file_id,
      tracking_number: exceptionRow.value.tracking_number,
      target_chute: exceptionRow.value.target_chute,
      exception_type: exceptionType.value,
      note: exceptionNote.value,
    })
    ElMessage.success('异常已上报管理员')
    tasks.value = tasks.value.filter(t => t.file_id !== exceptionRow.value.file_id)
    exceptionDialog.value = false
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '上报失败')
  }
  exceptionSubmitting.value = false
}

// WebSocket + 轮询初始化
let pollTimer = null
onMounted(() => {
  fetchTasks()
  // 同分拣口共享状态：每5秒刷新一次
  pollTimer = setInterval(fetchTasks, 5000)
  wsHandle = createDashboardSocket({
    onMessage: (data) => {
      const event = data.event
      const d = data.data || {}
      if (event === 'task_dispatched') { ElNotification({ title: '📦 新任务到达', message: `包裹分配至 ${d.target_chute}`, type: 'info', duration: 4000 }); fetchTasks() }
      if (event === 'task_urged') { ElNotification({ title: '⚠️ 管理员催办', message: `请尽快处理包裹 ${d.tracking_number || ''}`, type: 'warning', duration: 10000 }) }
      if (event === 'task_reassigned') { ElNotification({ title: '🔄 任务已改派', message: `包裹已改派至 ${d.new_chute || '其他'} 分拣口`, type: 'info', duration: 5000 }) }
      if (event === 'task_verified') { ElNotification({ title: '✅ 任务已核验', message: `包裹已被管理员核验通过`, type: 'success', duration: 5000 }) }
      if (event === 'exception_resolved') { ElNotification({ title: '✅ 异常已处理', message: `异常包裹已由管理员解决`, type: 'success', duration: 5000 }); fetchTasks() }
    },
  })
})

onUnmounted(() => {
  if (wsHandle) wsHandle.disconnect()
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.page { padding: 0; }
.header-bar { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.header-bar h2 { color: #2c3e50; margin: 0; font-size: 20px; }

/* 超时预警条 */
.overdue-bar { display: flex; align-items: center; gap: 8px; padding: 10px 16px; border-radius: 10px; margin-bottom: 16px; font-size: 14px; font-weight: 600; }
.overdue-warn-bar { background: #FFF3E0; color: #E65100; border: 1px solid #FFB74D; }
.overdue-critical-bar { background: #FFEBEE; color: #C62828; border: 1px solid #EF5350; animation: pulse-overdue 2s infinite; }
@keyframes pulse-overdue { 0%,100%{opacity:1} 50%{opacity:.7} }
.overdue-countdown { margin-left: auto; font-size: 12px; opacity: .7; }

/* 统计卡片 */
.stat { text-align: center; border-radius: 12px; padding: 14px; color: #fff; }
.stat .num { font-size: 24px; font-weight: 800; }
.stat .lab { font-size: 12px; opacity: .85; margin-top: 4px; }
.stat-blue { background: linear-gradient(135deg,#667eea,#764ba2); }
.stat-orange { background: linear-gradient(135deg,#fa8231,#f7b731); }
.stat-green { background: linear-gradient(135deg,#43e97b,#38f9d7); color: #1a3a1a; }
.stat-red { background: linear-gradient(135deg,#f5576c,#e74c3c); }

.filter-tabs { margin-bottom: 16px; }

/* 批量操作栏 */
.batch-bar { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: #ebeef5; color: #606266; border-radius: 10px; margin-bottom: 12px; font-size: 14px; transition: all 0.3s; }
.batch-bar.batch-ready { background: linear-gradient(135deg, #409EFF, #67C23A); color: #fff; }
.batch-bar.batch-ready b { color: #FFD700; }
.batch-left { display: flex; align-items: center; gap: 16px; }
.batch-right { display: flex; align-items: center; gap: 8px; }
.batch-count { margin-left: 4px; }
.batch-check { margin-right: 8px; flex-shrink: 0; }
.task-card { transition: all 0.2s; }
.task-card.task-selected { border-color: #409EFF; background: #ecf5ff; box-shadow: 0 0 0 1px #409EFF inset; }
.task-card.task-done { opacity: 0.6; background: #f5f5f5; }

/* 任务卡片 */
.task-queue { display: flex; flex-direction: column; gap: 10px; padding-bottom: 60px; }
.task-card { display: flex; background: #fff; border-radius: 12px; overflow: hidden; border: 1px solid #e8e8e8; transition: all 0.25s; }
.task-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,.08); transform: translateY(-1px); }
.task-card.task-accepting { background: #f0f9ff; border-color: #409EFF; }
.task-card.task-processing { background: #FFF7E6; }

.priority-bar { width: 4px; min-height: 80px; flex-shrink: 0; }
.bar-critical { background: #EF4444; }
.bar-high { background: #F59E0B; }
.bar-medium { background: #409EFF; }
.bar-normal { background: #67C23A; }
.bar-low { background: #e8e8e8; }

.task-content { flex: 1; padding: 12px 16px; display: flex; flex-direction: column; gap: 8px; }
.task-top { display: flex; justify-content: space-between; align-items: center; }
.task-tracking { font-weight: 700; font-size: 15px; color: #303133; letter-spacing: .5px; }
.task-actions { display: flex; gap: 6px; }
.task-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.meta-text { font-size: 12px; color: #909399; }
.task-bottom { display: flex; gap: 16px; align-items: center; }
.time-text { font-size: 11px; color: #b0b0b0; }
.countdown-text { font-size: 12px; font-weight: 600; }
.cd-normal { color: #67C23A; }
.cd-warn { color: #F59E0B; }
.cd-critical { color: #EF4444; animation: blink 1s infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
.urge-text { font-size: 11px; color: #EF4444; }

/* 底部统计条 */
.bottom-bar { position: fixed; bottom: 0; left: 0; right: 0; background: rgba(44,62,80,.92); color: #fff; display: flex; gap: 20px; padding: 8px 20px; font-size: 12px; justify-content: center; backdrop-filter: blur(8px); z-index: 100; }
.bottom-bar span { opacity: .9; }
</style>
