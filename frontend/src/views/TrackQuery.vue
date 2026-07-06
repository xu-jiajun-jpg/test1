<template>
  <div class="page" style="padding:40px;max-width:700px;margin:0 auto;">
    <h2>🔍 包裹追踪</h2>
    <el-input v-model="trackingNo" placeholder="输入运单号查询（如 SF1234567890）" clearable @keyup.enter="search">
      <template #append><el-button @click="search" :loading="loading">查询</el-button></template>
    </el-input>

    <div v-if="loading" style="text-align:center;margin-top:40px">
      <el-icon class="is-loading" :size="32"><i class="el-icon-loading" /></el-icon>
      <p style="color:#999;margin-top:8px">查询中...</p>
    </div>

    <template v-else-if="searched && (result?.length || delivery)">
      <!-- 配送信息 -->
      <el-card v-if="delivery" style="margin-top:20px;margin-bottom:12px" header="🚛 配送信息">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="当前状态">
            <el-tag :type="delivery.node_status_code>=4?'success':'warning'">{{ delivery.node_status_name || '已揽收' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="承运车辆">{{ delivery.active_vehicle || '待分配' }}</el-descriptions-item>
          <el-descriptions-item label="发货地">{{ delivery.origin || '南昌' }}</el-descriptions-item>
          <el-descriptions-item label="目的地">{{ delivery.destination || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 分拣信息 -->
      <el-card v-if="result && result.length" style="margin-bottom:12px">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="运单号">{{ trackingNo }}</el-descriptions-item>
          <el-descriptions-item label="状态"><el-tag :type="latestStatus==='delivered'?'success':'warning'">{{ statusLabel }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="最新节点">{{ result[0]?.desc }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ result[0]?.time }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
      <el-card v-if="result && result.length" header="物流轨迹">
        <el-timeline>
          <el-timeline-item
            v-for="(item, i) in result"
            :key="i"
            :timestamp="item.time"
            :color="i === 0 ? '#409EFF' : '#c0c4cc'"
            :type="i === 0 ? 'primary' : undefined"
          >
            {{ item.desc }}
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </template>

    <el-empty v-else-if="searched" description="未找到该运单记录" />
  </div>
</template>
<script setup>
import { ref, computed } from 'vue'
import request from '@/api/request'
const trackingNo = ref('')
const result = ref(null)
const delivery = ref(null)
const loading = ref(false)
const searched = ref(false)

const latestStatus = computed(() => {
  const first = result.value?.[0]
  if (!first) return ''
  if (first.desc?.includes('签收')) return 'delivered'
  if (first.desc?.includes('派送')) return 'delivering'
  if (first.desc?.includes('运输')) return 'transit'
  return 'processing'
})
const statusLabel = computed(() => {
  const m = { delivered:'已签收', delivering:'派送中', transit:'运输中', processing:'处理中' }
  return m[latestStatus.value] || '处理中'
})

async function search() {
  if (!trackingNo.value) return
  loading.value = true; searched.value = false
  try {
    const [trackRes, logiRes] = await Promise.allSettled([
      request.get(`/api/track/${trackingNo.value}`),
      request.get(`/api/logistics/track/${trackingNo.value}`),
    ])
    if (trackRes.status === 'fulfilled') result.value = trackRes.value.data?.timeline || []
    else result.value = null
    if (logiRes.status === 'fulfilled') delivery.value = logiRes.value.data
    else delivery.value = null
  } catch { result.value = null; delivery.value = null }
  loading.value = false; searched.value = true
}
</script>
