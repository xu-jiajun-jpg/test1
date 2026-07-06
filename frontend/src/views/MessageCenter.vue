<template>
  <div class="msg-center">
    <!-- 顶部标题栏 -->
    <div class="msg-header">
      <div class="msg-header-left">
        <h2>📬 消息中心</h2>
        <span class="role-badge" :class="role">{{ role === 'admin' ? '管理员' : '操作员' }}</span>
      </div>
      <div class="msg-header-actions">
        <el-tag v-if="unreadCount && !sentOnly" type="danger" effect="dark" size="large">{{ unreadCount }} 条未读</el-tag>
        <el-tag v-else-if="!sentOnly" type="success" effect="dark" size="large">全部已读</el-tag>
        <el-button v-if="!sentOnly" size="small" @click="markAllRead" :loading="markingAll" :disabled="!unreadCount">✅ 全部已读</el-button>
        <el-button size="small" type="primary" @click="openCompose">
          {{ role === 'admin' ? '✏️ 发送指令' : '⚠️ 上报异常' }}
        </el-button>
        <el-button size="small" @click="fetchMessages" :loading="loading">🔄 刷新</el-button>
      </div>
    </div>

    <!-- 收件箱/发件箱标签 -->
    <div class="msg-tabs">
      <div
        class="msg-tab"
        :class="{ active: !sentOnly }"
        @click="switchTab(false)"
      >📥 收件箱</div>
      <div
        class="msg-tab"
        :class="{ active: sentOnly }"
        @click="switchTab(true)"
      >📤 发件箱</div>
    </div>

    <!-- 筛选栏 -->
    <div class="msg-filter-bar">
      <el-radio-group v-if="!sentOnly" v-model="filter" size="small" @change="fetchMessages">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="unread">未读</el-radio-button>
      </el-radio-group>
      <div class="filter-right">
        <el-select v-model="catFilter" size="small" placeholder="类别" clearable style="width:130px" @change="fetchMessages">
          <el-option label="⚠️ 员工报错" value="error_report" />
          <el-option label="📋 管理指令" value="admin_directive" />
          <el-option label="📦 任务派发" value="task_dispatched" />
          <el-option label="📤 任务完成" value="task_completed" />
          <el-option label="⏰ 超时滞留" value="task_stale" />
          <el-option label="⛔ 任务拒收" value="task_rejected" />
          <el-option label="⚠️ 异常上报" value="exception_raised" />
          <el-option label="🔔 系统通知" value="system" />
        </el-select>
        <el-select v-model="levelFilter" size="small" placeholder="级别" clearable style="width:90px" @change="fetchMessages">
          <el-option label="🔴 异常" value="error" />
          <el-option label="🟠 警告" value="warning" />
          <el-option label="🔵 信息" value="info" />
          <el-option label="🟢 成功" value="success" />
        </el-select>
        <el-input v-model="searchText" size="small" placeholder="搜索..." clearable style="width:150px" />
      </div>
    </div>

    <!-- 消息列表 -->
    <div class="msg-list-wrapper">
      <el-card v-loading="loading" shadow="never" class="msg-card">
        <div v-if="displayMessages.length" class="msg-list">
          <div
            v-for="m in displayMessages"
            :key="m.message_id"
            class="msg-item"
            :class="{ 'msg-unread': !m.is_read }"
            @click="toggleRead(m)"
          >
            <div class="msg-avatar" :class="'avatar-' + m.level">
              <span>{{ levelEmoji(m.level) }}</span>
            </div>
            <div class="msg-body">
              <div class="msg-top">
                <span class="msg-title" :class="'title-' + m.level">{{ m.title }}</span>
                <span class="msg-time">{{ fmtTime(m.created_at) }}</span>
              </div>
              <div class="msg-content" v-if="m.content">{{ m.content }}</div>
              <div class="msg-tags">
                <!-- 发送者 -->
                <el-tag v-if="m.from_name" size="small" effect="dark"
                  :type="m.from_role === 'operator' ? 'warning' : 'primary'">
                  {{ m.from_role === 'admin' ? '👤 管理员' : '🔧' }} {{ m.from_name }}
                </el-tag>
                <!-- 目标标记 -->
                <el-tag v-if="m.target_role === 'operator' && role === 'admin'" size="small" type="success" effect="plain">
                  → {{ m.target_operator_id ? '指定操作员' : '全体操作员' }}
                </el-tag>
                <el-tag v-if="m.related_chute" size="small" effect="plain">{{ m.related_chute }}</el-tag>
                <el-tag v-if="m.related_tracking" size="small" type="info" effect="plain">{{ m.related_tracking }}</el-tag>
                <!-- 类别 -->
                <el-tag size="small" effect="plain" :type="catTagType(m.category)">{{ catLabel(m.category) }}</el-tag>
                <span v-if="!m.is_read" class="unread-dot"></span>
              </div>
            </div>
            <el-button size="small" :type="m.is_read ? 'info' : 'primary'" text @click.stop="toggleRead(m)" class="read-btn">
              {{ m.is_read ? '已读' : '标记已读' }}
            </el-button>
          </div>
        </div>
        <el-empty v-else description="暂无消息" :image-size="80" />
      </el-card>
    </div>

    <div class="msg-pagination" v-if="total > pageSize">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total"
        layout="prev, pager, next" small @current-change="fetchMessages" />
    </div>

    <!-- ===== 管理员发送指令弹窗 ===== -->
    <el-dialog v-if="role === 'admin'" v-model="showCompose" title="✏️ 发送指令" width="520px" :close-on-click-modal="false" destroy-on-close>
      <el-form :model="cf" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="cf.title" placeholder="指令标题" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="cf.content" type="textarea" :rows="3" placeholder="指令详细内容" maxlength="1000" show-word-limit />
        </el-form-item>
        <el-form-item label="级别">
          <el-radio-group v-model="cf.level">
            <el-radio value="info">🔵 通知</el-radio>
            <el-radio value="warning">🟠 警告</el-radio>
            <el-radio value="error">🔴 重要</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="发送给" required>
          <el-radio-group v-model="cf.target_type" @change="onTargetTypeChange" style="margin-bottom:8px">
            <el-radio value="all">全体操作员</el-radio>
            <el-radio value="chute">按分拣口</el-radio>
            <el-radio value="operator">指定操作员</el-radio>
          </el-radio-group>
          <el-select v-if="cf.target_type === 'chute'" v-model="cf.target_chute" placeholder="选择分拣口" style="width:100%">
            <el-option v-for="ch in chuteList" :key="ch" :label="ch" :value="ch" />
          </el-select>
          <el-select v-if="cf.target_type === 'operator'" v-model="cf.target_operator_id" placeholder="选择操作员" style="width:100%" filterable>
            <el-option v-for="op in operatorList" :key="op.operator_id" :label="`${op.name} (${op.shift}班)`" :value="op.operator_id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCompose = false">取消</el-button>
        <el-button type="primary" @click="doSend" :loading="sending">发送</el-button>
      </template>
    </el-dialog>

    <!-- ===== 员工报错弹窗（简化版） ===== -->
    <el-dialog v-if="role === 'operator'" v-model="showCompose" title="⚠️ 上报异常" width="480px" :close-on-click-modal="false" destroy-on-close>
      <div class="op-report-notice">
        📌 此消息将直接发送给管理员，管理员会尽快协调处理
      </div>
      <el-form :model="cf" label-width="80px" style="margin-top:12px">
        <el-form-item label="异常类型" required>
          <el-select v-model="cf.exception_type" placeholder="选择异常类型" style="width:100%">
            <el-option label="📦 包裹分拣错误" value="分拣错误" />
            <el-option label="🔍 条码无法识别" value="条码损坏" />
            <el-option label="🗺️ 分区不匹配" value="分区错误" />
            <el-option label="📐 包裹超尺寸" value="超尺寸" />
            <el-option label="⚠️ 设备故障" value="设备故障" />
            <el-option label="🔧 其他异常" value="其他异常" />
          </el-select>
        </el-form-item>
        <el-form-item label="运单号">
          <el-input v-model="cf.related_tracking" placeholder="关联运单号（可选）" maxlength="64" />
        </el-form-item>
        <el-form-item label="分拣口">
          <el-input v-model="cf.target_chute" placeholder="所在分拣口（可选）" maxlength="50" />
        </el-form-item>
        <el-form-item label="严重程度" required>
          <el-radio-group v-model="cf.level">
            <el-radio value="warning">🟠 一般</el-radio>
            <el-radio value="error">🔴 紧急</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="详细描述">
          <el-input v-model="cf.content" type="textarea" :rows="3" placeholder="请描述具体异常情况..." maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCompose = false">取消</el-button>
        <el-button type="danger" @click="doSend" :loading="sending">提交报错</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const route = useRoute()
const authStore = useAuthStore()
const role = computed(() => route.path.startsWith('/operator') ? 'operator' : 'admin')

const messages = ref([])
const unreadCount = ref(0)
const loading = ref(false)
const markingAll = ref(false)
const sending = ref(false)
const filter = ref('all')
const levelFilter = ref('')
const catFilter = ref('')
const searchText = ref('')
const showCompose = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const sentOnly = ref(false)  // 收件箱/发件箱切换

const operatorList = ref([])
const chuteList = ref([])

const cf = ref({
  title: '', content: '', level: 'info',
  target_type: 'all', target_operator_id: null, target_chute: '',
  related_tracking: '', exception_type: '分拣错误',
})

let wsPollTimer = null

function levelEmoji(l) { return { error:'🔴', warning:'🟠', info:'🔵', success:'🟢' }[l] || '📌' }
function catLabel(c) {
  return { error_report:'⚠️ 员工报错', admin_directive:'📋 管理指令', system:'🔔 系统通知',
    user_message:'💬 消息', task_handled:'📤 分拣处理', exception_raised:'⚠️ 异常上报',
    task_dispatched:'📦 任务派发', task_accepted:'✅ 任务接收', task_rejected:'⛔ 任务拒收',
    task_completed:'📤 任务完成', task_verified:'✅ 已核验', task_stale:'⏰ 超时滞留',
    task_urged:'🔔 管理员催办' }[c] || c
}
function catTagType(c) {
  if (!c) return 'info'
  if (c === 'error_report' || c === 'task_rejected' || c === 'exception_raised') return 'danger'
  if (c === 'admin_directive' || c === 'task_dispatched') return 'primary'
  if (c === 'task_completed' || c === 'task_verified') return 'success'
  if (c === 'task_stale' || c === 'task_urged') return 'warning'
  if (c === 'system') return 'info'
  return ''
}

function switchTab(isSent) {
  sentOnly.value = isSent
  filter.value = 'all'
  page.value = 1
  fetchMessages()
}
function fmtTime(t) {
  if (!t) return ''
  const d = new Date(t); const now = new Date(); const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff/60000)+'分钟前'
  if (diff < 86400000) return Math.floor(diff/3600000)+'小时前'
  return d.toLocaleString('zh-CN', {month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'})
}

const displayMessages = computed(() => {
  let list = messages.value
  if (levelFilter.value) list = list.filter(m => m.level === levelFilter.value)
  if (catFilter.value) list = list.filter(m => m.category === catFilter.value)
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(m =>
      (m.title||'').toLowerCase().includes(q) ||
      (m.content||'').toLowerCase().includes(q) ||
      (m.from_name||'').toLowerCase().includes(q) ||
      (m.related_tracking||'').toLowerCase().includes(q)
    )
  }
  return list
})

async function fetchMessages() {
  loading.value = true
  try {
    const params = { role: role.value, page: page.value, page_size: pageSize.value }
    if (sentOnly.value) params.sent_only = true
    if (!sentOnly.value && filter.value === 'unread') params.unread_only = true
    if (catFilter.value) params.category = catFilter.value
    // 操作员侧传递分拣口上下文用于隔离过滤
    if (role.value === 'operator') {
      const user = authStore.user
      if (user?.operator_id) params.operator_id = user.operator_id
      if (user?.chute_codes?.length) params.chute_codes = user.chute_codes.join(',')
    }
    const res = await request.get('/api/messages', { params })
    const d = res.data || {}
    messages.value = d.items || []
    total.value = d.total || 0
    unreadCount.value = d.unread_count || 0
  } catch { /* ignore */ }
  loading.value = false
}

async function toggleRead(m) {
  if (m.is_read) return
  try {
    const params = { role: role.value }
    if (role.value === 'operator') {
      const user = authStore.user
      if (user?.operator_id) params.operator_id = user.operator_id
      if (user?.chute_codes?.length) params.chute_codes = user.chute_codes.join(',')
    }
    await request.put('/api/messages/read', { message_ids: [m.message_id] }, { params })
    m.is_read = true; unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch (e) { ElMessage.error('操作失败') }
}

async function markAllRead() {
  markingAll.value = true
  try {
    const params = { role: role.value }
    if (role.value === 'operator') {
      const user = authStore.user
      if (user?.operator_id) params.operator_id = user.operator_id
      if (user?.chute_codes?.length) params.chute_codes = user.chute_codes.join(',')
    }
    const res = await request.put('/api/messages/read', { mark_all: true }, { params })
    ElMessage.success(res.message || '全部已读')
    // 立即乐观更新，避免轮询闪烁
    messages.value.forEach(m => { m.is_read = true })
    unreadCount.value = 0
    // 再从服务器拉取确认同步
    await fetchMessages()
  } catch (e) {
    ElMessage.error('操作失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
  markingAll.value = false
}

async function openCompose() {
  if (role.value === 'admin') {
    try { const r = await request.get('/api/messages/targets')
      operatorList.value = r.data?.operators || []
      chuteList.value = r.data?.chutes || []
    } catch { /* */ }
  }
  cf.value = {
    title: '', content: '', level: 'info',
    target_type: 'all', target_operator_id: null, target_chute: '',
    related_tracking: '', exception_type: '分拣错误',
  }
  showCompose.value = true
}

function onTargetTypeChange() {
  cf.value.target_operator_id = null
  cf.value.target_chute = ''
}

async function doSend() {
  // 员工端校验
  if (role.value === 'operator') {
    if (!cf.value.exception_type) { ElMessage.warning('请选择异常类型'); return }
    cf.value.title = cf.value.exception_type
    cf.value.target_type = 'all'
  }
  if (!cf.value.title.trim()) { ElMessage.warning('请输入标题'); return }
  sending.value = true
  try {
    const payload = {
      title: cf.value.title.trim(),
      content: cf.value.content.trim(),
      level: cf.value.level,
      target_type: cf.value.target_type || 'all',
      target_operator_id: cf.value.target_operator_id || null,
      target_chute: cf.value.target_chute || null,
      related_tracking: cf.value.related_tracking || null,
    }
    const res = await request.post('/api/messages/send', payload)
    ElMessage.success(res.message || '发送成功')
    showCompose.value = false
    page.value = 1
    filter.value = 'all'
    await fetchMessages()
  } catch { ElMessage.error('发送失败') }
  sending.value = false
}

onMounted(() => {
  fetchMessages()
  wsPollTimer = setInterval(() => {
    if (sentOnly.value) return  // 发件箱不轮询未读数
    const params = { role: role.value }
    if (role.value === 'operator') {
      const user = authStore.user
      if (user?.operator_id) params.operator_id = user.operator_id
      if (user?.chute_codes?.length) params.chute_codes = user.chute_codes.join(',')
    }
    request.get('/api/messages/unread-count', { params }).then(res => {
      unreadCount.value = res.data?.unread_count || 0
    }).catch(()=>{})
  }, 8000)
})
onUnmounted(() => { if (wsPollTimer) clearInterval(wsPollTimer) })
</script>

<style scoped>
.msg-center { padding: 20px; max-width: 960px; margin: 0 auto; height: calc(100vh - 100px); display: flex; flex-direction: column; }
.msg-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 8px; }
.msg-header-left { display: flex; align-items: center; gap: 10px; }
.msg-header-left h2 { margin: 0; color: #1a1a2e; font-size: 22px; }
.role-badge { font-size: 12px; padding: 2px 10px; border-radius: 10px; background: #e8f4fd; color: #409EFF; }
.role-badge.operator { background: #f0f9eb; color: #67C23A; }
.msg-header-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

/* 收件箱/发件箱标签页 */
.msg-tabs { display: flex; gap: 0; margin-bottom: 10px; border-bottom: 2px solid #e8e8e8; }
.msg-tab {
  padding: 10px 24px; font-size: 14px; font-weight: 500; color: #909399; cursor: pointer;
  border-bottom: 2px solid transparent; margin-bottom: -2px; transition: all 0.2s;
  user-select: none;
}
.msg-tab:hover { color: #409EFF; }
.msg-tab.active { color: #409EFF; border-bottom-color: #409EFF; font-weight: 600; }
.msg-filter-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px; }
.filter-right { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.msg-list-wrapper { flex: 1; overflow-y: auto; min-height: 0; }
.msg-card { height: 100%; }
.msg-list { display: flex; flex-direction: column; }
.msg-item { display: flex; align-items: flex-start; gap: 10px; padding: 12px 10px; border-radius: 8px; cursor: pointer; border-bottom: 1px solid #f5f5f5; transition: background .15s; }
.msg-item:hover { background: #f8f9ff; }
.msg-item.msg-unread { background: #f0f4ff; border-left: 3px solid #409EFF; }
.msg-avatar { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; }
.avatar-error { background: #fef0f0; } .avatar-warning { background: #fdf6ec; } .avatar-info { background: #ecf5ff; } .avatar-success { background: #f0f9eb; }
.msg-body { flex: 1; min-width: 0; }
.msg-top { display: flex; justify-content: space-between; align-items: baseline; }
.msg-title { font-weight: 600; font-size: 14px; }
.title-error { color: #F56C6C; } .title-warning { color: #E6A23C; } .title-info { color: #409EFF; } .title-success { color: #67C23A; }
.msg-time { font-size: 11px; color: #bbb; white-space: nowrap; margin-left: 10px; }
.msg-content { font-size: 13px; color: #606266; margin-top: 4px; line-height: 1.5; word-break: break-all; }
.msg-tags { display: flex; align-items: center; gap: 5px; margin-top: 6px; flex-wrap: wrap; }
.unread-dot { width: 6px; height: 6px; background: #F56C6C; border-radius: 50%; flex-shrink: 0; }
.read-btn { flex-shrink: 0; }
.msg-pagination { margin-top: 10px; text-align: center; }
.op-report-notice { background: #fef0f0; border: 1px solid #fde2e2; border-radius: 6px; padding: 10px 14px; font-size: 13px; color: #F56C6C; }

@media (max-width: 768px) {
  .msg-center { padding: 10px; }
  .msg-header { flex-direction: column; align-items: flex-start; }
  .msg-item { padding: 10px 6px; }
}
</style>
