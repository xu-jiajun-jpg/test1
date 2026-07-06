<template>
  <div class="login-container">
    <div class="login-card">
      <h2>物流分拣平台</h2>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="0" @keyup.enter="doLogin">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" :prefix-icon="userIcon" @keyup.enter="focusPassword" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input ref="pwdRef" v-model="form.password" type="password" placeholder="密码" :prefix-icon="lockIcon" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="doLogin" style="width:100%">登录</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, shallowRef, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import request from '@/api/request'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref(null)
const pwdRef = ref(null)
const loading = ref(false)
const userIcon = shallowRef(User)
const lockIcon = shallowRef(Lock)

const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

function focusPassword() {
  nextTick(() => {
    const input = pwdRef.value?.$el?.querySelector('input')
    if (input) input.focus()
  })
}

async function doLogin() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    const res = await request.post('/api/auth/login', {
      username: form.username,
      password: form.password,
    })
    authStore.setAuth(res.access_token, res.user)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e) {
    // error handled in interceptor
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container { height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1e3c72, #2a5298); }
.login-card { background: #fff; padding: 40px 36px; border-radius: 8px; width: 380px; box-shadow: 0 4px 20px rgba(0,0,0,.3); }
.login-card h2 { text-align: center; margin-bottom: 30px; color: #2c3e50; }
</style>
