<template>
  <div class="layout">
    <el-container>
      <el-header class="header">
        <span class="title">📦 物流分拣平台</span>
        <div class="header-right">
          <el-badge :value="msgUnread" :hidden="msgUnread === 0" :max="99" class="msg-bell-badge">
            <el-button class="msg-bell-btn" size="small" circle @click="goMessages" title="消息中心">
              <span class="bell-icon">📬</span>
            </el-button>
          </el-badge>
          <span class="user">{{ authStore.user?.username || '' }}</span>
          <el-button type="danger" size="small" @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-container>
        <el-aside width="200px" class="sidebar">
          <el-menu router :default-active="route.path" background-color="#304156" text-color="#bfcbd9" active-text-color="#409EFF">
            <el-menu-item index="/dashboard">
              <span>📊 实时大屏</span>
            </el-menu-item>
            <el-menu-item index="/ocr-result">
              <span>📤 上传与识别</span>
            </el-menu-item>
            <el-sub-menu index="manage">
              <template #title>⚙️ 系统管理</template>
              <el-menu-item index="/history">历史查询</el-menu-item>
              <el-menu-item index="/exceptions">异常处理</el-menu-item>
              <el-menu-item index="/chutes">分拣口管理</el-menu-item>
              <el-menu-item index="/operators">人员管理</el-menu-item>
              <el-menu-item index="/config">系统配置</el-menu-item>
              <el-menu-item index="/alerts">告警管理</el-menu-item>
              <el-menu-item index="/users">用户权限</el-menu-item>
            </el-sub-menu>
            <el-sub-menu index="tools">
              <template #title>🔧 智能工具</template>
              <el-menu-item index="/scheduling">📅 智能排班</el-menu-item>
              <el-menu-item index="/optimization">🚚 装车配送</el-menu-item>
              <el-menu-item index="/ops">🖥️ 远程运维</el-menu-item>
            </el-sub-menu>
            <el-menu-item index="/track">
              <span>🔍 包裹追踪</span>
            </el-menu-item>
          </el-menu>
        </el-aside>
        <el-main class="main-content">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import request from '@/api/request'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const msgUnread = ref(0)
let msgTimer = null

async function fetchUnread() {
  try {
    const res = await request.get('/api/messages/unread-count', { params: { role: 'admin' } })
    msgUnread.value = res.data?.unread_count || 0
  } catch { /* ignore */ }
}

function goMessages() { router.push('/messages') }

onMounted(() => {
  fetchUnread()
  msgTimer = setInterval(fetchUnread, 5000)
})
onUnmounted(() => clearInterval(msgTimer))

function logout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout { height: 100vh; }
.header {
  background: #2c3e50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}
.header .title { color: #fff; font-size: 20px; font-weight: bold; }
.header-right { display: flex; align-items: center; gap: 10px; }
.header-right .user { color: #bfcbd9; font-size: 14px; }
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
.msg-bell-badge { margin-right: 2px; }
.sidebar { background: #304156; overflow-y: auto; }
.main-content { background: #f0f2f5; min-height: calc(100vh - 60px); }

@media (max-width: 768px) {
  .header .title { font-size: 16px; }
  .sidebar { width: 60px !important; }
}
</style>
