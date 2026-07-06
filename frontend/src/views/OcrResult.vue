<template>
    <div class="page">
      <h2>📋 识别结果</h2>
      <el-card style="margin-bottom:16px" header="待识别文件">
        <el-upload
          :auto-upload="false"
          :limit="1"
          accept=".jpg,.jpeg,.png,.bmp"
          list-type="picture"
          :file-list="uploadFiles"
          :on-change="(f) => uploadFiles = [f]"
          drag style="max-width:500px"
        >
          <div class="upload-text">拖拽或点击选择图片进行识别</div>
        </el-upload>
        <el-button v-if="uploadFiles.length" type="primary" :loading="recognizing" @click="startRecognize" style="margin-top:12px">
          开始识别
        </el-button>
      </el-card>

      <el-card style="margin-bottom:16px" header="🎲 模拟包裹生成">
        <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
          <span style="font-size:13px;color:#606266">数量</span>
          <el-input-number v-model="simCount" :min="1" :max="40" :step="1" size="small" style="width:100px" />
          <span style="font-size:13px;color:#606266;margin-left:8px">破损占比</span>
          <el-slider v-model="simDamageRate" :min="0" :max="100" :step="5" show-input size="small" style="width:180px" />
          <el-button type="warning" :loading="simulating" @click="startSimulate">一键生成模拟包裹</el-button>
          <span style="font-size:12px;color:#909399">生成后自动识别并入库</span>
        </div>
      </el-card>

      <el-card v-if="currentResult" header="识别详情" style="margin-bottom:16px">
        <template v-if="currentResult.ocr">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="收件人">{{ currentResult.ocr.fields?.receiver_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="电话">{{ currentResult.ocr.fields?.phone || '-' }}</el-descriptions-item>
            <el-descriptions-item label="运单号">{{ currentResult.ocr.fields?.tracking_number || '-' }}</el-descriptions-item>
            <el-descriptions-item label="省份">{{ currentResult.ocr.fields?.province || '-' }}</el-descriptions-item>
            <el-descriptions-item label="城市">{{ currentResult.ocr.fields?.city || '-' }}</el-descriptions-item>
            <el-descriptions-item label="识别目的地">
              <el-tag v-if="currentResult.ocr.fields?.district" type="success">{{ currentResult.ocr.fields.district }}</el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="OCR状态">
              <el-tag :type="statusColor(currentResult.ocr.status)">{{ currentResult.ocr.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="条码类型" :span="2">{{ currentResult.barcode?.type || '无' }}</el-descriptions-item>
            <el-descriptions-item label="条码数据">{{ currentResult.barcode?.data || '-' }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </el-card>

      <el-card header="识别历史">
        <el-table :data="records" stripe @row-click="viewDetail">
          <el-table-column label="图片" width="80">
            <template #default="{ row }">
              <el-image
                :src="previewSrc(row)"
                style="width:50px;height:50px;border-radius:4px"
                fit="cover"
                preview-teleported
                :z-index="3000"
              >
                <template #error><div style="width:50px;height:50px;display:flex;align-items:center;justify-content:center;background:#f0f0f0;border-radius:4px;font-size:20px">📦</div></template>
              </el-image>
            </template>
          </el-table-column>
          <el-table-column prop="original_name" label="文件名" min-width="150" />
          <el-table-column prop="tracking_number" label="运单号" width="150" />
          <el-table-column label="条码" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.barcode_type" type="success" size="small">{{ row.barcode_type }}</el-tag>
              <span v-else style="color:#ccc;font-size:12px">未检测</span>
            </template>
          </el-table-column>
          <el-table-column prop="district" label="目的区" width="100" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }"><el-tag :type="statusColor(row.status)" size="small">{{ row.status }}</el-tag></template>
          </el-table-column>
        </el-table>
        <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="prev,pager,next" style="margin-top:12px;justify-content:center" @current-change="fetchRecords" />
      </el-card>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getOcrResults, recognizeImage, getOcrResult } from '@/api/ocr'
import { uploadSingle } from '@/api/upload'
import { demoGenerate } from '@/api/demo'
import { ElMessage } from 'element-plus'

const baseUrl = 'http://127.0.0.1:8003'
function previewSrc(row) {
  if (row?.thumbnail_url) return baseUrl + row.thumbnail_url
  if (row?.file_url) return baseUrl + row.file_url
  return ''
}
const records = ref([])
const page = ref(1)
const total = ref(0)
const uploadFiles = ref([])
const recognizing = ref(false)
const currentResult = ref(null)
const simCount = ref(5)
const simDamageRate = ref(15)
const simulating = ref(false)

async function startSimulate() {
  simulating.value = true
  try {
    const res = await demoGenerate(simCount.value, simDamageRate.value / 100)
    ElMessage.success(res.data?.message || `已生成 ${simCount.value} 个模拟包裹（破损占比 ${simDamageRate.value}%）`)
    fetchRecords(1)
  } catch { ElMessage.error('模拟生成失败') }
  finally { simulating.value = false }
}

function statusColor(s) { return s === 'auto_pass' ? 'success' : s === 'need_review' ? 'warning' : s === 'not_waybill' ? 'info' : 'danger' }

async function fetchRecords(p = 1) {
  page.value = p
  try { const res = await getOcrResults(p); records.value = res.data.items; total.value = res.data.total } catch { /* ignore */ }
}

async function startRecognize() {
  if (!uploadFiles.value.length) return
  recognizing.value = true
  currentResult.value = null
  try {
    const file = uploadFiles.value[0].raw
    const uploadRes = await uploadSingle(file)
    const fileId = uploadRes.data.file_id
    const ocrRes = await recognizeImage(fileId)
    currentResult.value = { ocr: ocrRes.data?.ocr || ocrRes.data }
    uploadFiles.value = []
    fetchRecords(1)
    ElMessage.success('识别完成')
  } catch {
    ElMessage.error('识别失败')
  } finally {
    recognizing.value = false
  }
}

async function viewDetail(row) {
  currentResult.value = null
  try {
    const check = await getOcrResult(row.file_id)
    if (check.data) {
      // getOcrResult 返回扁平字段，包装成 { fields: {...} } 以匹配模板
      currentResult.value = { ocr: { fields: check.data, status: check.data.status } }
      return
    }
    const res = await recognizeImage(row.file_id)
    currentResult.value = { ocr: res.data?.ocr || res.data }
  } catch { ElMessage.error('查询失败') }
}

onMounted(() => fetchRecords())
</script>

<style scoped>
.page { padding: 20px; }
h2 { margin-bottom: 16px; color: #2c3e50; }
.upload-text { color: #999; font-size: 14px; margin-top: 8px; }
</style>
