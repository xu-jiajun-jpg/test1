<template>
    <div class="page">
      <h2>👥 用户与权限管理</h2>

      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="6"><el-card shadow="hover" class="stat-card"><div class="stat-num">{{ total }}</div><div class="stat-label">👤 用户总数</div></el-card></el-col>
        <el-col :span="6"><el-card shadow="hover" class="stat-card"><div class="stat-num">{{ users.filter(u=>u.role==='admin').length }}</div><div class="stat-label">🔑 管理员</div></el-card></el-col>
        <el-col :span="6"><el-card shadow="hover" class="stat-card"><div class="stat-num">{{ users.filter(u=>u.role==='operator').length }}</div><div class="stat-label">👷 操作员</div></el-card></el-col>
        <el-col :span="6"><el-card shadow="hover" class="stat-card"><div class="stat-num">{{ roles.length }}</div><div class="stat-label">🔐 角色类型</div></el-card></el-col>
      </el-row>
      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="16">
          <el-card header="用户列表">
            <el-button type="primary" size="small" @click="openUserDialog()" style="margin-bottom:12px">新增用户</el-button>
            <el-table :data="users" size="small"><el-table-column prop="username" label="用户名" width="120" /><el-table-column prop="display_name" label="显示名" width="120" /><el-table-column prop="role" label="角色" width="100"><template #default="{ row }"><el-tag size="small">{{ roleLabel(row.role) }}</el-tag></template></el-table-column><el-table-column label="启用" width="60"><template #default="{ row }"><el-tag :type="row.is_active?'success':'info'" size="small">{{ row.is_active?'是':'否' }}</el-tag></template></el-table-column><el-table-column label="操作" width="140"><template #default="{ row }"><el-button size="small" @click="openUserDialog(row)">编辑</el-button><el-button type="danger" size="small" @click="deleteUser(row)">删除</el-button></template></el-table-column></el-table>
            <el-pagination small v-model:current-page="page" :total="total" :page-size="20" layout="prev,next" @current-change="fetchUsers" />
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card header="角色权限">
            <el-table :data="roles" size="small"><el-table-column prop="name" label="角色" /><el-table-column prop="code" label="编码" width="100" /></el-table>
          </el-card>
        </el-col>
      </el-row>

      <el-dialog :title="isEditUser?'编辑用户':'新增用户'" v-model="userDialog" width="400px">
        <el-form :model="userForm" label-width="80px">
          <el-form-item label="用户名"><el-input v-model="userForm.username" :disabled="isEditUser" /></el-form-item>
          <el-form-item label="密码" v-if="!isEditUser"><el-input v-model="userForm.password" type="password" /></el-form-item>
          <el-form-item label="显示名"><el-input v-model="userForm.display_name" /></el-form-item>
          <el-form-item label="角色"><el-select v-model="userForm.role"><el-option v-for="r in roles" :key="r.code" :label="r.name" :value="r.code" /></el-select></el-form-item>
        </el-form>
        <template #footer><el-button @click="userDialog=false">取消</el-button><el-button type="primary" @click="saveUser">保存</el-button></template>
      </el-dialog>
    </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const users = ref([])
const roles = ref([])
const page = ref(1)
const total = ref(0)
const userDialog = ref(false)
const isEditUser = ref(false)
const userForm = reactive({ username:'', password:'', display_name:'', role:'operator', id:null })
function roleLabel(r) { return { admin:'管理员', supervisor:'主管', operator:'操作员', maintainer:'运维' }[r] || r }

async function fetchUsers(p = 1) { page.value = p; try { const r = await request.get('/api/users', { params: { page: p } }); users.value = r.data.items; total.value = r.data.total } catch { /* ignore */ } }
async function fetchRoles() { try { const r = await request.get('/api/users/roles'); roles.value = r.data } catch { /* ignore */ } }
function openUserDialog(row) {
  if (row) { isEditUser.value = true; Object.assign(userForm, row) }
  else { isEditUser.value = false; Object.assign(userForm, { username:'', password:'', display_name:'', role:'operator', id:null }) }
  userDialog.value = true
}
async function saveUser() {
  try {
    if (isEditUser.value) await request.put(`/api/users/${userForm.id}`, { display_name:userForm.display_name, role:userForm.role })
    else await request.post('/api/users', { username:userForm.username, password:userForm.password, display_name:userForm.display_name, role:userForm.role })
    ElMessage.success('保存成功'); userDialog.value = false; fetchUsers(page.value)
  } catch { /* ignore */ }
}
async function deleteUser(row) {
  try { await request.delete(`/api/users/${row.id}`); ElMessage.success('删除成功'); fetchUsers(page.value) } catch { /* ignore */ }
}
onMounted(() => { fetchUsers(); fetchRoles() })
</script>
<style scoped>
.page { padding: 20px; }
h2 { margin-bottom: 16px; color: #2c3e50; }
.stat-card { text-align: center; }
.stat-card .stat-num { font-size: 28px; font-weight: bold; color: #303133; }
.stat-card .stat-label { font-size: 12px; color: #909399; margin-top: 6px; }
</style>
