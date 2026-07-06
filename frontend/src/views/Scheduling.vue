<template>
    <div class="page">
      <h2>📅 智能排班与任务调度 (模块9)</h2>
      <el-card style="margin-bottom:16px">
        <el-form :inline="true">
          <el-form-item label="日期"><el-date-picker v-model="sDate" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="操作员数"><el-input-number v-model="opsCount" :min="5" :max="50" /></el-form-item>
          <el-form-item><el-button type="primary" :loading="loading" @click="predict">AI预测排班</el-button></el-form-item>
        </el-form>
      </el-card>

      <template v-if="result">
        <el-row :gutter="16" style="margin-bottom:16px">
          <el-col :span="6"><el-card><el-statistic title="预测总量" :value="result.prediction?.total_predicted" suffix="件" /></el-card></el-col>
          <el-col :span="6"><el-card><el-statistic title="人力利用率" :value="result.schedule?.utilization_percent" suffix="%" /></el-card></el-col>
          <el-col :span="6"><el-card><el-statistic title="运行小时" :value="result.equipment?.total_runtime_hours" suffix="h" /></el-card></el-col>
          <el-col :span="6"><el-card><el-statistic title="节能比例" :value="result.equipment?.estimated_energy_saving" /></el-card></el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="16">
            <el-card header="排班明细">
              <el-table :data="result.schedule?.shifts" size="small" max-height="400">
                <el-table-column prop="hour" label="时段" width="100"><template #default="{row}">{{ row.hour }}:00</template></el-table-column>
                <el-table-column prop="volume_predicted" label="预测量" width="100" />
                <el-table-column prop="operators_needed" label="需人员" width="80" />
                <el-table-column prop="ratio" label="配置" width="80"><template #default="{row}">{{ row.ratio }}%</template></el-table-column>
                <el-table-column prop="type" label="类型" width="80"><template #default="{row}"><el-tag :type="row.type==='peak'?'danger':row.type==='normal'?'success':'info'" size="small">{{ {peak:'高峰',normal:'正常',low:'低谷'}[row.type] }}</el-tag></template></el-table-column>
              </el-table>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card header="设备启停策略">
              <div v-for="s in result.equipment?.strategy?.filter(x=>x.equipment_status!=='off')?.slice(0,12)" :key="s.hour" style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #eee">
                <span>{{ s.hour }}:00</span>
                <el-tag :type="s.equipment_status==='full'?'success':s.equipment_status==='eco'?'warning':'info'" size="small">{{ {full:'全速',eco:'经济',standby:'待机'}[s.equipment_status] }}</el-tag>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </template>
    </div>
</template>

<script setup>
import { ref } from 'vue'
import request from '@/api/request'

const sDate = ref(new Date().toISOString().slice(0, 10))
const opsCount = ref(10)
const loading = ref(false)
const result = ref(null)

async function predict() {
  loading.value = true
  try { const res = await request.get('/api/scheduling/predict', { params: { date: sDate.value, operators: opsCount.value } }); result.value = res.data } catch { /* data unavailable */ }
  loading.value = false
}

predict()
</script>
<style scoped>.page { padding: 20px; } h2 { margin-bottom: 16px; }</style>
