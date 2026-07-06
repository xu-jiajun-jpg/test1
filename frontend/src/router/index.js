import { createRouter, createWebHashHistory } from 'vue-router'
import AppLayout from '@/components/AppLayout.vue'
import OperatorLayout from '@/components/OperatorLayout.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
  },
  // 分拣员专属
  {
    path: '/operator',
    component: OperatorLayout,
    redirect: '/operator/tasks',
    meta: { requiresAuth: true, role: 'operator' },
    children: [
      {
        path: 'tasks',
        name: 'OperatorTasks',
        component: () => import('@/views/OperatorTasks.vue'),
        meta: { requiresAuth: true, role: 'operator' },
      },
      {
        path: 'messages',
        name: 'OperatorMessages',
        component: () => import('@/views/MessageCenter.vue'),
        meta: { requiresAuth: true, role: 'operator' },
      },
      {
        path: 'logistics',
        name: 'OperatorLogistics',
        component: () => import('@/views/OperatorLogistics.vue'),
        meta: { requiresAuth: true, role: 'operator' },
      },
      {
        path: 'exceptions',
        name: 'OperatorException',
        component: () => import('@/views/OperatorException.vue'),
        meta: { requiresAuth: true, role: 'operator' },
      },
    ],
  },
  // 管理员
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'upload',
        name: 'Upload',
        component: () => import('@/views/Upload.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'ocr-result',
        name: 'OcrResult',
        component: () => import('@/views/OcrResult.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/views/History.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'exceptions',
        name: 'ExceptionList',
        component: () => import('@/views/ExceptionList.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'chutes',
        name: 'ChuteManage',
        component: () => import('@/views/ChuteManage.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'operators',
        name: 'OperatorManage',
        component: () => import('@/views/OperatorManage.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'config',
        name: 'SystemConfig',
        component: () => import('@/views/SystemConfig.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'alerts',
        name: 'AlertManage',
        component: () => import('@/views/AlertManage.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'users',
        name: 'UserManage',
        component: () => import('@/views/UserManage.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'track',
        name: 'TrackQuery',
        component: () => import('@/views/TrackQuery.vue'),
      },
      {
        path: 'messages',
        name: 'Messages',
        component: () => import('@/views/MessageCenter.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'scheduling',
        name: 'Scheduling',
        component: () => import('@/views/Scheduling.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'optimization',
        name: 'Optimization',
        component: () => import('@/views/Logistics.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'ops',
        name: 'RemoteOps',
        component: () => import('@/views/RemoteOps.vue'),
        meta: { requiresAuth: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.matched.some(r => r.meta.requiresAuth) && !token) {
    next('/login')
    return
  }
  // 分拣员登录后自动跳转（CH-006异常口→异常处理页，普通→任务页）
  if (token && to.path === '/login') {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (payload.role === 'operator') {
      if (payload.is_ch006) { next('/operator/exceptions'); return }
      next('/operator/tasks'); return
    }
    next('/dashboard')
    return
  }
  // 非管理员无法访问管理页面
  if (token && to.matched.some(r => r.meta.requiresAuth && !r.meta.role)) {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (payload.role === 'operator' && !to.path.startsWith('/operator')) {
      if (payload.is_ch006) { next('/operator/exceptions'); return }
      next('/operator/tasks')
      return
    }
  }
  next()
})

export default router
