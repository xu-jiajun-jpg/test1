<template>
  <div class="ch006-page">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:12px">
      <div>
        <h2 style="margin:0 0 4px 0;color:#2c3e50">🔬 CH-006 异常包裹处理</h2>
        <p style="margin:0;color:#909399;font-size:13px">协助管理员处理异常暂存口包裹 — 1人1口专属通道</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <el-tag type="danger" size="large">CH-006 异常暂存口</el-tag>
        <el-badge :value="stats.pending" :hidden="stats.pending===0" :max="99">
          <el-button type="warning" size="small" @click="fetch()">🔄 刷新</el-button>
        </el-badge>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="exc-stats">
      <div class="exc-stat total"><div class="exc-num">{{ stats.total }}</div><div class="exc-lab">📦 异常总数</div></div>
      <div class="exc-stat damage"><div class="exc-num">{{ stats.damage }}</div><div class="exc-lab">💔 破损</div></div>
      <div class="exc-stat deformed"><div class="exc-num">{{ stats.deformed }}</div><div class="exc-lab">📐 变形</div></div>
      <div class="exc-stat leak"><div class="exc-num">{{ stats.leak }}</div><div class="exc-lab">💧 渗漏</div></div>
      <div class="exc-stat stain"><div class="exc-num">{{ stats.stain }}</div><div class="exc-lab">🟤 污渍</div></div>
      <div class="exc-stat pending">
        <div class="exc-num"><span class="blink" v-if="stats.pending>0"></span>{{ stats.pending }}</div>
        <div class="exc-lab">⏳ 待处理</div>
      </div>
    </div>

    <!-- 异常工单列表 -->
    <el-card shadow="never">
      <template #header>
        <span style="font-weight:bold">异常工单列表</span>
      </template>
      <el-table :data="records" stripe @row-click="showDetail" highlight-current-row size="small">
        <el-table-column label="预览" width="80">
          <template #default="{ row }">
            <el-image
              :src="previewSrc(row)"
              style="width:52px;height:52px;border-radius:4px"
              fit="cover"
              :preview-src-list="[previewSrc(row)]"
              preview-teleported :z-index="3000"
              @error="onImgErr"
            >
              <template #error><div class="img-placeholder">📦</div></template>
            </el-image>
          </template>
        </el-table-column>
        <el-table-column prop="file_id" label="文件ID" width="100">
          <template #default="{ row }">{{ row.file_id?.slice(0,8) }}...</template>
        </el-table-column>
        <el-table-column prop="exception_type" label="异常类型" width="140">
          <template #default="{ row }">
            <el-tag :type="typeColor(row.exception_type)" size="small" effect="dark">
              {{ typeLabel(row.exception_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status==='pending'?'danger':row.status==='processing'?'warning':'success'" size="small">
              {{ row.status==='pending'?'待处理':row.status==='processing'?'处理中':'已办结' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="检测详情" min-width="200">
          <template #default="{ row }">
            <div class="detail-preview" v-html="formatDetail(row.detail)"></div>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ row.created_at?.slice(0,19) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <template v-if="row.status==='pending'">
              <el-button type="warning" size="small" @click.stop="startProcess(row)">📋 领取</el-button>
              <el-button type="primary" size="small" @click.stop="openResolveDialog(row)">🔧 处理</el-button>
            </template>
            <template v-else-if="row.status==='processing'">
              <el-tag type="warning" size="small">处理中</el-tag>
              <el-button type="success" size="small" @click.stop="openResolveDialog(row)" style="margin-left:4px">✅ 完成</el-button>
            </template>
            <el-tag v-else type="success" size="small">已办结</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page" :total="total" :page-size="20"
        layout="prev,pager,next" style="margin-top:12px;justify-content:center"
        @current-change="fetch"
      />
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog title="异常检测详情" v-model="detailDialog" width="600px">
      <div v-if="selectedRow" class="detail-dialog">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="文件ID">{{ selectedRow.file_id }}</el-descriptions-item>
          <el-descriptions-item label="异常类型">
            <el-tag :type="typeColor(selectedRow.exception_type)" size="small">{{ typeLabel(selectedRow.exception_type) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="selectedRow.status==='pending'?'danger':'success'" size="small">{{ selectedRow.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="检测时间">{{ selectedRow.created_at?.slice(0,19) }}</el-descriptions-item>
          <el-descriptions-item label="检测详情" :span="2">
            <div v-html="formatDetail(selectedRow.detail)"></div>
          </el-descriptions-item>
          <el-descriptions-item label="建议操作" :span="2">
            <span style="color:#F56C6C;font-weight:bold">⚠️ 此为CH-006异常暂存口包裹，请确认后分流至正确分拣口</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer><el-button @click="detailDialog=false">关闭</el-button></template>
    </el-dialog>

    <!-- 处理工单弹窗 -->
    <el-dialog title="🔧 异常包裹处理" v-model="resolveDialog" width="780px" @close="resolveFormRef?.resetFields()">
      <el-steps :active="resolveStep" finish-status="success" simple style="margin-bottom:20px">
        <el-step title="领取" /><el-step title="处理" /><el-step title="办结" />
      </el-steps>
      <div v-if="resolveStep === 0">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-image v-if="resolveOcr?.resolve_img_url" :src="resolveOcr.resolve_img_url" style="width:100%;max-height:200px;border-radius:8px" fit="contain" preview-teleported :z-index="3000" />
            <div v-else class="no-img">📦 无预览图</div>
          </el-col>
          <el-col :span="12">
            <p style="color:#666;margin-bottom:8px">确认领取此异常工单？</p>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="文件ID">{{ resolveRow?.file_id?.slice(0,16) }}...</el-descriptions-item>
              <el-descriptions-item label="异常类型"><el-tag :type="typeColor(resolveRow?.exception_type)" size="small">{{ typeLabel(resolveRow?.exception_type) }}</el-tag></el-descriptions-item>
              <el-descriptions-item label="OCR分区">{{ resolveOcr?.district || '未识别' }}</el-descriptions-item>
              <el-descriptions-item label="OCR城市">{{ resolveOcr?.city || '-' }}</el-descriptions-item>
            </el-descriptions>
          </el-col>
        </el-row>
      </div>
      <div v-else>
        <el-row :gutter="16" style="margin-bottom:16px">
          <el-col :span="10">
            <el-image v-if="resolveOcr?.resolve_img_url" :src="resolveOcr.resolve_img_url" style="width:100%;max-height:180px;border-radius:8px" fit="contain" preview-teleported :z-index="3000" />
            <div v-else class="no-img">📦</div>
          </el-col>
          <el-col :span="14">
            <el-form ref="resolveFormRef" :model="resolveForm" label-width="80px">
              <el-form-item v-if="resolveOcr?.district" style="margin-bottom:8px">
                <el-alert :title="'OCR识别分区: '+resolveOcr.district" type="success" :closable="false" show-icon />
              </el-form-item>
              <el-form-item v-else style="margin-bottom:8px">
                <el-alert title="无法识别分区，请手动选择目标分拣口" type="warning" :closable="false" show-icon />
              </el-form-item>
              <el-form-item label="处理方式" required>
                <el-radio-group v-model="resolveForm.action">
                  <el-radio value="resolved">🟢 直接处理</el-radio>
                  <el-radio value="rerouted">📤 分流分拣</el-radio>
                  <el-radio value="discarded">🗑️ 标记废弃</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item v-if="resolveForm.action==='rerouted'" label="分拣口">
                <el-select v-model="resolveForm.target_chute" style="width:100%" placeholder="请选择目标分拣口">
                  <el-option v-for="c in chuteOptions" :key="c.chute_code" :label="c.chute_code+' '+c.name" :value="c.chute_code" :disabled="c.chute_code==='CH-006'">
                    <span>{{ c.chute_code }} {{ c.name }}</span>
                    <span v-if="c.chute_code===suggestChute" style="color:#67C23A;font-size:11px"> ← 推荐</span>
                  </el-option>
                </el-select>
              </el-form-item>
              <el-form-item label="处理人">
                <el-input v-model="resolveForm.handler" placeholder="请输入处理人姓名" />
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="resolveForm.note" type="textarea" :rows="2" placeholder="处理详情..." />
              </el-form-item>
            </el-form>
          </el-col>
        </el-row>
      </div>
      <template #footer>
        <el-button @click="resolveDialog=false">取消</el-button>
        <el-button v-if="resolveStep===0" type="warning" @click="doClaim" :loading="claiming">确认领取</el-button>
        <el-button v-else type="primary" @click="doResolve" :loading="resolving">提交办结</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useAuthStore } from '@/store/auth'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const store = useAuthStore()
const baseUrl = 'http://127.0.0.1:8003'

function previewSrc(row) {
  // 优先用后端返回的完整 image_url，降级用 image_path 拼接
  if (row.image_url) return `${baseUrl}${row.image_url}`
  if (row.image_path) return `${baseUrl}/uploads/${row.image_path}`
  return ''
}

const records = ref([])
const page = ref(1)
const total = ref(0)
// eslint-disable-next-line no-unused-vars
const createDialog = ref(false)
const detailDialog = ref(false)
const resolveDialog = ref(false)
const resolveStep = ref(0)
const claiming = ref(false)
const resolving = ref(false)
const selectedRow = ref(null)
const resolveRow = ref(null)
const resolveFormRef = ref(null)
const resolveForm = reactive({ action:'rerouted', handler:'', note:'', target_chute:'' })

// 自动填入当前操作员姓名
onMounted(() => {
  const user = store.user
  if (user?.display_name) resolveForm.handler = user.display_name
  fetch()
})

const stats = computed(() => ({
  total: records.value.length,
  damage: records.value.filter(r => r.exception_type === 'damage').length,
  deformed: records.value.filter(r => r.exception_type === 'deformed').length,
  leak: records.value.filter(r => r.exception_type === 'leak').length,
  stain: records.value.filter(r => r.exception_type === 'stain').length,
  pending: records.value.filter(r => r.status === 'pending').length,
}))

function typeColor(t) {
  const m = { damage:'danger', deformed:'warning', leak:'primary', stain:'info', ocr_fail:'danger', ocr_incomplete:'warning', other:'' }
  return m[t] || 'info'
}
function typeLabel(t) {
  const m = { damage:'💔 破损', deformed:'📐 变形', leak:'💧 渗漏', stain:'🟤 污渍', ocr_fail:'❌ OCR失败', ocr_incomplete:'📝 识别不完整', other:'📋 其他' }
  return m[t] || t
}

function formatDetail(detail) {
  if (!detail) return '-'
  try {
    let arr = typeof detail === 'string' ? JSON.parse(detail.replace(/'/g, '"')) : detail
    if (!Array.isArray(arr)) arr = [arr]
    return arr.map(item => {
      const sev = item.severity === 'high' ? '🔴' : item.severity === 'medium' ? '🟡' : '🟢'
      return `<div style="margin:2px 0">${sev} <b>${item.description || JSON.stringify(item)}</b></div>`
    }).join('')
  } catch { return `<span style="color:#666">${detail}</span>` }
}

function onImgErr() {}

async function fetch(p = 1) {
  page.value = p
  try {
    const res = await request.get('/api/exceptions', { params: { page: p, chute_code: 'CH-006' } })
    records.value = res.data.items; total.value = res.data.total
  } catch { /* ignore */ }
}

function showDetail(row) { selectedRow.value = row; detailDialog.value = true }

async function startProcess(row) {
  try {
    await request.post(`/api/exceptions/${row.id}/process`)
    ElMessage.success('已领取工单')
    fetch(page.value)
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '领取失败')
  }
}

const resolveOcr = ref(null)
const chuteOptions = ref([])
const suggestChute = ref('')
const loadingOcr = ref(false)
const provinceChuteMap = { '东湖区':'CH-001', '西湖区':'CH-002', '青云谱区':'CH-003', '青山湖区':'CH-004', '红谷滩区':'CH-005' }

async function openResolveDialog(row) {
  resolveRow.value = row
  resolveStep.value = row.status === 'pending' ? 0 : 1
  resolveOcr.value = null
  suggestChute.value = ''

  try { const r = await request.get('/api/chutes'); chuteOptions.value = r.data } catch { /* ignore */ }

  loadingOcr.value = true
  try {
    const r = await request.get(`/api/ocr/results/${row.file_id}`)
    resolveOcr.value = r.data || { district:'', city:'' }
    if (resolveOcr.value?.district) suggestChute.value = provinceChuteMap[resolveOcr.value.district] || ''

    // 优先从异常列表的 image_url 回退
    if (row.image_url) {
      resolveOcr.value = { ...resolveOcr.value, resolve_img_url: `${baseUrl}${row.image_url}` }
    }

    // 然后尝试从 upload/records 精确查询图片
    try {
      const upRes = await request.get('/api/upload/records', { params: { page: 1, page_size: 200 } })
      const items = upRes.data?.items || []
      const match = items.find(i => i.file_id === row.file_id)
      if (match?.file_url) {
        resolveOcr.value = { ...resolveOcr.value, resolve_img_url: `${baseUrl}${match.file_url}` }
      }
    } catch { /* ignore */ }
  } catch {
    resolveOcr.value = { district:'', city:'', resolve_img_url: row.image_url ? `${baseUrl}${row.image_url}` : '' }
  }
  loadingOcr.value = false

  // CH-006操作员默认分流到推荐正常口，无推荐时才直接处理
  if (suggestChute.value) {
    Object.assign(resolveForm, { action:'rerouted', handler: store.user?.display_name || '', note:'', target_chute: suggestChute.value })
  } else {
    Object.assign(resolveForm, { action:'resolved', handler: store.user?.display_name || '', note:'', target_chute: 'CH-006' })
  }
  resolveDialog.value = true
}

async function doClaim() {
  claiming.value = true
  try {
    await request.post(`/api/exceptions/${resolveRow.value.id}/process`)
    ElMessage.success('已领取，请填写处理信息')
    resolveStep.value = 1
  } catch (e) { ElMessage.error(e?.response?.data?.message || '领取失败') }
  claiming.value = false
}

async function doResolve() {
  if (!resolveForm.handler) { ElMessage.warning('请填写处理人姓名'); return }
  resolving.value = true
  try {
    await request.put(`/api/exceptions/${resolveRow.value.id}/resolve`, { ...resolveForm })
    ElMessage.success(resolveForm.action === 'rerouted' ? `已分流至${resolveForm.target_chute}` : '处理完成')
    resolveDialog.value = false
    fetch(page.value)
  } catch (e) { ElMessage.error(e?.response?.data?.message || '提交失败') }
  resolving.value = false
}
</script>

<style scoped>
.ch006-page { min-height: calc(100vh - 80px); }
.exc-stats { display: grid; grid-template-columns: repeat(6,1fr); gap: 12px; margin-bottom: 16px; }
.exc-stat { border-radius: 12px; padding: 14px; text-align: center; color: #fff; }
.exc-num { font-size: 24px; font-weight: 800; }
.exc-lab { font-size: 11px; opacity: .85; margin-top: 4px; }
.exc-stat.total { background: linear-gradient(135deg,#667eea,#764ba2); }
.exc-stat.damage { background: linear-gradient(135deg,#f5576c,#e74c3c); }
.exc-stat.deformed { background: linear-gradient(135deg,#fa8231,#f7b731); }
.exc-stat.leak { background: linear-gradient(135deg,#4facfe,#00f2fe); color: #1a3a1a; }
.exc-stat.stain { background: linear-gradient(135deg,#a18cd1,#fbc2eb); }
.exc-stat.pending { background: linear-gradient(135deg,#ff6b6b,#c0392b); }
.blink { display: inline-block; width: 8px; height: 8px; background: #fff; border-radius: 50%; margin-right: 6px; vertical-align: middle; animation: blink 1s infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
.img-placeholder { width:52px;height:52px;display:flex;align-items:center;justify-content:center;background:#f0f0f0;border-radius:4px;font-size:20px; }
.detail-preview { font-size:12px; line-height:1.6; }
.detail-dialog { max-height: 400px; overflow-y: auto; }
.no-img { height:180px; display:flex; align-items:center; justify-content:center; background:#f5f5f5; border-radius:8px; font-size:36px; color:#ccc; }

@media (max-width: 768px) {
  .exc-stats { grid-template-columns: repeat(3,1fr); }
}
</style>
