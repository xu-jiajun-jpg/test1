<template>
  <div class="layout">
    <el-container>
      <el-header class="header">
        <span class="title">📦 分拣任务面板</span>
        <div class="header-right">
          <!-- CH-006 操作员专属导航 -->
          <template v-if="isCh006">
            <el-button v-if="!isOnExceptions" size="small" type="danger" @click="router.push('/operator/exceptions')" style="margin-right:8px">
              🔬 异常处理
            </el-button>
            <el-button v-if="isOnExceptions" size="small" type="primary" @click="router.push('/operator/tasks')" style="margin-right:8px">
              ← 返回任务
            </el-button>
          </template>
          <!-- 普通操作员导航 -->
          <template v-else>
            <el-button v-if="isOnMessages || isOnExceptions" size="small" type="primary" @click="router.push('/operator/tasks')" style="margin-right:8px">
              ← 返回任务
            </el-button>
            <el-button v-if="isOnLogistics" size="small" type="primary" @click="router.push('/operator/tasks')" style="margin-right:8px">
              ← 返回任务
            </el-button>
            <el-button v-if="!isOnLogistics && !isOnExceptions" size="small" type="success" @click="router.push('/operator/logistics')" style="margin-right:8px">
              🚚 装车路径
            </el-button>
          </template>
          <el-badge :value="msgUnread" :hidden="msgUnread === 0" :max="99" class="msg-bell-badge">
            <el-button class="msg-bell-btn" size="small" circle @click="goMessages" title="消息中心">
              <span class="bell-icon">📬</span>
            </el-button>
          </el-badge>
          <span class="user">{{ store.user?.display_name || store.user?.username }}</span>
          <el-tag size="small" type="success" style="margin:0 8px">{{ chuteInfo }}</el-tag>
          <el-button type="danger" size="small" @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import request from '@/api/request'

const router = useRouter()
const route = useRoute()
const store = useAuthStore()

const isOnMessages = computed(() => route.path === '/operator/messages')
const isOnLogistics = computed(() => route.path === '/operator/logistics')
const isOnExceptions = computed(() => route.path === '/operator/exceptions')
const isCh006 = computed(() => store.user?.is_ch006 || store.user?.chute_codes?.includes('CH-006'))

const chuteInfo = computed(() => {
  const user = store.user
  if (!user) return '未登录'
  const codes = user.chute_codes
  return codes?.length ? `负责: ${codes.join(', ')}` : '未分配分拣口'
})

const msgUnread = ref(0)
let msgTimer = null

async function fetchUnread() {
  try {
    const params = { role: 'operator' }
    const user = store.user
    if (user?.operator_id) params.operator_id = user.operator_id
    if (user?.chute_codes?.length) params.chute_codes = user.chute_codes.join(',')
    const res = await request.get('/api/messages/unread-count', { params })
    msgUnread.value = res.data?.unread_count || 0
  } catch { /* ignore */ }
}

function goMessages() { router.push('/operator/messages') }

onMounted(() => {
  fetchUnread()
  msgTimer = setInterval(fetchUnread, 5000)
})

onUnmounted(() => clearInterval(msgTimer))

function logout() {
  localStorage.removeItem('token')
  store.user = null
  router.push('/login')
}
</script>

<style scoped>
.layout { height: 100vh; }
.header {
  background: #2c3e50;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}
.title { font-size: 18px; font-weight: bold; }
.header-right { display: flex; align-items: center; gap: 8px; }
.header-right .user { font-size: 14px; }
.msg-bell-btn {
  border: none;
  background: rgba(255,255,255,.1);
  color: #fff;
  font-size: 18px;
  width: 36px;
  height: 36px;
  transition: background .2s;
}
.msg-bell-btn:hover { background: rgba(255,255,255,.2); }
.bell-icon { font-size: 18px; line-height: 1; }
.main-content { background: #f0f2f5; padding: 20px; min-height: calc(100vh - 60px); }

@media (max-width: 768px) {
  .header { padding: 0 10px; }
  .title { font-size: 15px; }
  .header-right { gap: 4px; }
}
</style>
