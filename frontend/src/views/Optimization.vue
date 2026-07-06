<template>
  <div class="page">
    <h2>🚚 路径优化与装载规划 (南昌分区配送)</h2>

    <el-row :gutter="16">
      <!-- ===== 路径规划（地图） ===== -->
      <el-col :span="12">
        <el-card header="🐜 蚁群算法 - 南昌分区路径规划">
          <div ref="mapContainer" class="map-canvas"></div>
          <div style="margin-top:12px">
            <el-select v-model="selectedCities" multiple filterable placeholder="选择南昌分区" style="width:100%">
              <el-option v-for="c in nanchangDistricts" :key="c.name" :label="c.name" :value="c.name" />
            </el-select>
          </div>
          <div style="margin-top:8px;display:flex;gap:8px;align-items:center">
            <el-input-number v-model="acoIters" :min="20" :max="200" :step="10" size="small" style="width:120px" />
            <span style="font-size:12px;color:#999">迭代次数</span>
            <el-button type="primary" @click="runACO" :loading="acoLoading" size="small">🐜 运行蚁群算法</el-button>
          </div>
          <div v-if="acoResult" style="margin-top:12px;display:flex;gap:16px;font-size:14px">
            <span>📍 起点：<b style="color:#409EFF">南昌分拣中心</b></span>
            <span>🛣️ 总里程：<b>{{ acoResult.total_distance_km }} km</b></span>
            <span>🔁 迭代：<b>{{ acoResult.iterations }}</b> 次</span>
          </div>
          <div v-if="acoResult" style="margin-top:4px">
            <el-tag v-for="(city,i) in acoResult.path" :key="city"
              :type="i===0?'success':i===acoResult.path.length-1?'danger':''"
              size="small" style="margin:2px">
              {{ i+1 }}.{{ city }}
            </el-tag>
          </div>
        </el-card>
      </el-col>

      <!-- ===== GA 装箱优化 ===== -->
      <el-col :span="6">
        <el-card header="🧬 遗传算法 - 车厢装载优化">
          <el-form label-width="70px" size="small" style="margin-bottom:8px">
            <el-form-item label="包裹数"><el-input-number v-model="gaParams.count" :min="5" :max="30" size="small" /></el-form-item>
            <el-form-item label="车载量"><el-input-number v-model="gaParams.capacity" :min="2" :max="20" size="small" /></el-form-item>
          </el-form>
          <el-button type="primary" @click="runGA" :loading="gaLoading" size="small" style="width:100%">运行 GA 装箱优化</el-button>
          <div v-if="gaResult" style="margin-top:12px">
            <p style="font-size:13px">📦 车厢：<b>{{ gaResult.vehicle || '240×120×200cm' }}</b></p>
            <p style="font-size:13px">📊 填充率：<b :style="{color:gaResult.fill_rate>=95?'#67C23A':'#E6A23C'}">{{ gaResult.fill_rate || gaResult.load_rate_percent }}%</b></p>
            <p v-if="gaResult.filled_packages !== undefined" style="font-size:13px">✅ 装入：<b>{{ gaResult.filled_packages }}/{{ gaResult.total_packages }}</b> 件</p>
          </div>
        </el-card>
      </el-col>

      <!-- ===== 3D装箱 ===== -->
      <el-col :span="6">
        <el-card header="📦 3D装箱规划">
          <el-form label-width="70px" size="small" style="margin-bottom:8px">
            <el-form-item label="包裹数"><el-input-number v-model="packParams.count" :min="3" :max="12" size="small" /></el-form-item>
          </el-form>
          <el-button type="primary" @click="runPack" :loading="packLoading" size="small" style="width:100%">运行装箱优化</el-button>
          <div v-if="packResult" style="margin-top:12px">
            <p style="font-size:13px">🚛 车厢：<b>{{ packResult.vehicle || '240×120×200cm' }}</b></p>
            <p style="font-size:13px">📦 包裹：<b>{{ packResult.total_packages }}</b> | 合格：<b>{{ packResult.valid_packages }}</b></p>
            <p v-if="packResult.oversized?.length" style="color:#F56C6C;font-size:12px">⚠️ {{ packResult.oversized.length }}件超车厢尺寸</p>
            <p style="font-size:13px">📐 填充率：<b :style="{color:packResult.fill_rate>=95?'#67C23A':'#E6A23C'}">{{ packResult.fill_rate }}%</b></p>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import request from '@/api/request'

// ===== 南昌分区数据 =====
const nanchangDistricts = [
  { name: '东湖区', lng: 115.8891, lat: 28.6850 },
  { name: '西湖区', lng: 115.8777, lat: 28.6571 },
  { name: '青云谱区', lng: 115.9258, lat: 28.6214 },
  { name: '青山湖区', lng: 115.9620, lat: 28.6820 },
  { name: '新建区', lng: 115.8150, lat: 28.6920 },
  { name: '红谷滩区', lng: 115.8582, lat: 28.6982 },
]

// ===== 参数 =====
const gaResult = ref(null); const acoResult = ref(null); const packResult = ref(null)
const gaLoading = ref(false); const acoLoading = ref(false); const packLoading = ref(false)
const gaParams = reactive({ count: 8, capacity: 5 })
const acoIters = ref(100)
const packParams = reactive({ count: 5 })
const selectedCities = ref(['东湖区', '西湖区', '青云谱区', '青山湖区', '红谷滩区'])

// ===== 地图 =====
const mapContainer = ref(null)
const GAODE_URL = 'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}'
let mapInstance = null, routePolyline = null

// Leaflet 加载
let leafletReady = null
function loadLeaflet() {
  if (leafletReady) return leafletReady
  leafletReady = new Promise((resolve, reject) => {
    if (window.L) return resolve(window.L)
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
    link.onerror = () => {
      const l2 = document.createElement('link'); l2.rel = 'stylesheet'
      l2.href = 'https://cdn.bootcdn.net/ajax/libs/leaflet/1.9.4/leaflet.css'
      document.head.appendChild(l2)
    }
    document.head.appendChild(link)
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

async function initMap(container) {
  if (!container) return null
  const L = await loadLeaflet()
  const map = L.map(container, { attributionControl: false }).setView([28.68, 115.86], 12)
  L.tileLayer(GAODE_URL, { maxZoom: 18, subdomains: ['1', '2', '3', '4'] }).addTo(map)
  return map
}

async function drawRoute(map, waypoints) {
  const L = await loadLeaflet()
  if (!map || !waypoints?.length) return
  if (routePolyline) { map.removeLayer(routePolyline); routePolyline = null }
  map.eachLayer(layer => {
    if (layer instanceof L.Marker || layer instanceof L.CircleMarker) map.removeLayer(layer)
  })
  const coords = waypoints.map(w => [w.lat, w.lng])
  routePolyline = L.polyline(coords, { color: '#409EFF', weight: 5, opacity: 0.9 }).addTo(map)
  waypoints.forEach((wp, i) => {
    const color = i === 0 ? '#67C23A' : i === waypoints.length - 1 ? '#F56C6C' : '#409EFF'
    L.circleMarker([wp.lat, wp.lng], {
      radius: 8, fillColor: color, color: '#fff', weight: 2, fillOpacity: 1
    }).bindTooltip(`${i + 1}. ${wp.name}`, { permanent: false, direction: 'top' }).addTo(map)
  })
  map.fitBounds(coords, { padding: [30, 30] })
}

// ===== API 调用 =====
async function runGA() {
  gaLoading.value = true
  try {
    const r = await request.post('/api/optimization/ga-load', { count: gaParams.count, capacity: gaParams.capacity })
    gaResult.value = r.data
  } catch { /* ignore */ }
  gaLoading.value = false
}

async function runACO() {
  if (selectedCities.value.length < 2) { return }
  acoLoading.value = true
  try {
    const cities = ['南昌', ...selectedCities.value.filter(c =>
      nanchangDistricts.find(d => d.name === c)
    )]
    const resp = await request.post('/api/logistics/route-plan', {
      cities: cities,
      iterations: acoIters.value
    })
    acoResult.value = resp.data.data || resp.data
    await nextTick()
    if (!mapInstance) mapInstance = await initMap(mapContainer.value)
    if (mapInstance && acoResult.value?.waypoints) {
      await drawRoute(mapInstance, acoResult.value.waypoints)
    }
  } catch (e) {
    console.error('路径规划失败:', e)
  }
  acoLoading.value = false
}

async function runPack() {
  packLoading.value = true
  try {
    const r = await request.post('/api/optimization/pack-bin', { count: packParams.count, container: [120, 80, 60] })
    packResult.value = r.data
  } catch { /* ignore */ }
  packLoading.value = false
}

// ===== 生命周期 =====
onMounted(async () => {
  await nextTick()
  if (mapContainer.value) {
    mapInstance = await initMap(mapContainer.value)
  }
})

onUnmounted(() => {
  if (mapInstance) { mapInstance.remove(); mapInstance = null }
})
</script>

<style scoped>
.page { padding: 20px; }
h2 { margin-bottom: 16px; color: #2c3e50; }

.map-canvas { width: 100%; height: 400px; border-radius: 12px; border: 2px solid #e0e0e0; z-index: 1; }
</style>
