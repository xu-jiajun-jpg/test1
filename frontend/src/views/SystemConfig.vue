<template>
    <div class="page">
      <h2>⚙️ 系统配置</h2>
      <el-tabs v-model="activeModule" @tab-change="fetch">
        <el-tab-pane label="通用" name="general" />
        <el-tab-pane label="OCR识别" name="ocr" />
        <el-tab-pane label="分拣决策" name="sorting" />
        <el-tab-pane label="通知" name="notification" />
      </el-tabs>
      <el-card style="margin-top:12px">
        <div style="margin-bottom:12px;display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap">
          <div style="display:flex;gap:8px;align-items:center">
            <el-tag type="info">共 {{ configs.length }} 项配置</el-tag>
            <el-tag v-for="(cnt, cat) in catCounts" :key="cat" :type="cat==='general'?'':cat==='ocr'?'success':cat==='sorting'?'warning':'info'" size="small">{{ catLabel(cat) }} {{ cnt }}</el-tag>
          </div>
          <el-button type="primary" size="small" @click="openCreateDialog">新增配置</el-button>
        </div>
        <el-table :data="configs" stripe>
        <el-table-column prop="config_key" label="配置项" width="200" />
        <el-table-column prop="config_value" label="当前值" min-width="300" />
        <el-table-column prop="value_type" label="类型" width="80" />
        <el-table-column prop="description" label="说明" min-width="200" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="editConfig(row)">修改</el-button>
            <el-button type="danger" size="small" @click="deleteConfig(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      </el-card>

      <el-dialog title="修改配置" v-model="dialogVisible" width="450px">
        <el-form :model="editForm" label-width="80px">
          <el-form-item label="配置项"><el-input :value="editForm.config_key" disabled /></el-form-item>
          <el-form-item label="当前值"><el-input v-model="editForm.config_value" /></el-form-item>
        </el-form>
        <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="saveConfig">保存</el-button></template>
      </el-dialog>

      <el-dialog title="新增配置" v-model="createDialog" width="450px">
        <el-form :model="createForm" label-width="80px">
          <el-form-item label="配置项"><el-input v-model="createForm.config_key" placeholder="如: max_upload_size" /></el-form-item>
          <el-form-item label="值"><el-input v-model="createForm.config_value" /></el-form-item>
          <el-form-item label="类型"><el-select v-model="createForm.value_type" style="width:100%"><el-option label="字符串" value="string" /><el-option label="数字" value="number" /><el-option label="布尔" value="boolean" /></el-select></el-form-item>
          <el-form-item label="模块"><el-select v-model="createForm.module" style="width:100%"><el-option label="通用" value="general" /><el-option label="OCR识别" value="ocr" /><el-option label="分拣决策" value="sorting" /><el-option label="通知" value="notification" /></el-select></el-form-item>
          <el-form-item label="说明"><el-input v-model="createForm.description" /></el-form-item>
        </el-form>
        <template #footer><el-button @click="createDialog=false">取消</el-button><el-button type="primary" @click="createConfig">创建</el-button></template>
      </el-dialog>
    </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const activeModule = ref('general')
const configs = ref([])
const dialogVisible = ref(false)
const createDialog = ref(false)
const editForm = reactive({ id:null, config_key:'', config_value:'' })
const createForm = reactive({ config_key:'', config_value:'', value_type:'string', module:'general', description:'' })

const catCounts = computed(() => {
  const m = {}
  configs.value.forEach(c => { m[c.module||'general'] = (m[c.module||'general']||0) + 1 })
  return m
})
function catLabel(c) { return { general:'通用', ocr:'OCR', sorting:'分拣', notification:'通知' }[c] || c }

async function fetch() {
  try { const res = await request.get('/api/config', { params: { module: activeModule.value } }); configs.value = res.data } catch { /* ignore */ }
}
function editConfig(row) { Object.assign(editForm, row); dialogVisible.value = true }
async function saveConfig() {
  try { await request.put(`/api/config/${editForm.id}`, { config_value: editForm.config_value }); ElMessage.success('配置已更新'); dialogVisible.value = false; fetch() } catch { /* ignore */ }
}
function openCreateDialog() { Object.assign(createForm, { config_key:'', config_value:'', value_type:'string', module:activeModule.value, description:'' }); createDialog.value = true }
async function createConfig() {
  try { await request.post('/api/config', { ...createForm }); ElMessage.success('创建成功'); createDialog.value = false; fetch() } catch { /* ignore */ }
}
async function deleteConfig(row) {
  try { await request.delete(`/api/config/${row.id}`); ElMessage.success('已删除'); fetch() } catch { /* ignore */ }
}
onMounted(() => fetch())
</script>
<style scoped>.page { padding: 20px; } h2 { margin-bottom: 16px; color: #2c3e50; }</style>
