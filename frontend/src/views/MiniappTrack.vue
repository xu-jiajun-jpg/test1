<template>
  <div class="miniapp-page">
    <div class="phone-frame">
      <div class="phone-status-bar">📶 9:41</div>
      <div class="phone-screen">
        <!-- 头部 -->
        <div class="header">
          <div class="header-title">📦 包裹追踪</div>
          <div class="header-desc">查询运单分拣状态与物流信息</div>
        </div>

        <!-- 输入区 -->
        <div class="card">
          <div class="input-row">
            <el-input v-model="trackingNo" placeholder="输入运单号（如 SF7591795563）" size="large" @keyup.enter="search">
              <template #prefix>🔍</template>
            </el-input>
            <el-button type="primary" @click="search">查询</el-button>
          </div>
        </div>

        <!-- 示例运单号 -->
        <div class="card demo-cards" v-if="sampleNos.length">
          <div class="section-title">📋 示例运单号（点击查询）</div>
          <div class="demo-list">
            <el-tag v-for="no in sampleNos" :key="no" type="info" class="demo-tag" @click="searchNo(no)">{{ no }}</el-tag>
          </div>
        </div>

        <!-- 加载中 -->
        <el-skeleton v-if="loading" :rows="6" animated style="margin-bottom:20px" />

        <!-- 查询结果 -->
        <template v-if="result">
          <!-- 包裹状态卡片 -->
          <div class="card status-card" :class="'status-' + result.status">
            <div class="track-no">{{ trackingNo }}</div>
            <el-tag :type="statusType" size="large" effect="dark">{{ statusLabel }}</el-tag>
            <div class="eta" v-if="result.target_chute">分拣至：{{ result.target_chute }}</div>
          </div>

          <!-- 快递信息 -->
          <div class="card" v-if="result.province">
            <div class="section-title">📋 运单信息</div>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="分区">{{ result.district || '-' }}</el-descriptions-item>
              <el-descriptions-item label="城市">{{ result.city || '-' }}</el-descriptions-item>
              <el-descriptions-item label="分拣口">{{ result.target_chute || '-' }}</el-descriptions-item>
              <el-descriptions-item label="状态">{{ statusLabel }}</el-descriptions-item>
            </el-descriptions>
            <el-button type="primary" size="small" style="margin-top:12px" @click="showAddress=true">✏️ 修改收件地址</el-button>
          </div>

          <!-- 分拣时间线 -->
          <div class="card" v-if="timeline.length">
            <div class="section-title">🚚 分拣进度</div>
            <el-timeline>
              <el-timeline-item
                v-for="(item, i) in timeline"
                :key="i"
                :timestamp="item.time"
                :color="i===0 ? '#409EFF' : '#67C23A'"
              >
                {{ item.desc }}
              </el-timeline-item>
            </el-timeline>
          </div>
        </template>

        <!-- 无结果 -->
        <el-empty v-if="!loading && searched && !result" description="未查到该运单" />
      </div>
    </div>

    <!-- 修改地址对话框 -->
    <el-dialog title="✏️ 修改收件地址" v-model="showAddress" width="450px">
      <el-form :model="addrForm" label-width="70px">
        <el-form-item label="运单号"><el-input v-model="trackingNo" disabled /></el-form-item>
        <el-form-item label="分区"><el-input v-model="addrForm.district" placeholder="如：东湖区" /></el-form-item>
        <el-form-item label="城市"><el-input v-model="addrForm.city" placeholder="如：广州市" /></el-form-item>
        <el-form-item label="新地址"><el-input v-model="addrForm.address" placeholder="详细地址" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddress=false">取消</el-button>
        <el-button type="primary" @click="submitAddress" :loading="addrLoading">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const trackingNo = ref('')
const loading = ref(false)
const searched = ref(false)
const result = ref(null)
const timeline = ref([])
const sampleNos = ref([])
const showAddress = ref(false)
const addrLoading = ref(false)
const addrForm = ref({ district:'', city:'', address:'' })

const statusType = computed(() => {
  if (!result.value) return 'info'
  return result.value.status === 'success' ? 'success' : result.value.status === 'failed' ? 'danger' : 'warning'
})
const statusLabel = computed(() => {
  if (!result.value) return '查询中'
  const m = { success:'✅ 已分拣', no_match:'⚠️ 无匹配规则', failed:'❌ 分拣失败', manual_required:'🔧 需人工处理' }
  return m[result.value.status] || result.value.status
})

async function search() {
  if (!trackingNo.value.trim()) return
  loading.value = true; searched.value = true
  try {
    const res = await request.get(`/api/track/${encodeURIComponent(trackingNo.value.trim())}`)
    const data = res.data
    result.value = data
    if (data.timeline) {
      timeline.value = data.timeline.slice().reverse()
    }
  } catch { result.value = null; timeline.value = [] }
  loading.value = false
}
function searchNo(no) { trackingNo.value = no; search() }

async function submitAddress() {
  if (!addrForm.value.district) { ElMessage.warning('请填写分区'); return }
  addrLoading.value = true
  try {
    await request.put(`/api/track/${trackingNo.value}/address`, {
      district: addrForm.value.district,
      city: addrForm.value.city,
      address: addrForm.value.address,
    })
    ElMessage.success('地址已修改，重新分拣中')
    showAddress.value = false
    search()
  } catch { ElMessage.error('修改失败') }
  addrLoading.value = false
}

onMounted(async () => {
  // 加载示例运单号
  try {
    const res = await request.get('/api/sort/decisions?page=1&page_size=10')
    const nos = (res.data.items || []).map(d => d.tracking_number).filter(Boolean)
    sampleNos.value = [...new Set(nos)].slice(0, 6)
  } catch { /* no samples available */ }
})
</script>

<style scoped>
.miniapp-page { display:flex; justify-content:center; padding:20px; }
.phone-frame { width:420px; border:2px solid #333; border-radius:24px; overflow:hidden; background:#f5f5f5; box-shadow:0 4px 20px rgba(0,0,0,0.15); }
.phone-status-bar { background:#333; color:#fff; text-align:center; padding:8px; font-size:12px; }
.phone-screen { padding:16px; max-height:80vh; overflow-y:auto; }
.header { text-align:center; padding:20px 0; }
.header-title { font-size:22px; font-weight:bold; color:#2c3e50; }
.header-desc { font-size:13px; color:#909399; margin-top:6px; }
.card { background:#fff; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 1px 6px rgba(0,0,0,0.06); }
.input-row { display:flex; gap:8px; }
.input-row .el-input { flex:1; }
.section-title { font-size:15px; font-weight:bold; margin-bottom:12px; }
.demo-list { display:flex; flex-wrap:wrap; gap:6px; }
.demo-tag { cursor:pointer; }
.status-card { text-align:center; padding:24px; color:#fff; }
.status-card.status-success { background:linear-gradient(135deg,#1e3c72,#2a5298); }
.status-card:not(.status-success) { background:linear-gradient(135deg,#c0392b,#e74c3c); }
.track-no { font-size:18px; font-weight:bold; margin-bottom:8px; }
.eta { margin-top:10px; font-size:13px; opacity:0.9; }
</style>
