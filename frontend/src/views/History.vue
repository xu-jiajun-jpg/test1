<template>
    <div class="page">
      <h2>📜 历史查询与统计 (模块8)</h2>
      <el-card style="margin-bottom:16px">
        <el-form :inline="true">
          <el-form-item label="日期范围"><el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" /></el-form-item>
          <el-form-item><el-button type="primary" @click="fetch">查询</el-button></el-form-item>
          <el-form-item><el-button @click="exportExcel">导出Excel</el-button></el-form-item>
          <el-form-item><el-button @click="exportPDF">导出PDF</el-button></el-form-item>
        </el-form>
      </el-card>

      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="6"><el-card><el-statistic title="总处理量" :value="stats.total_decisions" /></el-card></el-col>
        <el-col :span="6"><el-card><el-statistic title="成功率" :value="successRate" suffix="%" /></el-card></el-col>
        <el-col :span="6"><el-card><el-statistic title="异常占比" :value="failRate" suffix="%" /></el-card></el-col>
        <el-col :span="6"><el-card><el-statistic title="平均耗时" :value="avgTime" suffix="ms" /></el-card></el-col>
      </el-row>

      <el-card header="分拣记录明细">
        <el-table :data="records" stripe>
          <el-table-column prop="tracking_number" label="运单号" width="150" />
          <el-table-column prop="province" label="分区" width="80" />
          <el-table-column prop="city" label="城市" width="100" />
          <el-table-column prop="target_chute" label="分拣口" width="100" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }"><el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag></template>
          </el-table-column>
          <el-table-column label="决策时间" width="180">
            <template #default="{ row }">{{ row.decision_time?.slice(0,19) }}</template>
          </el-table-column>
        </el-table>
        <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="prev,pager,next" style="margin-top:12px;justify-content:center" @current-change="fetch" />
      </el-card>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import request from '@/api/request'
const baseUrl = 'http://127.0.0.1:8003'
const records = ref([])
const page = ref(1)
const total = ref(0)
const dateRange = ref([])
const stats = ref({ total_decisions: 0, success_count: 0, fail_count: 0, avg_processing_ms: 0 })
const successRate = computed(() => stats.value.total_decisions ? (stats.value.success_count/stats.value.total_decisions*100).toFixed(1) : 0)
const failRate = computed(() => stats.value.total_decisions ? (stats.value.fail_count/stats.value.total_decisions*100).toFixed(1) : 0)
const avgTime = computed(() => stats.value.avg_processing_ms || '-')
function statusTagType(s) {
  const map = { pending:'info', dispatched:'warning', accepted:'', processing:'', completed:'success', verified:'success', rejected:'danger', stale:'danger', failed:'danger' }
  return map[s] || 'info'
}

async function fetch(p = 1) {
  page.value = p
  try {
    const [hist, sum] = await Promise.all([
      request.get('/api/stats/history', { params: { page: p } }),
      request.get('/api/stats/summary')
    ])
    records.value = hist.data.items
    total.value = hist.data.total
    stats.value = sum.data
  } catch { /* ignore */ }
}
function exportExcel() { window.open(`${baseUrl}/api/export/excel`) }
function exportPDF() { window.open(`${baseUrl}/api/export/pdf`) }
onMounted(() => fetch())
</script>
<style scoped>.page { padding: 20px; } h2 { margin-bottom: 16px; }</style>
