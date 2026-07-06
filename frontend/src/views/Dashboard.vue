<template>
    <div class="dashboard">
      <div class="dash-header">
        <h2>📊 分拣实时大屏</h2>
        <span class="live-badge"><span class="pulse"></span>实时监控中</span>
      </div>

      <!-- 实时任务状态行 -->
      <div class="task-status-row">
        <div class="ts-card ts-blue">
          <div class="ts-num">{{ taskSummary.pending }}</div>
          <div class="ts-lab">📋 待派发</div>
        </div>
        <div class="ts-card ts-cyan">
          <div class="ts-num">{{ taskSummary.dispatched }}</div>
          <div class="ts-lab">📤 派发中</div>
        </div>
        <div class="ts-card ts-purple">
          <div class="ts-num">{{ taskSummary.accepted + taskSummary.processing }}</div>
          <div class="ts-lab">⚙️ 执行中</div>
        </div>
        <div class="ts-card ts-green">
          <div class="ts-num">{{ taskSummary.completed + taskSummary.verified }}</div>
          <div class="ts-lab">✅ 待核验</div>
        </div>
        <div class="ts-card" :class="taskSummary.stale > 0 ? 'ts-red pulse-red-bg' : 'ts-orange'">
          <div class="ts-num">{{ taskSummary.stale }}</div>
          <div class="ts-lab">⚠️ 超时滞留</div>
        </div>
        <div class="ts-card ts-gray">
          <div class="ts-num">{{ taskSummary.failed }}</div>
          <div class="ts-lab">❌ 异常暂停</div>
        </div>
      </div>

      <!-- KPI 卡片 -->
      <div class="kpi-grid">
        <div class="kpi-card kpi-blue">
          <div class="kpi-icon">📤</div><div class="kpi-num">{{ stats.total_uploaded }}</div><div class="kpi-label">总上传</div>
        </div>
        <div class="kpi-card kpi-purple">
          <div class="kpi-icon">📦</div><div class="kpi-num">{{ stats.total_decisions }}</div><div class="kpi-label">总分拣</div>
        </div>
        <div class="kpi-card kpi-green">
          <div class="kpi-icon">✅</div><div class="kpi-num">{{ stats.success_count }}</div><div class="kpi-label">成功分拣</div>
        </div>
        <div class="kpi-card kpi-red">
          <div class="kpi-icon">⚠️</div><div class="kpi-num">{{ failTotal }}</div><div class="kpi-label">异常</div>
        </div>
        <div class="kpi-card kpi-teal">
          <div class="kpi-icon">🎯</div><div class="kpi-num">{{ successRate }}%</div><div class="kpi-label">分拣成功率</div>
        </div>
        <div class="kpi-card kpi-orange">
          <div class="kpi-icon">⚙️</div><div class="kpi-num">{{ stats.oee || 0 }}%</div><div class="kpi-label">OEE 设备效率</div>
        </div>
      </div>

      <!-- 第二行 KPI -->
      <div class="kpi-grid kpi-grid-4">
        <div class="kpi-card kpi-mini">
          <div class="kpi-num">{{ stats.quality_rate || 100 }}%</div><div class="kpi-label">质量率</div>
        </div>
        <div class="kpi-card kpi-mini">
          <div class="kpi-num">{{ stats.availability || 100 }}%</div><div class="kpi-label">可用性</div>
        </div>
        <div class="kpi-card kpi-mini">
          <div class="kpi-num">{{ stats.utilization || 100 }}%</div><div class="kpi-label">利用率</div>
        </div>
        <div class="kpi-card kpi-mini" style="cursor:default">
          <el-dropdown @command="downloadReport" trigger="click">
            <div style="text-align:center">
              <div class="kpi-num" style="font-size:18px;color:#409EFF">📄</div>
              <div class="kpi-label">报表导出</div>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="daily">📋 日报</el-dropdown-item>
                <el-dropdown-item command="weekly">📊 周报</el-dropdown-item>
                <el-dropdown-item command="monthly">📈 月报</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <!-- 图表区域 -->
      <div class="chart-grid">
        <el-card shadow="hover" class="chart-card">
          <template #header><div class="card-title">📊 分拣口吞吐量</div></template>
          <v-chart :option="chuteOption" style="height:320px" autoresize />
        </el-card>
        <el-card shadow="hover" class="chart-card">
          <template #header><div class="card-title">📋 最近分拣决策</div></template>
          <el-table :data="recentDecisions" max-height="320" size="small" stripe>
            <el-table-column prop="tracking_number" label="运单号" width="140" />
            <el-table-column prop="district" label="分区" width="60" />
            <el-table-column prop="target_chute" label="分拣口" width="100" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" size="small" effect="dark">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="时间" width="90">
              <template #default="{ row }">{{ row.decision_time?.slice(11,19) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
        <el-card shadow="hover" class="chart-card">
          <template #header><div class="card-title">🎯 分拣成功率仪表盘</div></template>
          <v-chart :option="gaugeOption" style="height:320px" autoresize />
        </el-card>
        <el-card shadow="hover" class="chart-card">
          <template #header><div class="card-title">🍩 分拣口分布</div></template>
          <v-chart :option="chutePieOption" style="height:320px" autoresize />
        </el-card>
      </div>

      <!-- 操作员实时状态 -->
      <el-card shadow="hover" style="margin-top:16px">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span class="card-title">🔧 操作员实时状态</span>
            <el-button size="small" @click="fetchOperatorStats" :loading="opStatsLoading">🔄 刷新</el-button>
          </div>
        </template>
        <div v-if="operatorStats.length" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px">
          <div v-for="op in operatorStats" :key="op.operator_id" class="op-card" :class="{ 'op-offline': op.status !== 'active' }">
            <div class="op-header">
              <span class="op-name">👤 {{ op.name }}</span>
              <el-tag :type="op.status === 'active' ? 'success' : 'info'" size="small" effect="dark">
                {{ op.status === 'active' ? '🟢 在线' : '⚫ 离线' }}
              </el-tag>
            </div>
            <div class="op-body">
              <div class="op-chutes">
                <el-tag v-for="ch in op.chutes" :key="ch" size="small" effect="plain" style="margin:2px">{{ ch }}</el-tag>
                <span v-if="!op.chutes.length" style="font-size:11px;color:#999">未绑定分拣口</span>
              </div>
              <div class="op-stats">
                <span>⏳ 待处理: <b>{{ op.pending }}</b></span>
                <span>✅ 已处理: <b>{{ op.handled }}</b></span>
                <span>⏰ {{ op.shift === 'morning' ? '早班' : op.shift === 'afternoon' ? '中班' : op.shift === 'night' ? '晚班' : '排班' }}</span>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无在线操作员" :image-size="60" />
      </el-card>

      <!-- 峰谷分析 -->
      <el-card shadow="hover" style="margin-top:16px">
        <template #header><div class="card-title">📈 峰谷分析 (24小时)</div></template>
        <v-chart :option="peakOption" style="height:280px" autoresize />
      </el-card>

      <!-- 报表弹窗 -->
      <el-dialog v-model="reportDialog" :title="'📊 ' + reportData.title" width="600px">
        <div v-if="reportData.summary">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="总分拣">{{ reportData.summary.total_decisions }}</el-descriptions-item>
            <el-descriptions-item label="成功数">{{ reportData.summary.success_count }}</el-descriptions-item>
            <el-descriptions-item label="OEE">{{ reportData.summary.oee }}%</el-descriptions-item>
            <el-descriptions-item label="质量率">{{ reportData.summary.quality_rate }}%</el-descriptions-item>
            <el-descriptions-item label="异常数">{{ reportData.summary.exception_count }}</el-descriptions-item>
            <el-descriptions-item label="生成时间">{{ reportData.generated_at }}</el-descriptions-item>
          </el-descriptions>
          <div style="margin-top:16px">
            <p style="font-weight:bold;margin-bottom:8px">📋 分析洞察</p>
            <el-tag v-for="(ins,i) in reportData.insights" :key="i" style="display:block;margin:4px 0;text-align:left;white-space:normal;height:auto;padding:8px 12px" effect="plain">
              {{ ins }}
            </el-tag>
          </div>
        </div>
        <template #footer>
          <el-button @click="reportDialog=false">关闭</el-button>
          <el-button type="primary" @click="exportReport">导出Excel</el-button>
        </template>
      </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getStatsSummary, getRecentDecisions } from '@/api/dashboard'
import { createDashboardSocket } from '@/utils/websocket'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const stats = ref({ total_uploaded: 0, total_decisions: 0, success_count: 0, fail_count: 0, exception_count: 0, oee: 0, quality_rate: 100, availability: 100, utilization: 100, peak_valley: [], chute_stats: [] })
const recentDecisions = ref([])
const operatorStats = ref([])
const opStatsLoading = ref(false)
const taskSummary = ref({ pending: 0, dispatched: 0, accepted: 0, processing: 0, completed: 0, verified: 0, rejected: 0, stale: 0, failed: 0 })
let wsHandle = null

const failTotal = computed(() => (stats.value.fail_count || 0) + (stats.value.exception_count || 0))
const successRate = computed(() => {
  if (!stats.value.total_decisions) return 0
  return ((stats.value.success_count / stats.value.total_decisions) * 100).toFixed(1)
})

const chuteOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 50, right: 20, top: 10, bottom: 30 },
  xAxis: { type: 'category', data: (stats.value.chute_stats || []).map(c => c.chute), axisLabel: { rotate: 0, fontSize: 11 } },
  yAxis: { type: 'value' },
  series: [{
    type: 'bar', data: (stats.value.chute_stats || []).map(c => c.count),
    itemStyle: { borderRadius: [6, 6, 0, 0], color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
      colorStops: [{offset:0,color:'#667eea'},{offset:1,color:'#764ba2'}] } },
    label: { show: true, position: 'top', fontSize: 11, fontWeight: 'bold' },
    barWidth: '50%',
  }],
}))

const chutePieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} 件 ({d}%)' },
  legend: { bottom: 0 },
  series: [{
    type: 'pie', radius: ['45%', '75%'], center: ['50%', '45%'],
    data: (stats.value.chute_stats || []).map(c => ({ name: c.chute, value: c.count })),
    label: { formatter: '{b}\n{d}%' },
    itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
    color: ['#667eea','#764ba2','#f093fb','#f5576c','#4facfe','#00f2fe'],
    emphasis: { scaleSize: 12 },
  }],
}))

const gaugeOption = computed(() => ({
  series: [{
    type: 'gauge', min: 0, max: 100,
    startAngle: 200, endAngle: -20,
    center: ['50%', '55%'],
    detail: { formatter: '{value}%', fontSize: 32, fontWeight: 'bold', offsetCenter: [0, '60%'] },
    data: [{ value: parseFloat(successRate.value), name: '分拣成功率' }],
    axisLine: { lineStyle: { color: [[0.3,'#F56C6C'],[0.7,'#E6A23C'],[1,'#67C23A']], width: 20 } },
    pointer: { length: '70%', width: 8 },
    title: { offsetCenter: [0, '85%'], fontSize: 13 },
  }],
}))

const peakOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 50, right: 20, top: 10, bottom: 20 },
  xAxis: { type: 'category', data: Array.from({length:24},(_,i)=>i+':00'), axisLabel: { rotate: 0, fontSize: 10 } },
  yAxis: { type: 'value' },
  series: [{
    type: 'bar', name: '分拣量',
    data: Array.from({length:24},(_,h)=>{ const pv=stats.value.peak_valley||[]; const f=pv.find(p=>p.hour===h); return f?f.count:0 }),
    itemStyle: { borderRadius: [6,6,0,0], color: { type:'linear',x:0,y:0,x2:0,y2:1,
      colorStops: [{offset:0,color:'#43e97b'},{offset:1,color:'#38f9d7'}] } },
    barWidth: '70%',
    markLine: { silent: true, data: [{ type: 'average', name: '平均值', label: { fontSize: 10 } }], lineStyle: { color: '#F56C6C', type: 'dashed' } },
  }],
}))

const reportDialog = ref(false)
const reportData = ref({})

function statusTagType(status) {
  const map = {
    pending: 'info', dispatched: 'warning', accepted: '', processing: '',
    completed: 'success', verified: 'success',
    rejected: 'danger', stale: 'danger', failed: 'danger',
  }
  return map[status] || 'info'
}

async function downloadReport(period) {
  try { const res = await request.get('/api/stats/report', { params: { period } }); reportData.value = res.data || {}; reportDialog.value = true } catch { /* report unavailable */ }
}
function exportReport() {
  request.get('/api/export/excel', { responseType: 'blob' }).then(res => {
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a'); a.href = url; a.download = '分拣记录.xlsx'; a.click()
  }).catch(() => {})
}

async function fetchData() {
  try { const [sum, rec] = await Promise.all([getStatsSummary(), getRecentDecisions()]); stats.value = sum.data; recentDecisions.value = rec.data } catch { /* ignore */ }
}

async function fetchOperatorStats() {
  opStatsLoading.value = true
  try {
    const res = await request.get('/api/operators/stats')
    operatorStats.value = res.data || []
  } catch { /* ignore */ }
  opStatsLoading.value = false
}

async function fetchTaskSummary() {
  try {
    const res = await request.get('/api/tasks/status-summary')
    if (res?.data?.status_counts) taskSummary.value = res.data.status_counts
  } catch { /* ignore */ }
}

onMounted(() => {
  fetchData()
  fetchOperatorStats()
  fetchTaskSummary()
  wsHandle = createDashboardSocket({
    onMessage: (data) => {
      if (data.event === 'sorting_result') {
        recentDecisions.value.unshift(data.data)
        if (recentDecisions.value.length > 20) recentDecisions.value.pop()
        stats.value.total_decisions++
        const s = data.data.status
        if (['completed', 'verified'].includes(s)) stats.value.success_count++
        else if (['failed', 'rejected', 'stale'].includes(s)) stats.value.fail_count++
      }
      if (data.event === 'alert_triggered') {
        const a = data.data
        ElMessage.warning({ message: `🚨 ${a.rule}: ${a.message}`, duration: 5000 })
        if (Notification.permission === 'granted') {
          new Notification(`🚨 ${a.rule}`, { body: a.message })
        }
      }
      // P0: 操作员已处理（兼容旧事件）
      if (data.event === 'task_handled') {
        ElMessage.success({ message: `✅ ${data.data.handler} 处理了包裹 ${data.data.tracking_number} → ${data.data.target_chute}`, duration: 3000 })
        fetchOperatorStats()
      }
      // P0: 操作员上报异常
      if (data.event === 'exception_raised') {
        const e = data.data
        ElMessage.error({ message: `⚠️ ${e.reported_by} 上报异常: ${e.tracking_number} ${e.exception_type}${e.note ? ' - ' + e.note : ''}`, duration: 6000 })
        if (Notification.permission === 'granted') {
          new Notification(`⚠️ 分拣异常`, { body: `${e.tracking_number}: ${e.exception_type}` })
        }
      }
      // 9态事件 → 刷新任务状态
      if (['task_dispatched', 'task_accepted', 'task_rejected', 'task_processing', 'task_completed', 'task_verified', 'task_stale'].includes(data.event)) {
        fetchTaskSummary()
      }
      // 发车事件 → 通知管理员
      if (data.event === 'vehicle_departed') {
        const v = data.data
        ElMessage.success({ message: `🚛 车辆 ${v.vehicle_id} 已发车！${v.operator} 完成 ${v.packages} 件包裹分拣并发车`, duration: 6000 })
        if (Notification.permission === 'granted') {
          new Notification(`🚛 发车通知`, { body: `${v.vehicle_id}: ${v.packages}件包裹已发车` })
        }
        fetchTaskSummary()
      }
    },
  })
  if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission()
})

onUnmounted(() => { wsHandle?.disconnect() })
</script>

<style scoped>
.dashboard { padding: 24px; background: #f0f2f5; min-height: 100vh; }
.dash-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.dash-header h2 { color: #1a1a2e; font-size: 24px; margin: 0; }
.live-badge { display: flex; align-items: center; gap: 8px; background: rgba(103,194,58,.15); color: #67C23A; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: 600; }
.pulse { width: 8px; height: 8px; background: #67C23A; border-radius: 50%; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(1.3)} }

/* 实时任务状态行 */
.task-status-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 16px; }
.ts-card { background: #fff; border-radius: 12px; padding: 14px 12px; text-align: center; border: 1px solid #e8e8e8; transition: all 0.2s; }
.ts-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,.06); }
.ts-num { font-size: 22px; font-weight: 800; color: #303133; }
.ts-lab { font-size: 11px; color: #909399; margin-top: 2px; }
.ts-blue { border-top: 3px solid #409EFF; }
.ts-cyan { border-top: 3px solid #00B4D8; }
.ts-purple { border-top: 3px solid #8B5CF6; }
.ts-green { border-top: 3px solid #67C23A; }
.ts-orange { border-top: 3px solid #F59E0B; }
.ts-red { border-top: 3px solid #EF4444; }
.ts-gray { border-top: 3px solid #909399; }
.pulse-red-bg { animation: pulse-red-bg 2s infinite; border-color: #EF4444 !important; }
@keyframes pulse-red-bg { 0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.2)} 50%{box-shadow:0 0 0 8px rgba(239,68,68,0)} }

.kpi-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 12px; }
.kpi-grid-4 { grid-template-columns: repeat(4, 1fr); }

.kpi-card { border-radius: 14px; padding: 20px 16px; text-align: center; color: #fff; position: relative; overflow: hidden; transition: transform .2s; }
.kpi-card:hover { transform: translateY(-2px); }
.kpi-card::after { content: ''; position: absolute; top: -30px; right: -30px; width: 80px; height: 80px; border-radius: 50%; background: rgba(255,255,255,.1); }
.kpi-blue { background: linear-gradient(135deg,#667eea,#764ba2); }
.kpi-purple { background: linear-gradient(135deg,#f093fb,#f5576c); }
.kpi-green { background: linear-gradient(135deg,#43e97b,#38f9d7); color: #1a3a1a; }
.kpi-red { background: linear-gradient(135deg,#f5576c,#ff6b6b); }
.kpi-teal { background: linear-gradient(135deg,#4facfe,#00f2fe); color: #1a3a1a; }
.kpi-orange { background: linear-gradient(135deg,#fa8231,#f7b731); }
.kpi-mini { background: #fff; color: #303133; border: 1px solid #e8e8e8; }

.kpi-icon { font-size: 28px; margin-bottom: 4px; }
.kpi-num { font-size: 28px; font-weight: 800; letter-spacing: -.5px; }
.kpi-mini .kpi-num { font-size: 22px; color: #409EFF; }
.kpi-label { font-size: 12px; opacity: .85; margin-top: 2px; }
.kpi-mini .kpi-label { opacity: .6; }

.chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
.chart-card { border-radius: 14px; }
.card-title { font-weight: 600; font-size: 14px; color: #303133; }

/* 操作员卡片 */
.op-card { background: #fff; border-radius: 12px; border: 1px solid #e8e8e8; padding: 12px 16px; transition: all .2s; }
.op-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.08); transform: translateY(-1px); }
.op-card.op-offline { opacity: .5; background: #f5f5f5; }
.op-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.op-name { font-weight: 700; font-size: 15px; color: #303133; }
.op-body { display: flex; flex-direction: column; gap: 8px; }
.op-chutes { display: flex; flex-wrap: wrap; gap: 4px; }
.op-stats { display: flex; gap: 12px; font-size: 12px; color: #909399; }
.op-stats b { color: #409EFF; }
</style>
