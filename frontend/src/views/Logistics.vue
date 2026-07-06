<template>
  <div class="page">
    <h2>🚛 发车审批 &middot; 发车监控</h2>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- ==================== 发车审批 ==================== -->
      <el-tab-pane label="📋 发车审批" name="approval">
        <el-card header="🚛 操作员发车申请">
          <div style="margin-bottom:12px;display:flex;justify-content:space-between;align-items:center">
            <span>待审批：<b style="color:#E6A23C">{{ dispatchRequests.length }}</b> 个操作员</span>
            <el-button size="small" type="primary" @click="fetchDispatchRequests" :loading="drLoading">🔄 刷新</el-button>
          </div>
          <el-table :data="dispatchRequests" stripe v-if="dispatchRequests.length">
            <el-table-column prop="operator_name" label="操作员" width="100">
              <template #default="{ row }"><el-tag size="small" type="warning">{{ row.operator_name || '—' }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="count" label="包裹数" width="80" />
            <el-table-column label="管辖分拣口" width="150">
              <template #default="{ row }">{{ (row.chutes || []).join('、') }}</template>
            </el-table-column>
            <el-table-column label="目的区" min-width="150">
              <template #default="{ row }">{{ [...new Set(row.districts || [])].join('、') }}</template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button size="small" type="success" @click="approveDispatch(row)">✅ 审批发车</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无待审批发车申请" :image-size="60" />
        </el-card>
      </el-tab-pane>

      <!-- ==================== 发车监控 ==================== -->
      <el-tab-pane label="🚦 发车监控" name="monitor">
        <!-- 摘要卡片 -->
        <el-row :gutter="16" style="margin-bottom:12px">
          <el-col :span="6"><el-card class="monitor-stat running"><div class="mnum">{{ vehiclesSummary.running }}</div><div class="mlab">🚛 行驶中</div></el-card></el-col>
          <el-col :span="6"><el-card class="monitor-stat idle"><div class="mnum">{{ vehiclesSummary.idle }}</div><div class="mlab">🟢 空闲中</div></el-card></el-col>
          <el-col :span="6"><el-card class="monitor-stat total"><div class="mnum">{{ vehiclesSummary.total }}</div><div class="mlab">📊 总车辆</div></el-card></el-col>
          <el-col :span="6"><el-card class="monitor-stat stopped"><div class="mnum">{{ vehiclesSummary.total - vehiclesSummary.running - vehiclesSummary.idle }}</div><div class="mlab">📋 历史</div></el-card></el-col>
        </el-row>

        <!-- 地图 -->
        <el-row :gutter="16" style="margin-bottom:12px">
          <el-col :span="16">
            <div ref="monitorMap" class="map-canvas"></div>
          </el-col>
          <el-col :span="8">
            <el-card header="🚛 车辆实时状态">
              <div v-if="vehicleState" class="vehicle-panel">
                <div class="v-id">车辆 {{ vehicleState.vehicle_id }}</div>
                <el-progress :percentage="vehicleState.progress_percent" :color="'#409EFF'" :stroke-width="14" />
                <div class="v-stats">
                  <div class="row"><span>状态</span>
                    <el-tag :type="vehicleState.status==='running'?'success':vehicleState.status==='idle'?'info':'warning'" size="small">
                      {{ {running:'行驶中',idle:'空闲待命',paused:'暂停'}[vehicleState.status] || vehicleState.status }}
                    </el-tag>
                  </div>
                  <div class="row"><span>速度</span><b>{{ vehicleState.speed_kmh }} km/h</b></div>
                  <div class="row"><span>已行驶</span><b>{{ vehicleState.traveled_km }} km</b></div>
                  <div class="row"><span>剩余</span><b>{{ vehicleState.remaining_km }} km</b></div>
                  <div class="row"><span>预计到达</span><b style="color:#409EFF;font-size:18px">{{ formatETA(vehicleState.eta_minutes) }}</b></div>
                </div>
              </div>
              <el-empty v-else description="暂无活跃车辆" />
            </el-card>
          </el-col>
        </el-row>

        <!-- 绑定关系摘要 -->
        <el-card header="🔗 包裹-车辆绑定关系" style="margin-bottom:12px">
          <div class="bind-bar" v-if="bindingSummary">
            <div class="bind-stat"><span class="b-num">{{ bindingSummary.total_packages }}</span><span class="b-lab">总包裹</span></div>
            <div class="bind-stat"><span class="b-num" style="color:#409EFF">{{ bindingSummary.bound_packages }}</span><span class="b-lab">已绑定</span></div>
            <div class="bind-stat"><span class="b-num" style="color:#E6A23C">{{ bindingSummary.in_transit }}</span><span class="b-lab">运输中</span></div>
            <div class="bind-stat"><span class="b-num" style="color:#67C23A">{{ bindingSummary.delivered }}</span><span class="b-lab">已签收</span></div>
          </div>
          <div v-if="bindingSummary.by_vehicle?.length" style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px">
            <el-tag v-for="bv in bindingSummary.by_vehicle" :key="bv.vehicle_id" type="primary" size="small">
              🚛 {{ bv.vehicle_id }}: {{ bv.count }}件
            </el-tag>
          </div>
          <el-empty v-if="!bindingSummary" description="暂无绑定数据" :image-size="40" />
        </el-card>

        <!-- 所有车辆状态表 -->
        <el-card header="📋 所有车辆状态表">
          <el-table :data="allVehicles" size="small" stripe max-height="400" highlight-current-row @row-click="selectVehicle">
            <el-table-column label="车辆ID" prop="vehicle_id" width="120" />
            <el-table-column label="状态" width="90">
              <template #default="{row}">
                <el-tag :type="row.status==='running'?'success':row.status==='idle'?'info':'warning'" size="small">
                  {{ {running:'行驶中',idle:'空闲待命',paused:'暂停'}[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="进度" width="150">
              <template #default="{row}"><el-progress :percentage="row.progress_percent" :stroke-width="8" :color="row.status==='arrived'?'#67C23A':'#409EFF'" /></template>
            </el-table-column>
            <el-table-column label="包裹" prop="package_count" width="65">
              <template #default="{row}">{{ row.package_count ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="速度(km/h)" prop="speed_kmh" width="95" />
            <el-table-column label="已行驶(km)" prop="traveled_km" width="100" />
            <el-table-column label="剩余(km)" prop="remaining_km" width="90" />
            <el-table-column label="预计到达" width="110">
              <template #default="{row}"><b style="color:#409EFF">{{ formatETA(row.eta_minutes) }}</b></template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!allVehicles.length" description="暂无车辆记录" />
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import request from '@/api/request'
import { ElMessage, ElMessageBox } from 'element-plus'

const activeTab = ref('route')  // 默认路径规划页（操作员发车后跳转到此）

// ===== 发车审批 =====
const dispatchRequests = ref([])
const drLoading = ref(false)
async function fetchDispatchRequests() {
  drLoading.value = true
  try {
    const res = await request.get('/api/tasks/dispatch-requests')
    dispatchRequests.value = res.data?.requests || []
  } catch { dispatchRequests.value = [] }
  drLoading.value = false
}

async function approveDispatch(row) {
  const ids = row.decision_ids || []
  if (!ids.length) { ElMessage.warning('无包裹可审批'); return }
  try {
    await ElMessageBox.confirm(`确认审批 ${row.operator_name} 的 ${row.count} 件包裹并发车？`, '发车审批', { type: 'info' })
    const res = await request.post('/api/tasks/approve-dispatch', { decision_ids: ids })
    ElMessage.success(res.message || '审批完成，已发车')
    fetchDispatchRequests()
  } catch { /* 用户取消 */ }
}

watch(activeTab, async (tab) => {
  if (tab === 'approval') fetchDispatchRequests()
})

// ===== 地图 + 路径 =====
const mapContainer = ref(null)
const monitorMap = ref(null)
const cityList = ref([])
const selectedCities = ref(['东湖区','西湖区','青云谱区','青山湖区','红谷滩区'])
const acoIters = ref(100)
const acoLoading = ref(false)
const routeResult = ref(null)

// 高德地图瓦片URL（国内无需Key）
const GAODE_URL = 'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}'
const GAODE_ATTR = '&copy;物流分拣平台'

let mapInstance = null, monitorMapInstance = null
let routePolyline = null, monitorPolyline = null
let vehicleMarker = null

async function initMap(container) {
  if (!container) return null
  const L = await loadLeaflet()
  const map = L.map(container, { attributionControl: false }).setView([28.68, 115.86], 12)
  L.tileLayer(GAODE_URL, { maxZoom: 18, subdomains: ['1','2','3','4'] }).addTo(map)
  // 添加简单水印
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
    L.circleMarker([wp.lat, wp.lng], {
      radius: 8, fillColor: color, color: '#fff', weight: 2, fillOpacity: 1
    }).bindTooltip(`${i + 1}. ${wp.name}`, { permanent: false, direction: 'top' }).addTo(map)
  })
  map.fitBounds(coords, { padding: [30, 30] })
  return newPoly
}

// eslint-disable-next-line no-unused-vars
async function runACO() {
  if (selectedCities.value.length < 2) { ElMessage.warning('请至少选择1个配送分区（起点南昌自动添加）'); return }
  acoLoading.value = true
  try {
    const resp = await request.post('/api/logistics/route-plan', { cities: selectedCities.value, iterations: acoIters.value })
    routeResult.value = resp.data
    await nextTick()
    if (!mapInstance) mapInstance = await initMap(mapContainer.value)
    if (mapInstance) routePolyline = await drawRoute(mapInstance, routeResult.value?.waypoints, routePolyline)
    // 自动加载目的地匹配的包裹
    await fetchRoutePackages()
  } catch (e) {
    ElMessage.error('路径规划失败: ' + (e?.message || '网络错误'))
  }
  acoLoading.value = false
}

// ===== 发车 =====
const departSpeed = ref(20)
const departLoading = ref(false)
const vehicleRunning = ref(false)
const vehicleState = ref(null)
const departResult = ref(null)
const departPackages = ref([])
const departSelectedPackages = ref([])
const routePkgLoading = ref(false)
const routePackResult = ref(null)
const currentVehicleId = ref('')
const allVehicles = ref([])
const vehiclesSummary = ref({ total: 0, running: 0, idle: 0 })
const bindingSummary = ref(null)
let monitorTimer = null

async function fetchRoutePackages() {
  if (!routeResult.value?.path) return
  routePkgLoading.value = true; routePackResult.value = null
  try {
    const districts = routeResult.value.path.filter(c => c !== '南昌')
    // 并行：获取包裹列表 + 装箱优化
    const [pkgRes, packRes] = await Promise.all([
      request.get('/api/logistics/packages/available'),
      request.post('/api/logistics/pack', { destinations: districts, limit: 50 }),
    ])
    const all = pkgRes.data || []
    routePackResult.value = packRes.data

    // 装入成功的包裹追踪号
    const packedTns = new Set((routePackResult.value?.placed || []).map(p => p.tracking_number))
    // 装箱成功的优先显示，其余按分区匹配
    const packedList = all.filter(p => packedTns.has(p.tracking_number))
    const otherList = all.filter(p => !packedTns.has(p.tracking_number) && !p.is_bound &&
      selectedCities.value.some(c => (p.district || '').includes(c) || (p.city || '').includes(c)))
    departPackages.value = [...packedList, ...otherList]
    departSelectedPackages.value = packedList.filter(p => !p.is_bound).map(p => p.tracking_number)

    // 如果都没有，从 total_packages 兜底（pack API 返回的所有参与包裹）
    if (!departPackages.value.length && routePackResult.value?.total_packages?.length) {
      departPackages.value = routePackResult.value.total_packages
        .filter(p => selectedCities.value.some(c => (p.destination || '').includes(c)))
        .map(p => ({ tracking_number: p.tracking_number, district: p.destination, target_chute: p.district || '', is_bound: false }))
      departSelectedPackages.value = departPackages.value.map(p => p.tracking_number)
    }
  } catch { ElMessage.error('获取包裹+装箱失败') }
  routePkgLoading.value = false
}


// eslint-disable-next-line no-unused-vars
function selectAllPackages() {
  departSelectedPackages.value = departPackages.value.filter(p => !p.is_bound).map(p => p.tracking_number)
}
// eslint-disable-next-line no-unused-vars
function clearPackageSelection() {
  departSelectedPackages.value = []
}

// eslint-disable-next-line no-unused-vars
async function doDepart() {
  if (departSelectedPackages.value.length === 0) {
    ElMessage.warning('请先在包裹选择区选择至少1件包裹')
    return
  }
  if (!routeResult.value?.waypoints) { ElMessage.warning('请先执行路径规划'); return }
  departLoading.value = true
  try {
    // 自动分配车辆ID
    currentVehicleId.value = 'V-' + Date.now().toString(36).toUpperCase()
    const resp = await request.post('/api/logistics/depart', {
      tracking_numbers: departSelectedPackages.value,
      waypoints: routeResult.value.waypoints,
      speed_kmh: departSpeed.value,
      vehicle_id: currentVehicleId.value,
    })
    const d = resp.data
    const boundCount = d?.bound || 0
    departResult.value = { ...(d || {}), vehicle_id: currentVehicleId.value, message: resp.message || '已出发', origin: '南昌分拣中心' }
    ElMessage.success((resp.message || '已出发') + '，绑定 ' + boundCount + ' 件包裹，开始分区配送')
    vehicleRunning.value = true
    activeTab.value = 'monitor'
    await nextTick()
    startMonitor()
  } catch (e) {
    ElMessage.error('发车失败: ' + (e?.message || '请求错误'))
  }
  departLoading.value = false
}

async function startMonitor() {
  if (monitorTimer) clearInterval(monitorTimer)
  const update = async () => {
    // 获取所有车辆（独立刷新，不依赖发车操作）
    try {
      const vehicles = (await request.get('/api/logistics/vehicles')).data || []
      allVehicles.value = vehicles
      vehiclesSummary.value = { 
        total: vehicles.length, 
        running: vehicles.filter(v => v.status === 'running').length, 
        idle: vehicles.filter(v => v.status === 'idle').length 
      }
    } catch { /* ignore */ }
    // 获取绑定关系
    try {
      const rb = await request.get('/api/logistics/bindings')
      bindingSummary.value = rb.data
    } catch { /* ignore */ }

    if (!currentVehicleId.value || !vehicleRunning.value) return
    try {
      const resp = await request.get('/api/logistics/vehicle/' + currentVehicleId.value + '/status')
      vehicleState.value = resp.data
      const s = vehicleState.value; if (!s) return
      const L = await loadLeaflet()
      if (!monitorMapInstance) {
        monitorMapInstance = await initMap(monitorMap.value)
        if (routeResult.value?.waypoints) {
          monitorPolyline = await drawRoute(monitorMapInstance, routeResult.value.waypoints, monitorPolyline)
        }
      }
      if (monitorMapInstance && s.current_lat && s.current_lng) {
        if (vehicleMarker) monitorMapInstance.removeLayer(vehicleMarker)
        const icon = L.divIcon({ html: '<div style="font-size:24px">🚛</div>', className: 'vehicle-icon', iconSize: [32,32], iconAnchor: [16,16] })
        vehicleMarker = L.marker([s.current_lat, s.current_lng], { icon }).addTo(monitorMapInstance)
          .bindTooltip(`${s.progress_percent}% | ${formatETA(s.eta_minutes)}`, { permanent: true, direction: 'top' })
      }
      if (s.status === 'idle') {
        vehicleRunning.value = false
        ElMessage.success('车辆已完成南昌分区配送，进入空闲状态')
        if (monitorTimer) { clearInterval(monitorTimer); monitorTimer = null }
      }
    } catch { /* ignore */ }
  }
  update()
  monitorTimer = setInterval(update, 2000)
}

function selectVehicle(row) {
  vehicleState.value = row
  currentVehicleId.value = row.vehicle_id
  vehicleRunning.value = row.status === 'running'
}

function formatETA(minutes) {
  if (minutes <= 0) return '已到达'
  if (minutes < 60) return Math.round(minutes) + '分钟'
  const h = Math.floor(minutes / 60), m = Math.round(minutes % 60)
  return h + '时' + m + '分'
}

// ===== Leaflet加载（多CDN回退） =====
let leafletReady = null
function loadLeaflet() {
  if (leafletReady) return leafletReady
  leafletReady = new Promise((resolve, reject) => {
    if (window.L) return resolve(window.L)
    // CSS: bootcdn优先
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
    link.onerror = () => {
      const l2 = document.createElement('link'); l2.rel = 'stylesheet'
      l2.href = 'https://cdn.bootcdn.net/ajax/libs/leaflet/1.9.4/leaflet.css'
      document.head.appendChild(l2)
    }
    document.head.appendChild(link)
    // JS: 多源回退
    function tryLoad(urls, idx) {
      if (idx >= urls.length) return reject(new Error('Leaflet加载失败'))
      const s = document.createElement('script')
      s.src = urls[idx]
      s.onload = () => resolve(window.L)
      s.onerror = () => tryLoad(urls, idx + 1)
      document.head.appendChild(s)
    }
    tryLoad([
      'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
      'https://cdn.bootcdn.net/ajax/libs/leaflet/1.9.4/leaflet.js',
    ], 0)
  })
  return leafletReady
}

// ===== 生命周期 =====
async function fetchCities() {
  try {
    const resp = await request.get('/api/logistics/cities')
    cityList.value = resp.data?.districts || []
  } catch { /* ignore */ }
}

onMounted(fetchCities)

let vehiclesPollTimer = null
watch(activeTab, async (tab) => {
  await nextTick()
  if (tab === 'route' && !mapInstance && mapContainer.value) {
    mapInstance = await initMap(mapContainer.value)
  }
  if (tab === 'monitor') {
    if (!monitorMapInstance && monitorMap.value) monitorMapInstance = await initMap(monitorMap.value)
    // 启动车辆列表自动刷新（3秒轮询）
    const refreshVehicles = async () => {
      try {
        const r = await request.get('/api/logistics/vehicles')
        const vlist = (r.data || r).vehicles || (r.data || [])
        allVehicles.value = Array.isArray(vlist) ? vlist : (r.data || [])
        vehiclesSummary.value = { 
          total: allVehicles.value.length, 
          running: allVehicles.value.filter(v => v.status === 'running').length, 
          idle: allVehicles.value.filter(v => v.status === 'idle').length 
        }
      } catch { /* ignore */ }
    }
    refreshVehicles()
    if (vehiclesPollTimer) clearInterval(vehiclesPollTimer)
    vehiclesPollTimer = setInterval(refreshVehicles, 3000)
  } else {
    if (vehiclesPollTimer) { clearInterval(vehiclesPollTimer); vehiclesPollTimer = null }
  }
})

onUnmounted(() => { if (monitorTimer) clearInterval(monitorTimer); if (vehiclesPollTimer) clearInterval(vehiclesPollTimer) })

</script>

<style scoped>
.page { padding: 20px; }
h2 { margin-bottom: 16px; color: #2c3e50; }

/* 2D装箱可视化 */
.pack-viz { display: flex; gap: 16px; }
.viz-section { flex: 1; }
.viz-label { font-size: 13px; font-weight: 600; color: #606266; margin-bottom: 8px; text-align: center; }
.viz-canvas { width: 100%; height: auto; background: #1a1a2e; border-radius: 10px; border: 2px solid #409EFF; }

/* 地图 */
.map-canvas { width: 100%; height: 500px; border-radius: 12px; border: 2px solid #e0e0e0; z-index: 1; }

/* 统计 */
.stat-grid { display: flex; gap: 8px; }
.stat-item { flex: 1; text-align: center; background: #f5f7fa; border-radius: 8px; padding: 12px 8px; }
.stat-item .val { display: block; font-size: 24px; font-weight: 800; color: #409EFF; }
.stat-item .lbl { font-size: 11px; color: #909399; margin-top: 4px; }

.route-stats { display: flex; gap: 20px; font-size: 14px; color: #606266; }

/* 车辆面板 */
.vehicle-panel { text-align: center; }
.v-id { font-size: 16px; font-weight: bold; margin-bottom: 12px; color: #409EFF; }
.v-stats { margin-top: 16px; }
.v-stats .row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; }

/* 监控摘要卡片 */
.monitor-stat { text-align: center; padding: 8px; border-radius: 10px !important; color: #fff; }
.monitor-stat.running { background: linear-gradient(135deg,#409EFF,#337ECC); }
.monitor-stat.idle { background: linear-gradient(135deg,#67C23A,#529B2E); }
.monitor-stat.total { background: linear-gradient(135deg,#909399,#606266); }
.monitor-stat.stopped { background: linear-gradient(135deg,#E6A23C,#CF9236); }
.mnum { font-size: 26px; font-weight: 800; }
.mlab { font-size: 12px; opacity: .85; margin-top: 4px; }

/* 绑定关系 */
.bind-bar { display: flex; gap: 8px; }
.bind-stat { flex: 1; text-align: center; background: #f5f7fa; border-radius: 8px; padding: 10px; }
.bind-stat .b-num { display: block; font-size: 22px; font-weight: 800; color: #303133; }
.bind-stat .b-lab { font-size: 11px; color: #909399; margin-top: 2px; }
</style>
