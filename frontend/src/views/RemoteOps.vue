<template>
    <div class="page">
      <h2>🖥️ 远程运维与多中心协同 (模块11+12)</h2>

      <el-tabs v-model="tab">
        <!-- ====== 设备监控 ====== -->
        <el-tab-pane label="设备监控" name="devices">
          <div class="stats-row">
            <div class="stat-card green"><div class="num">{{ deviceSummary.running }}</div><div class="lab">✅ 运行中</div></div>
            <div class="stat-card orange"><div class="num">{{ deviceSummary.warning }}</div><div class="lab">⚠️ 告警</div></div>
            <div class="stat-card gray"><div class="num">{{ deviceSummary.idle }}</div><div class="lab">⏸️ 空闲</div></div>
            <div class="stat-card blue"><div class="num">{{ deviceSummary.total }}</div><div class="lab">📊 总数</div></div>
          </div>
          <el-row :gutter="12" style="margin-top:12px">
            <el-col :span="4" v-for="d in devices" :key="d.id" style="margin-bottom:12px">
              <el-card shadow="hover" :body-style="{padding:'14px'}">
                <div style="text-align:center">
                  <div style="font-size:28px">{{ d.code === 'CH-006' ? '🔬' : '🛤️' }}</div>
                  <div style="font-weight:bold;margin:6px 0;font-size:13px">{{ d.name }}</div>
                  <el-tag :type="d.status==='running'?'success':d.status==='warning'?'warning':'info'" size="small">{{ d.status === 'running' ? '运行中' : d.status === 'warning' ? '高负载' : '空闲' }}</el-tag>
                  <div style="margin-top:8px">
                    <el-progress :percentage="d.load" :color="d.load>80?'#F56C6C':'#409EFF'" :stroke-width="6" />
                    <div style="font-size:11px;color:#999;margin-top:4px">负载 {{ d.load }}% | {{ d.packages }}件</div>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>
          <el-alert title="数据来源" type="info" :closable="false" style="margin-top:12px">
            设备状态来自数据库 sorting_chutes 表，容量为预设值，负载 = 当前包裹数/容量×100%。非随机生成。
          </el-alert>
        </el-tab-pane>

        <!-- ====== 多中心协同 ====== -->
        <el-tab-pane label="多中心协同" name="centers">
          <div class="stats-row">
            <div class="stat-card blue"><div class="num">{{ centers.length }}</div><div class="lab">🏢 中心数</div></div>
            <div class="stat-card green"><div class="num">{{ centers.filter(c=>c.status==='active').length }}</div><div class="lab">✅ 活跃</div></div>
            <div class="stat-card orange"><div class="num">{{ centers.filter(c=>c.load>0.5).length }}</div><div class="lab">⚠️ 高负载</div></div>
          </div>
          <el-row :gutter="12" style="margin-top:12px">
            <el-col :span="6" v-for="c in centers" :key="c.id" style="margin-bottom:12px">
              <el-card shadow="hover" :body-style="{padding:'14px'}" :class="{'high-load':c.load>0.5}">
                <div style="font-weight:bold;font-size:14px">{{ c.name }}</div>
                <div style="font-size:12px;color:#909399;margin:4px 0">{{ c.location }}</div>
                <el-progress :percentage="Math.round(c.load*100)" :color="c.load>0.5?'#F56C6C':'#409EFF'" :stroke-width="10" />
                <div style="font-size:11px;color:#909399;margin-top:4px">
                  容量: {{ c.capacity }}件/时 | 负载: {{ (c.load*100).toFixed(0) }}%
                </div>
              </el-card>
            </el-col>
          </el-row>

          <!-- 操作区 -->
          <el-row :gutter="12" style="margin-top:12px">
            <el-col :span="12">
              <el-card header="🔄 跨中心调度">
                <p style="font-size:13px;color:#666;margin-bottom:8px">将新任务分配给当前负载最低的活跃中心</p>
                <el-button type="primary" @click="doSchedule" :loading="schedLoading">执行调度</el-button>
                <div v-if="schedResult" class="result-panel success">
                  <div class="result-icon">✅</div>
                  <div class="result-text">
                    <div>任务已分配至 <b>{{ schedResult.assigned_center }}</b></div>
                    <div class="result-reason">{{ schedResult.reason }}</div>
                  </div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card header="🚨 故障转移">
                <p style="font-size:13px;color:#666;margin-bottom:8px">模拟某中心故障，自动转移至邻近中心</p>
                <div style="display:flex;gap:8px;margin-bottom:8px">
                  <el-select v-model="failCenter" placeholder="选择故障中心" size="small" style="width:180px">
                    <el-option v-for="c in centers" :key="c.id" :label="c.name" :value="c.id" />
                  </el-select>
                  <el-button type="danger" @click="doFailover" :loading="failLoading">执行转移</el-button>
                </div>
                <div v-if="failResult" class="result-panel danger">
                  <div class="result-icon">🔄</div>
                  <div class="result-text">
                    <div><b>{{ failResult.failed_center }}</b> 故障</div>
                    <div class="result-reason">转移至：
                      <el-tag v-for="t in failResult.transfer_to" :key="t.id" size="small" type="warning" style="margin:2px">{{ t.name }}</el-tag>
                    </div>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>
          <el-alert title="数据来源" type="info" :closable="false" style="margin-top:12px">
            分拣中心数据 = sorting_chutes 表。负载 = 包裹数/容量，容量来自数据库预设值，非随机生成。
          </el-alert>
        </el-tab-pane>

        <!-- ====== 系统升级 ====== -->
        <el-tab-pane label="系统升级" name="upgrade">
          <el-card>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="当前版本">{{ upgrade?.current_version || '-' }}</el-descriptions-item>
              <el-descriptions-item label="最新版本">{{ upgrade?.latest_version || '-' }}</el-descriptions-item>
              <el-descriptions-item label="更新可用">
                <el-tag :type="upgrade?.upgrade_available?'warning':'success'">{{ upgrade?.upgrade_available?'是':'否' }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="更新内容">{{ upgrade?.changelog || '-' }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const tab = ref('devices')
const devices = ref([])
const deviceStatus = ref({})
const centers = ref([])
const upgrade = ref({})

const deviceSummary = computed(() => ({
  total: devices.value.length,
  running: devices.value.filter(d => d.status === 'running').length,
  warning: devices.value.filter(d => d.status === 'warning').length,
  idle: devices.value.filter(d => d.status !== 'running' && d.status !== 'warning').length,
}))

const schedLoading = ref(false)
const schedResult = ref(null)
const failLoading = ref(false)
const failResult = ref(null)
const failCenter = ref(1)

async function fetchDevices() {
  try { const r = await request.get('/api/ops/devices'); devices.value = r.data.devices || []; deviceStatus.value = r.data.summary || {} } catch { /* ignore */ }
}
async function fetchCenters() {
  try { const r = await request.get('/api/ops/centers'); centers.value = r.data || []; if (centers.value.length) failCenter.value = centers.value[0].id } catch { /* ignore */ }
}
async function fetchUpgrade() {
  try { const r = await request.get('/api/ops/upgrade'); upgrade.value = r.data || {} } catch { /* ignore */ }
}

async function doSchedule() {
  schedLoading.value = true; schedResult.value = null
  try {
    const r = await request.post('/api/ops/centers/schedule', { package_count: 500 })
    schedResult.value = r.data
  } catch { ElMessage.error('调度失败') }
  schedLoading.value = false
}

async function doFailover() {
  failLoading.value = true; failResult.value = null
  try {
    const r = await request.post(`/api/ops/centers/failover/${failCenter.value}`)
    failResult.value = r.data
  } catch { ElMessage.error('故障转移失败') }
  failLoading.value = false
}

onMounted(() => { fetchDevices(); fetchCenters(); fetchUpgrade() })
</script>

<style scoped>
.page { padding: 20px; background: #f0f2f5; min-height: 100vh; }
h2 { margin-bottom: 16px; color: #2c3e50; }

.stats-row { display: flex; gap: 12px; }
.stat-card { flex: 1; border-radius: 12px; padding: 16px; text-align: center; color: #fff; }
.stat-card .num { font-size: 26px; font-weight: 800; }
.stat-card .lab { font-size: 12px; opacity: .85; margin-top: 4px; }
.stat-card.green { background: linear-gradient(135deg,#43e97b,#38f9d7); color: #1a3a1a; }
.stat-card.orange { background: linear-gradient(135deg,#fa8231,#f7b731); }
.stat-card.blue { background: linear-gradient(135deg,#4facfe,#00f2fe); color: #1a3a1a; }
.stat-card.gray { background: linear-gradient(135deg,#a0a0a0,#c0c0c0); }

.high-load { border-left: 3px solid #F56C6C; }

.result-panel { display: flex; gap: 12px; align-items: center; margin-top: 12px; padding: 14px; border-radius: 10px; }
.result-panel.success { background: #f0f9eb; border: 1px solid #c2e7b0; }
.result-panel.danger { background: #fef0f0; border: 1px solid #fbc4c4; }
.result-icon { font-size: 28px; }
.result-text { font-size: 14px; }
.result-reason { font-size: 12px; color: #909399; margin-top: 4px; }
</style>
