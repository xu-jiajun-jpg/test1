<template>
    <div class="page">
      <h2>👷 分拣人员管理</h2>

      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="6"><el-card shadow="hover" class="stat-card"><div class="stat-num">{{ total }}</div><div class="stat-label">👥 人员总数</div></el-card></el-col>
        <el-col :span="6"><el-card shadow="hover" class="stat-card"><div class="stat-num">{{ operators.filter(o=>o.status==='active').length }}</div><div class="stat-label">✅ 在岗</div></el-card></el-col>
        <el-col :span="6"><el-card shadow="hover" class="stat-card"><div class="stat-num">{{ operators.filter(o=>o.shift==='早班').length }}</div><div class="stat-label">🌅 早班</div></el-card></el-col>
        <el-col :span="6"><el-card shadow="hover" class="stat-card"><div class="stat-num">{{ operators.filter(o=>o.shift==='中班').length }}</div><div class="stat-label">☀️ 中班</div></el-card></el-col>
        <el-col :span="6"><el-card shadow="hover" class="stat-card"><div class="stat-num">{{ operators.filter(o=>o.shift==='晚班').length }}</div><div class="stat-label">🌙 晚班</div></el-card></el-col>
      </el-row>

      <el-card style="margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
          <div style="display:flex;gap:12px;align-items:center">
            <el-input v-model="searchKey" placeholder="搜索姓名/工号" clearable style="width:220px" @input="onSearch" />
            <el-select v-model="shiftFilter" placeholder="排班筛选" clearable style="width:120px" @change="onSearch">
              <el-option label="早班" value="早班" /><el-option label="中班" value="中班" /><el-option label="晚班" value="晚班" />
            </el-select>
          </div>
          <el-button type="primary" @click="openDialog()">新增人员</el-button>
        </div>
      </el-card>
      <el-table :data="operators" stripe>
        <el-table-column prop="employee_id" label="工号" width="100" />
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="phone" label="电话" width="130" />
        <el-table-column prop="shift" label="排班" width="100">
          <template #default="{ row }"><el-tag size="small">{{ shiftLabel(row.shift) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }"><el-tag :type="row.status==='active'?'success':'info'" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="分拣口" width="180">
          <template #default="{ row }">
            <div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center">
              <el-tag v-for="ch in (row.chutes||[])" :key="ch" size="small" closable @close="unbindChute(row,ch)">{{ ch }}</el-tag>
              <el-button size="small" circle @click="openChuteDialog(row)">+</el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="prev,pager,next" style="margin-top:12px;justify-content:center" @current-change="fetch" />

      <el-dialog :title="isEdit?'编辑人员':'新增人员'" v-model="dialogVisible" width="450px">
        <el-form :model="form" label-width="80px">
          <el-form-item label="工号"><el-input v-model="form.employee_id" :disabled="isEdit" /></el-form-item>
          <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="电话"><el-input v-model="form.phone" /></el-form-item>
          <el-form-item label="排班"><el-select v-model="form.shift"><el-option label="早班" value="早班" /><el-option label="中班" value="中班" /><el-option label="晚班" value="晚班" /></el-select></el-form-item>
          <el-form-item label="状态"><el-switch v-model="form.status" active-value="active" inactive-value="inactive" /></el-form-item>
        </el-form>
        <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
      </el-dialog>

      <!-- 分拣口绑定弹窗 -->
      <el-dialog title="绑定分拣口" v-model="chuteDialog" width="350px">
        <el-select v-model="bindChute" placeholder="选择分拣口" style="width:100%">
          <el-option v-for="c in allChutes" :key="c.chute_code" :label="c.chute_code+' '+c.name" :value="c.chute_code" />
        </el-select>
        <template #footer>
          <el-button @click="chuteDialog=false">取消</el-button>
          <el-button type="primary" @click="doBind">绑定</el-button>
        </template>
      </el-dialog>
    </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const operators = ref([])
const allOperators = ref([])
const page = ref(1)
const total = ref(0)
const searchKey = ref('')
const shiftFilter = ref('')
const dialogVisible = ref(false)
const isEdit = ref(false)
const form = reactive({ employee_id:'', name:'', phone:'', shift:'morning', status:'active', id:null })
function shiftLabel(s) {
  return { morning:'早班', afternoon:'中班', night:'晚班', '早班':'早班', '中班':'中班', '晚班':'晚班' }[s] || s
}
function onSearch() {
  let list = [...allOperators.value]
  if (searchKey.value) {
    const kw = searchKey.value.toLowerCase()
    list = list.filter(o => o.name?.toLowerCase().includes(kw) || o.employee_id?.toLowerCase().includes(kw))
  }
  if (shiftFilter.value) list = list.filter(o => o.shift === shiftFilter.value)
  operators.value = list; total.value = list.length; page.value = 1
}

async function fetch(p = 1) {
  page.value = p
  try { const res = await request.get('/api/operators', { params: { page: p, page_size: 100 } }); allOperators.value = res.data.items || []; operators.value = [...allOperators.value]; total.value = res.data.total || allOperators.value.length } catch { /* ignore */ }
}
function openDialog(row) {
  if (row) { isEdit.value = true; Object.assign(form, row) }
  else { isEdit.value = false; Object.assign(form, { employee_id:'', name:'', phone:'', shift:'morning', status:'active', id:null }) }
  dialogVisible.value = true
}
async function save() {
  try {
    const data = { name:form.name, phone:form.phone, shift:form.shift, status:form.status }
    if (isEdit.value) { data.employee_id = form.employee_id; await request.put(`/api/operators/${form.id}`, data) }
    else await request.post('/api/operators', { ...data, employee_id: form.employee_id })
    ElMessage.success('保存成功'); dialogVisible.value = false; fetch(page.value)
  } catch { /* ignore */ }
}
async function del(row) {
  try { await request.delete(`/api/operators/${row.id}`); ElMessage.success('删除成功'); fetch(page.value) } catch { /* ignore */ }
}

// ===== 分拣口绑定 =====
const chuteDialog = ref(false)
const bindChute = ref('')
const currentOp = ref(null)
const allChutes = ref([])

async function loadChutes() {
  try { const r = await request.get('/api/chutes'); allChutes.value = r.data } catch { /* chute list unavailable */ }
}

function openChuteDialog(row) {
  currentOp.value = row; bindChute.value = ''
  loadChutes(); chuteDialog.value = true
}

async function doBind() {
  if (!bindChute.value || !currentOp.value) return
  try {
    await request.post(`/api/operators/${currentOp.value.id}/chutes`, { chute_code: bindChute.value })
    ElMessage.success('绑定成功'); chuteDialog.value = false; fetch(page.value)
  } catch { ElMessage.error('绑定失败') }
}

async function unbindChute(row, chuteCode) {
  try {
    await request.delete(`/api/operators/${row.id}/chutes/${chuteCode}`)
    ElMessage.success('已解绑'); fetch(page.value)
  } catch { /* ignore */ }
}

onMounted(() => { fetch(); loadChutes() })
</script>
<style scoped>
.page { padding: 20px; }
h2 { margin-bottom: 16px; color: #2c3e50; }
.stat-card { text-align: center; }
.stat-card .stat-num { font-size: 28px; font-weight: bold; color: #303133; }
.stat-card .stat-label { font-size: 12px; color: #909399; margin-top: 6px; }
</style>
