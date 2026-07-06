<template>
    <div class="page">
      <h2>🚨 告警管理</h2>

      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="4"><el-card shadow="hover" class="stat-card"><div class="stat-num">{{ rules.length }}</div><div class="stat-label">📋 规则总数</div></el-card></el-col>
        <el-col :span="4"><el-card shadow="hover" class="stat-card"><div class="stat-num">{{ rules.filter(r=>r.is_active).length }}</div><div class="stat-label">✅ 启用中</div></el-card></el-col>
        <el-col :span="4"><el-card shadow="hover" class="stat-card" style="border-left:4px solid #F56C6C"><div class="stat-num">{{ alerts.filter(a=>a.alert_level==='critical').length }}</div><div class="stat-label">🔴 严重告警</div></el-card></el-col>
        <el-col :span="4"><el-card shadow="hover" class="stat-card" style="border-left:4px solid #E6A23C"><div class="stat-num">{{ alerts.filter(a=>a.alert_level==='warning').length }}</div><div class="stat-label">🟡 警告</div></el-card></el-col>
        <el-col :span="4"><el-card shadow="hover" class="stat-card" style="border-left:4px solid #909399"><div class="stat-num">{{ alerts.filter(a=>a.alert_level==='info').length }}</div><div class="stat-label">🔵 信息</div></el-card></el-col>
        <el-col :span="4"><el-card shadow="hover" class="stat-card"><div class="stat-num">{{ alertTotal }}</div><div class="stat-label">📊 历史总计</div></el-card></el-col>
      </el-row>
      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="12">
          <el-card header="告警规则">
            <el-button type="primary" size="small" @click="openRuleDialog()" style="margin-bottom:12px">新增规则</el-button>
            <el-table :data="rules" size="small"><el-table-column prop="rule_name" label="名称" /><el-table-column prop="metric" label="指标" width="120" /><el-table-column prop="threshold" label="阈值" width="80" /><el-table-column label="启用" width="60"><template #default="{ row }"><el-switch v-model="row.is_active" size="small" @change="toggleRule(row)" /></template></el-table-column><el-table-column label="操作" width="70"><template #default="{ row }"><el-button type="danger" size="small" @click="deleteRule(row)">删除</el-button></template></el-table-column></el-table>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card header="告警历史">
            <div style="margin-bottom:8px;display:flex;gap:8px">
              <el-button type="warning" size="small" @click="checkAlerts" :loading="checking">🔍 检测告警</el-button>
            </div>
            <el-table :data="alerts" size="small"><el-table-column prop="message" label="内容" min-width="200" show-overflow-tooltip /><el-table-column prop="alert_level" label="等级" width="80"><template #default="{ row }"><el-tag :type="levelColor(row.alert_level)" size="small">{{ row.alert_level }}</el-tag></template></el-table-column><el-table-column label="时间" width="100"><template #default="{ row }">{{ row.created_at?.slice(11,19) }}</template></el-table-column></el-table>
            <el-pagination small v-model:current-page="alertPage" :total="alertTotal" :page-size="10" layout="prev,next" @current-change="fetchAlerts" />
          </el-card>
        </el-col>
      </el-row>

      <el-dialog title="新增告警规则" v-model="ruleDialog" width="450px">
        <el-form :model="ruleForm" label-width="80px">
          <el-form-item label="名称"><el-input v-model="ruleForm.rule_name" /></el-form-item>
          <el-form-item label="指标"><el-input v-model="ruleForm.metric" /></el-form-item>
          <el-form-item label="阈值"><el-input-number v-model="ruleForm.threshold" /></el-form-item>
          <el-form-item label="等级"><el-select v-model="ruleForm.alert_level"><el-option label="信息" value="info" /><el-option label="警告" value="warning" /><el-option label="严重" value="critical" /></el-select></el-form-item>
        </el-form>
        <template #footer><el-button @click="ruleDialog=false">取消</el-button><el-button type="primary" @click="saveRule">保存</el-button></template>
      </el-dialog>
    </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const rules = ref([])
const alerts = ref([])
const alertPage = ref(1)
const alertTotal = ref(0)
const ruleDialog = ref(false)
const ruleForm = reactive({ rule_name:'', metric:'', threshold:0, alert_level:'warning', is_active:true })
function levelColor(l) { return l==='critical'?'danger':l==='warning'?'warning':'info' }

async function fetchRules() { try { const r = await request.get('/api/alerts/rules'); rules.value = r.data } catch { /* ignore */ } }
async function fetchAlerts(p = 1) { alertPage.value = p; try { const r = await request.get('/api/alerts/history', { params: { page: p, page_size: 10 } }); alerts.value = r.data.items; alertTotal.value = r.data.total } catch { /* ignore */ } }
async function toggleRule(row) { try { await request.put(`/api/alerts/rules/${row.id}`, { is_active: row.is_active }) } catch { /* ignore */ } }
function openRuleDialog() { Object.assign(ruleForm, { rule_name:'', metric:'', threshold:0, alert_level:'warning' }); ruleDialog.value = true }
async function saveRule() { try { await request.post('/api/alerts/rules', { ...ruleForm }); ElMessage.success('创建成功'); ruleDialog.value = false; fetchRules() } catch { /* ignore */ } }
async function deleteRule(row) { try { await request.delete(`/api/alerts/rules/${row.id}`); ElMessage.success('已删除'); fetchRules() } catch { /* ignore */ } }
const checking = ref(false)
async function checkAlerts() {
  checking.value = true
  try {
    const r = await request.post('/api/alerts/check')
    const t = r.data.triggered?.length || 0
    ElMessage.success(t > 0 ? `触发 ${t} 条告警` : '当前无告警')
    fetchAlerts()
  } catch { /* ignore */ }
  checking.value = false
}
onMounted(() => { fetchRules(); fetchAlerts() })
</script>
<style scoped>
.page { padding: 20px; }
h2 { margin-bottom: 16px; color: #2c3e50; }
.stat-card { text-align: center; }
.stat-card .stat-num { font-size: 28px; font-weight: bold; color: #303133; }
.stat-card .stat-label { font-size: 12px; color: #909399; margin-top: 6px; }
</style>
