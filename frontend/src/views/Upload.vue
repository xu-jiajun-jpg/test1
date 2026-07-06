<template>
    <div class="page">
      <h2>📤 包裹图片上传</h2>
      <el-card style="margin: 16px 0">
        <FileUploader @uploaded="onUploaded" />
      </el-card>

      <el-card v-if="records.length" header="上传记录">
        <el-table :data="records" stripe>
          <el-table-column label="预览" width="90">
            <template #default="{ row }">
              <el-image :src="previewUrl(row)" style="width:60px;height:60px;border-radius:4px" fit="cover" preview-teleported :z-index="3000">
                <template #error><div class="img-placeholder">📦</div></template>
              </el-image>
            </template>
          </el-table-column>
          <el-table-column prop="original_name" label="文件名" min-width="150" />
          <el-table-column label="大小" width="100">
            <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
          </el-table-column>
          <el-table-column label="包裹尺寸" width="150">
            <template #default="{ row }">
              <span v-if="row.package_length">{{ row.package_length }}×{{ row.package_width }}×{{ row.package_height }} cm</span>
              <span v-else style="color:#ccc">-</span>
              <span v-if="row.package_volume" style="display:block;font-size:11px;color:#909399">{{ (row.package_volume/1000).toFixed(1) }}L</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }"><el-tag :type="row.status==='done'?'success':'warning'" size="small">{{ row.status }}</el-tag></template>
          </el-table-column>
          <el-table-column label="时间" width="160">
            <template #default="{ row }">{{ row.created_at?.slice(0,19) }}</template>
          </el-table-column>
        </el-table>
        <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="prev,pager,next" style="margin-top:12px;justify-content:center" @current-change="fetchRecords" />
      </el-card>
      <el-empty v-else description="暂无上传记录，请上传图片" />
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import FileUploader from '@/components/FileUploader.vue'
import { getUploadRecords } from '@/api/upload'

const baseUrl = `http://${window.location.hostname}:8003`

function previewUrl(row) {
  if (row.thumbnail_url) return baseUrl + row.thumbnail_url
  if (row.file_url) return baseUrl + row.file_url
  return ''
}
const records = ref([])
const page = ref(1)
const total = ref(0)

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(2) + ' MB'
}

async function fetchRecords(p = 1) {
  page.value = p
  try {
    const res = await getUploadRecords(p)
    records.value = res.data.items
    total.value = res.data.total
  } catch { /* ignore */ }
}

function onUploaded() {
  fetchRecords(1)
}

onMounted(() => fetchRecords())
</script>

<style scoped>
.page { padding: 20px; }
h2 { margin-bottom: 16px; color: #2c3e50; }
.img-placeholder { width:60px;height:60px;display:flex;align-items:center;justify-content:center;background:#f0f0f0;border-radius:4px;font-size:24px; }
</style>
