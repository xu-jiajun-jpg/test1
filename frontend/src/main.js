import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'

// 应用启动时先清除过期/无效 token，确保首次访问展示登录页
;(function cleanupStaleToken() {
  const token = localStorage.getItem('token')
  if (!token) return
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    const now = Math.floor(Date.now() / 1000)
    if (payload.exp && payload.exp < now) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    }
  } catch {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }
})()

// Element Plus
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

// ECharts
import VueECharts from 'vue-echarts'
import 'echarts'

const app = createApp(App)

// 全局错误处理
app.config.errorHandler = (err, vm, info) => {
  if (err?.message?.includes("parentNode") || err?.message?.includes("ResizeObserver")) {
    return  // 忽略 ECharts 图表 resize 和 Element Plus 卸载边界错误
  }
  console.error('[Vue]', err, info)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.component('v-chart', VueECharts)

app.mount('#app')
