<template>
  <div class="uploader">
    <el-upload
      ref="uploadRef"
      :auto-upload="false"
      :limit="limit"
      :accept="accept"
      :file-list="fileList"
      list-type="picture-card"
      :on-exceed="onExceed"
      :on-change="onChange"
      :before-remove="onRemove"
      drag
    >
      <el-icon><UploadFilled /></el-icon>
      <div class="upload-text">拖拽图片到此处，或 <em>点击选择</em></div>
      <template #tip>
        <div class="tip">拖入即自动上传+识别，支持 JPG/PNG/BMP/WebP，单文件 ≤10MB</div>
      </template>
    </el-upload>
    <el-progress v-if="uploading" :percentage="progress" :status="progressStatus" :stroke-width="14" style="margin-top:12px" />
    <div class="upload-tip" v-if="uploading">⏳ 正在上传识别中...</div>
  </div>
</template>

<script setup>
/* global defineEmits */
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { uploadSingle } from '@/api/upload'
import { recognizeImage } from '@/api/ocr'

const emit = defineEmits(['uploaded', 'recognized'])
const uploadRef = ref(null)
const fileList = ref([])
const uploading = ref(false)
const progress = ref(0)
const progressStatus = ref('')
const accept = '.jpg,.jpeg,.png,.bmp,.webp'
const limit = 10

async function onChange(file) {
  const maxSize = 10 * 1024 * 1024
  if (file.size > maxSize) {
    fileList.value.pop()
    ElMessage.warning(`${file.name} 超过10MB限制`)
    return
  }
  // 拖入即自动上传+识别
  await autoProcess(file)
  // 处理完自动清掉预览
  const idx = fileList.value.indexOf(file)
  if (idx > -1) fileList.value.splice(idx, 1)
  uploadRef.value?.clearFiles()
}

async function autoProcess(file) {
  if (!file.raw) return
  uploading.value = true
  progress.value = 0
  progressStatus.value = ''

  try {
    const uploadRes = await uploadSingle(file.raw, (p) => { progress.value = p })
    const fileId = uploadRes.data.file_id
    progress.value = 100
    progressStatus.value = 'success'
    ElMessage.success('上传成功，正在识别...')

    emit('uploaded', uploadRes.data)
    fileList.value = []

    // 自动触发识别
    try {
      const ocrRes = await recognizeImage(fileId)
      const ocrData = ocrRes.data?.ocr || ocrRes.data
      const fields = ocrData?.fields || ocrData || {}
      if (fields.tracking_number || fields.district) {
        ElMessage.success(`识别完成: ${fields.district||''} ${fields.city||''} | ${fields.tracking_number||''}`)
      } else {
        ElMessage.info('图像已上传，识别结果待查看')
      }
    } catch {
      ElMessage.info('图像已上传')
    }
  } catch {
    progressStatus.value = 'exception'
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
  }
}

function onExceed() {
  ElMessage.warning('最多上传10张图片')
}

function onRemove(file) {
  const idx = fileList.value.indexOf(file)
  if (idx > -1) fileList.value.splice(idx, 1)
}
</script>

<style scoped>
.uploader { max-width: 600px; }
.upload-text { color: #999; font-size: 14px; margin-top: 8px; }
.tip { font-size: 12px; color: #999; margin-top: 8px; }
.upload-tip { text-align: center; color: #409EFF; font-size: 14px; margin-top: 8px; }
</style>
