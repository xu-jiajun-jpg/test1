<template>
  <div class="page">
    <h2>📦 装车优化 &middot; 🗺️ 路径规划</h2>

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="📦 装车优化" name="packing">
        <el-row :gutter="16">
          <el-col :span="16">
            <div class="pack-viz">
              <div class="viz-section"><div class="viz-label">俯视图（顶视）</div><canvas ref="topCanvas" width="500" height="320" class="viz-canvas"></canvas></div>
              <div class="viz-section"><div class="viz-label">正视图（侧面）</div><canvas ref="frontCanvas" width="500" height="320" class="viz-canvas"></canvas></div>
            </div>
          </el-col>
          <el-col :span="8">
            <el-card header="⚙️ 装箱设置">
              <el-form label-width="80px" size="small">
                <el-form-item label="车长(cm)"><el-input-number v-model="vehicle.l" :min="50" :max="600" :step="10" /></el-form-item>
                <el-form-item label="车宽(cm)"><el-input-number v-model="vehicle.w" :min="50" :max="300" :step="10" /></el-form-item>
                <el-form-item label="车高(cm)"><el-input-number v-model="vehicle.h" :min="50" :max="300" :step="10" /></el-form-item>
                <el-form-item label="包裹"><span style="font-size:14px">{{ packDecisionIds.length }} 件</span></el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="runPack" :loading="packLoading" style="width:100%">🚛 执行装箱优化</el-button>
                </el-form-item>
              </el-form>
            </el-card>
            <el-card v-if="packResult" header="📊 装载统计" style="margin-top:12px">
              <div class="stat-grid">
                <div class="stat-item"><span class="val">{{ packResult.placed_count }}</span><span class="lbl">已装件</span></div>
                <div class="stat-item"><span class="val">{{ packResult.unplaced_count }}</span><span class="lbl">未装件</span></div>
                <div class="stat-item"><span class="val" :style="{color:packResult.fill_rate>=85?'#67C23A':'#E6A23C'}">{{ packResult.fill_rate }}%</span><span class="lbl">填充率</span></div>
                <div class="stat-item"><span class="val">{{ ((packResult.used_volume||0) / 1000000).toFixed(2) }}</span><span class="lbl">已用m³</span></div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="🗺️ 路径规划" name="route">
        <el-row :gutter="16">
          <el-col :span="16">
            <div ref="mapContainer" class="map-canvas"></div>
          </el-col>
          <el-col :span="8">
            <el-card header="🏙️ 配送分区（自动识别）">
              <div style="margin-bottom:6px;font-size:13px;color:#606266">分拣口：<el-tag v-for="c in opChutes" :key="c" size="small" type="primary" style="margin:2px">{{ c }}</el-tag></div>
              <el-select v-model="selectedCities" multiple filterable collapse-tags placeholder="选择配送分区" style="width:100%">
                <el-option v-for="c in cityList" :key="c.name" :label="c.name" :value="c.name" />
              </el-select>
              <el-form label-width="80px" size="small" style="margin-top:8px">
                <el-form-item label="迭代次数"><el-input-number v-model="acoIters" :min="20" :max="200" :step="10" /></el-form-item>
              </el-form>
              <el-button type="primary" @click="runACO" :loading="acoLoading" style="width:100%">🐜 运行蚁群算法</el-button>
            </el-card>

            <el-card v-if="routeResult" header="🛣️ 路径结果" style="margin-top:12px">
              <div class="route-stats">
                <div>总里程: <b>{{ routeResult.total_distance_km }} km</b></div>
                <div>迭代: <b>{{ routeResult.iterations }}</b> 次</div>
              </div>
              <div style="margin-top:8px">
                <el-tag v-for="(city,i) in routeResult.path" :key="city" :type="i===0?'success':i===routeResult.path.length-1?'danger':''" size="small" style="margin:2px">{{ i+1 }}.{{ city }}</el-tag>
              </div>
              <div style="margin-top:4px;font-size:11px;color:#999">📍 南昌分拣中心 → 各分区配送</div>
              <el-button type="success" size="small" style="width:100%;margin-top:10px" @click="requestDispatch" :loading="reqLoading">📤 确认路径，向管理员申请发车</el-button>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const router = useRouter()
const activeTab = ref('packing')

// ---- 操作员选中包裹 ----
const opChutes = ref([])
const packDecisionIds = ref([])

onMounted(async () => {
  // 优先从 sessionStorage 读取待发车包裹（操作员从任务页选中的）
  const stored = sessionStorage.getItem('pending_dispatch_ids')
  if (stored) {
    try {
      const ids = JSON.parse(stored)
      if (ids.length) {
        packDecisionIds.value = ids
        // 获取这批包裹的分拣口和分区信息
        const res = await request.get('/api/operators/my/tasks')
        const tasks = res.data?.tasks || []
        const matched = tasks.filter(t => ids.includes(t.decision_id || t.file_id))
        opChutes.value = [...new Set(matched.map(t => t.target_chute).filter(Boolean))]
        const districts = [...new Set(matched.map(t => t.district).filter(Boolean))]
        if (districts.length) selectedCities.value = districts
      }
    } catch { /* ignore */ }
  }
  // 没有 sessionStorage 数据时，回退到 awaiting_dispatch 任务
  if (!packDecisionIds.value.length) {
    try {
      const res = await request.get('/api/operators/my/tasks')
      const tasks = res.data?.tasks || []
      const awaiting = tasks.filter(t => t.status === 'awaiting_dispatch')
      if (awaiting.length) {
        packDecisionIds.value = awaiting.map(t => t.decision_id).filter(Boolean)
        opChutes.value = [...new Set(awaiting.map(t => t.target_chute).filter(Boolean))]
        const districts = [...new Set(awaiting.map(t => t.district).filter(Boolean))]
        if (districts.length) selectedCities.value = districts
      }
    } catch { /* ignore */ }
  }
  await fetchCities()
})

// ---- 装箱（复用管理员代码） ----
const topCanvas = ref(null), frontCanvas = ref(null)
const vehicle = reactive({ l: 220, w: 200, h: 120 })
const packLoading = ref(false), packResult = ref(null)
const COLORS = ['#FF6B6B','#4ECDC4','#45B7D1','#96CEB4','#FFEAA7','#DDA0DD','#98D8C8','#F7DC6F','#BB8FCE','#85C1E9','#F8C471','#82E0AA','#F1948A','#AED6F1','#D7BDE2','#A3E4D7','#FAD7A0','#E59866','#76D7C4','#F0B27A']

function draw2DPacking(placed, vehicleSize) {
  const tc = topCanvas.value, fc = frontCanvas.value
  if (!tc || !fc) return
  const vl = vehicleSize.length, vw = vehicleSize.width, vh = vehicleSize.height
  const scale = Math.min(480 / vl, 300 / vw)
  const tctx = tc.getContext('2d')
  tctx.clearRect(0, 0, 500, 320)
  tctx.strokeStyle = '#409EFF'; tctx.lineWidth = 3
  tctx.strokeRect(10, 10, vl * scale, vw * scale)
  tctx.fillStyle = 'rgba(64,158,255,0.06)'
  tctx.fillRect(10, 10, vl * scale, vw * scale)
  for (const pkg of placed) {
    const pos = pkg.position; const ps = pkg.placed_size
    const x = 10 + pos.x * scale, y = 10 + pos.y * scale
    const w = ps.l * scale, h = ps.w * scale
    tctx.fillStyle = pkg.color; tctx.fillRect(x, y, w, h)
    tctx.strokeStyle = '#fff'; tctx.lineWidth = 1; tctx.strokeRect(x, y, w, h)
  }
  const fctx = fc.getContext('2d')
  const hScale = Math.min(480 / vl, 290 / vh)
  fctx.clearRect(0, 0, 500, 320)
  fctx.strokeStyle = '#409EFF'; fctx.lineWidth = 3
  fctx.strokeRect(10, 10, vl * hScale, vh * hScale)
  fctx.fillStyle = 'rgba(64,158,255,0.06)'
  fctx.fillRect(10, 10, vl * hScale, vh * hScale)
  for (const pkg of placed) {
    const pos = pkg.position; const ps = pkg.placed_size
    const x = 10 + pos.x * hScale
    const y = 10 + (vh - (pos.z + ps.h)) * hScale
    const w = ps.l * hScale, ht = ps.h * hScale
    fctx.fillStyle = pkg.color; fctx.fillRect(x, y, w, ht)
    fctx.strokeStyle = '#fff'; fctx.lineWidth = 1; fctx.strokeRect(x, y, w, ht)
  }
}

async function runPack() {
  if (!packDecisionIds.value.length) return ElMessage.warning('无用包裹数据')
  packLoading.value = true; packResult.value = null
  try {
    const { data: r } = await request({ method: 'post', url: '/api/logistics/pack', data: { container: { length: vehicle.l, width: vehicle.w, height: vehicle.h }, decision_ids: packDecisionIds.value, limit: packDecisionIds.value.length + 10 }, timeout: 60000 })
    const d = r.data || r
    d.placed = (d.placed || []).map((p, i) => ({ ...p, color: COLORS[i % COLORS.length], destination: p.destination || '', position: { x: p.x || 0, y: p.y || 0, z: p.z || 0 }, placed_size: { l: p.l || 0, w: p.w || 0, h: p.h || 0 }, size: { l: p.l || 0, w: p.w || 0, h: p.h || 0 }, volume: (p.l || 0) * (p.w || 0) * (p.h || 0) }))
    d.placed_count = d.placed.length; d.unplaced_count = (d.unplaced || []).length; d.fill_rate = d.fill_rate || 0; d.used_volume = d.used_volume || 0
    packResult.value = d
    await nextTick()
    draw2DPacking(d.placed, { length: vehicle.l, width: vehicle.w, height: vehicle.h })
  } catch { ElMessage.error('装箱计算失败') }
  packLoading.value = false
}

// ---- 地图 + 路径（100% 复制管理员 Logistics.vue 代码） ----
const mapContainer = ref(null)
const cityList = ref([])
const selectedCities = ref(['东湖区','西湖区','青云谱区','青山湖区','红谷滩区'])
const acoIters = ref(100)
const acoLoading = ref(false)
const routeResult = ref(null)
const reqLoading = ref(false)

const GAODE_URL = 'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}'
const GAODE_ATTR = '&copy;物流分拣平台'

let mapInstance = null, routePolyline = null

let leafletReady = null
function loadLeaflet() {
  if (leafletReady) return leafletReady
  leafletReady = new Promise((resolve, reject) => {
    if (window.L) return resolve(window.L)
    const link = document.createElement('link'); link.rel = 'stylesheet'
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
    link.onerror = () => { const l2 = document.createElement('link'); l2.rel = 'stylesheet'; l2.href = 'https://cdn.bootcdn.net/ajax/libs/leaflet/1.9.4/leaflet.css'; document.head.appendChild(l2) }
    document.head.appendChild(link)
    function tryLoad(urls, idx) {
      if (idx >= urls.length) return reject(new Error('Leaflet fail'))
      const s = document.createElement('script'); s.src = urls[idx]
      s.onload = () => resolve(window.L)
      s.onerror = () => tryLoad(urls, idx + 1)
      document.head.appendChild(s)
    }
    tryLoad(['https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', 'https://cdn.bootcdn.net/ajax/libs/leaflet/1.9.4/leaflet.js'], 0)
  })
  return leafletReady
}

async function initMap(container) {
  if (!container) return null
  const L = await loadLeaflet()
  const map = L.map(container, { attributionControl: false }).setView([28.68, 115.86], 12)
  L.tileLayer(GAODE_URL, { maxZoom: 18, subdomains: ['1','2','3','4'] }).addTo(map)
  L.control.attribution({ position: 'bottomright' }).setPrefix('').addAttribution(GAODE_ATTR).addTo(map)
  return map
}

async function drawRoute(map, waypoints, polyRef) {
  const L = await loadLeaflet()
  if (!map || !waypoints?.length) return null
  if (polyRef) { map.removeLayer(polyRef); polyRef = null }
  map.eachLayer(layer => { if (layer instanceof L.Marker || layer instanceof L.CircleMarker) map.removeLayer(layer) })
  const coords = waypoints.map(w => [w.lat, w.lng])
  const newPoly = L.polyline(coords, { color: '#409EFF', weight: 5, opacity: 0.9 }).addTo(map)
  waypoints.forEach((wp, i) => {
    const color = i === 0 ? '#67C23A' : i === waypoints.length - 1 ? '#F56C6C' : '#409EFF'
    L.circleMarker([wp.lat, wp.lng], { radius: 8, fillColor: color, color: '#fff', weight: 2, fillOpacity: 1 }).bindTooltip(`${i + 1}. ${wp.name}`, { permanent: false, direction: 'top' }).addTo(map)
  })
  map.fitBounds(coords, { padding: [30, 30] })
  return newPoly
}

async function runACO() {
  if (selectedCities.value.length < 1) { ElMessage.warning('请至少选择1个配送分区'); return }
  activeTab.value = 'route'; await nextTick()
  acoLoading.value = true; routeResult.value = null
  try {
    if (!mapInstance && mapContainer.value) mapInstance = await initMap(mapContainer.value)
    const resp = await request.post('/api/logistics/route-plan', { cities: selectedCities.value, iterations: acoIters.value })
    routeResult.value = resp.data
    await nextTick()
    if (!mapInstance) mapInstance = await initMap(mapContainer.value)
    if (mapInstance) routePolyline = await drawRoute(mapInstance, routeResult.value?.waypoints, routePolyline)
    ElMessage.success('路径规划完成')
  } catch { ElMessage.error('路径规划失败') }
  acoLoading.value = false
}

async function requestDispatch() {
  if (!packDecisionIds.value.length) return ElMessage.warning('无包裹')
  reqLoading.value = true
  try {
    const res = await request.post('/api/tasks/request-dispatch', { decision_ids: packDecisionIds.value })
    if (res.code === 400) { ElMessage.warning(res.message); reqLoading.value = false; return }
    ElMessage.success(res.message || '已提交发车申请，等待管理员审批')
    sessionStorage.removeItem('pending_dispatch_ids')
    setTimeout(() => router.push('/operator/tasks'), 1500)
  } catch (e) { ElMessage.error(e?.response?.data?.detail || '申请失败') }
  reqLoading.value = false
}

async function fetchCities() {
  try { const resp = await request.get('/api/logistics/cities'); cityList.value = resp.data?.districts || [] } catch { /* ignore */ }
}

watch(activeTab, async (tab) => {
  await nextTick()
  if (tab === 'route' && !mapInstance && mapContainer.value) mapInstance = await initMap(mapContainer.value)
})

onUnmounted(() => { if (mapInstance) { mapInstance.remove(); mapInstance = null } })
</script>

<style scoped>
.page { padding: 20px; }
h2 { margin-bottom: 16px; color: #2c3e50; }
.pack-viz { display: flex; gap: 16px; }
.viz-section { flex: 1; }
.viz-label { font-size: 13px; font-weight: 600; color: #606266; margin-bottom: 8px; text-align: center; }
.viz-canvas { width: 100%; height: auto; background: #1a1a2e; border-radius: 10px; border: 2px solid #409EFF; }
.map-canvas { width: 100%; height: 500px; border-radius: 12px; border: 2px solid #e0e0e0; z-index: 1; }
.stat-grid { display: flex; gap: 8px; }
.stat-item { flex: 1; text-align: center; background: #f5f7fa; border-radius: 8px; padding: 12px 8px; }
.stat-item .val { display: block; font-size: 24px; font-weight: 800; color: #409EFF; }
.stat-item .lbl { font-size: 11px; color: #909399; margin-top: 4px; }
.route-stats { display: flex; gap: 20px; font-size: 14px; color: #606266; }
</style>
