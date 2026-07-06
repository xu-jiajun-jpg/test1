<template>
    <div class="page">
      <h2>📦 分拣口管理 (模块4)</h2>
      <el-button type="primary" @click="openDialog()" style="margin-bottom:16px">新增分拣口</el-button>
      <el-table :data="chutes" stripe row-key="chute_code" @expand-change="onExpand">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div v-loading="row._loading" style="padding:8px 20px">
              <p v-if="row._packages?.length" style="margin-bottom:8px;color:#666">
                📦 <b>{{ row._total }}</b> 个包裹在此分拣口
              </p>
              <p v-else-if="!row._loading" style="color:#999">暂无包裹</p>
              <el-table v-if="row._packages?.length" :data="row._packages" size="small" border>
                <el-table-column prop="tracking_number" label="运单号" width="150" />
                <el-table-column :label="row.chute_code==='CH-006'?'处理人':'分区'" width="100">
                  <template #default="{ row: p }">{{ p.district }}</template>
                </el-table-column>
                <el-table-column :label="row.chute_code==='CH-006'?'备注':'城市'" width="120">
                  <template #default="{ row: p }">{{ p.city || '-' }}</template>
                </el-table-column>
                <el-table-column label="状态" width="90">
                  <template #default="{ row: p }">
                    <el-tag v-if="row.chute_code==='CH-006'" type="danger" size="small">异常件</el-tag>
                    <el-tag v-else :type="statusTagType(p.status)" size="small">{{ p.status }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column v-if="row.chute_code==='CH-006'" label="操作" width="80">
                  <template #default="{ row: p }">
                    <el-button type="primary" size="small" @click="openReview(p)">🔍 复核</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="chute_code" label="编码" width="100" />
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="location" label="位置" width="100" />
        <el-table-column label="包裹数" width="90">
          <template #default="{ row }">
            <el-tag v-if="row._total != null" :type="row._total>0?'primary':'info'" size="small">{{ row._total }}</el-tag>
            <span v-else style="color:#ccc">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="capacity" label="容量(件/时)" width="120" />
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }"><el-tag :type="row.is_active?'success':'info'" size="small">{{ row.is_active?'启用':'停用' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 人工复核弹窗 -->
      <el-dialog title="🔍 人工复核 - 异常包裹处理" v-model="reviewDialog" width="700px" @close="reviewPkg=null">
        <template v-if="reviewPkg">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-image :src="reviewPkg.image_url" style="width:100%;border-radius:8px" fit="contain" :preview-src-list="[reviewPkg.image_url]" preview-teleported :z-index="3000">
                <template #error><div style="height:200px;display:flex;align-items:center;justify-content:center;background:#f5f5f5;border-radius:8px">📦 无法加载</div></template>
              </el-image>
              <p style="margin-top:8px;font-size:12px;color:#999">运单号: {{ reviewPkg.tracking_number }}</p>
            </el-col>
            <el-col :span="12">
              <el-alert v-if="reviewPkg.ocr_text" title="OCR识别原文" :description="reviewPkg.ocr_text" type="info" :closable="false" show-icon style="margin-bottom:12px;max-height:150px;overflow:auto" />
              <el-form :model="reviewForm" label-width="70px" size="small">
                <el-form-item label="分区"><el-input v-model="reviewForm.district" placeholder="如：东湖区" /></el-form-item>
                <el-form-item label="城市"><el-input v-model="reviewForm.city" placeholder="如：广州市" /></el-form-item>
                <el-form-item label="收件人"><el-input v-model="reviewForm.receiver_name" placeholder="收件人姓名" /></el-form-item>
                <el-form-item label="电话"><el-input v-model="reviewForm.phone" placeholder="手机号" /></el-form-item>
              </el-form>
            </el-col>
          </el-row>
        </template>
        <template #footer>
          <el-button @click="discardPkg" type="danger" :loading="reviewLoading">🗑️ 丢弃包裹</el-button>
          <el-button @click="reviewDialog=false">取消</el-button>
          <el-button type="primary" @click="submitReview" :loading="reviewLoading">📤 人工分拣</el-button>
        </template>
      </el-dialog>

      <el-dialog :title="isEdit?'编辑分拣口':'新增分拣口'" v-model="dialogVisible" width="500px">
        <el-form :model="form" label-width="100px">
          <el-form-item label="编码"><el-input v-model="form.chute_code" :disabled="isEdit" /></el-form-item>
          <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="位置"><el-input v-model="form.location" /></el-form-item>
          <el-form-item label="容量"><el-input-number v-model="form.capacity" :min="1" /></el-form-item>
          <el-form-item label="启用"><el-switch v-model="form.is_active" /></el-form-item>
        </el-form>
        <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
      </el-dialog>
    </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/api/request'
import { ElMessage, ElMessageBox } from 'element-plus'

const chutes = ref([])
const expandedRows = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const form = reactive({ chute_code:'', name:'', location:'', capacity:1000, is_active:true, id:null })

function statusTagType(s) {
  const map = { pending:'info', dispatched:'warning', accepted:'', processing:'', completed:'success', verified:'success', rejected:'danger', stale:'danger', failed:'danger' }
  return map[s] || 'info'
}

async function fetch() {
  try { const res = await request.get('/api/chutes'); chutes.value = res.data } catch { /* ignore */ }
  // 预加载所有分拣口的包裹数量
  for (const ch of chutes.value) {
    try {
      const r = await request.get(`/api/chutes/${ch.chute_code}/packages?page=1&page_size=1`)
      ch._total = r.data?.total ?? 0
    } catch { ch._total = 0 }
  }
}

async function onExpand(row, expanded) {
  expandedRows.value = expanded
  if (!expanded.includes(row)) return
  if (row._packages) return
  row._loading = true
  try {
    const res = await request.get(`/api/chutes/${row.chute_code}/packages?page=1&page_size=50`)
    row._packages = res.data.items
    row._total = res.data.total
  } catch { row._packages = [] }
  row._loading = false
}

function openDialog(row) {
  if (row) { isEdit.value = true; Object.assign(form, row) }
  else { isEdit.value = false; Object.assign(form, { chute_code:'', name:'', location:'', capacity:1000, is_active:true, id:null }) }
  dialogVisible.value = true
}
async function save() {
  try {
    if (isEdit.value) await request.put(`/api/chutes/${form.id}`, { name:form.name, location:form.location, capacity:form.capacity, is_active:form.is_active })
    else await request.post('/api/chutes', { chute_code:form.chute_code, name:form.name, location:form.location, capacity:form.capacity })
    ElMessage.success('保存成功'); dialogVisible.value = false; fetch()
  } catch { /* ignore */ }
}
const reviewDialog = ref(false)
const reviewPkg = ref(null)
const reviewLoading = ref(false)
const reviewForm = reactive({ district:'', city:'', receiver_name:'', phone:'' })

async function openReview(pkg) {
  reviewLoading.value = true
  try {
    const res = await request.get(`/api/chutes/packages/detail/${pkg.tracking_number}`)
    const data = res.data
    reviewPkg.value = {
      ...pkg,
      image_url: `http://127.0.0.1:8003${data.image_url}`,
      ocr_text: data.ocr_text || '',
      ocr_province: data.ocr_province || '',
      ocr_city: data.ocr_city || '',
      file_id: data.file_id,
    }
    Object.assign(reviewForm, { district:data.ocr_district||'', city:data.ocr_city||'', receiver_name:'', phone:'' })
    reviewDialog.value = true
  } catch { ElMessage.error('获取包裹详情失败') }
  reviewLoading.value = false
}

async function submitReview() {
  if (!reviewForm.district) { ElMessage.warning('请填写分区'); return }
  reviewLoading.value = true
  try {
    const res = await request.post(`/api/chutes/packages/${reviewPkg.value.tracking_number}/manual-sort`, { ...reviewForm })
    ElMessage.success(res.data.message || '人工分拣完成')
    reviewDialog.value = false
    refreshChute('CH-006')
  } catch { /* ignore */ }
  reviewLoading.value = false
}

async function discardPkg() {
  await ElMessageBox.confirm('确定丢弃此包裹？将从系统中移除。', '确认丢弃', { type:'warning' })
  reviewLoading.value = true
  try {
    await request.post(`/api/chutes/packages/${reviewPkg.value.tracking_number}/discard`)
    ElMessage.success('包裹已丢弃')
    reviewDialog.value = false
    refreshChute('CH-006')
  } catch { /* ignore */ }
  reviewLoading.value = false
}

function refreshChute(chuteCode) {
  const chute = chutes.value.find(c => c.chute_code === chuteCode)
  if (chute) {
    chute._packages = null; chute._total = null; chute._loaded = false
    onExpand(chute, [chute])
  }
}

async function del(row) {
  await ElMessageBox.confirm('确定删除？', '确认', { type:'warning' })
  try { await request.delete(`/api/chutes/${row.id}`); ElMessage.success('删除成功'); fetch() } catch { /* ignore */ }
}
onMounted(() => fetch())
</script>
<style scoped>.page { padding: 20px; } h2 { margin-bottom: 16px; }</style>
