<script setup>
import { useDocuments } from '../../composables/useDocuments.js'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'

const { uploadDocument } = useDocuments()

async function handleUpload(options) {
  const result = await uploadDocument(options.file)
  if (result.ok) {
    ElMessage.success('文档上传成功')
  } else {
    ElMessage.error(`上传失败: ${result.data.detail || '未知错误'}`)
  }
}

function handleExceed() {
  ElMessage.warning('一次只能上传一个文件')
}
</script>

<template>
  <div style="padding: 16px;">
    <el-upload
      :auto-upload="true"
      :show-file-list="false"
      :limit="1"
      :on-exceed="handleExceed"
      :http-request="handleUpload"
      accept=".txt,.md,.pdf"
      drag
    >
      <el-icon style="font-size: 48px; color: #909399;"><UploadFilled /></el-icon>
      <div style="margin-top: 8px; color: #606266;">
        拖拽文件到此处或 <em style="color: #409EFF;">点击上传</em>
      </div>
      <template #tip>
        <div style="color: #909399; font-size: 12px; margin-top: 8px;">
          支持 .txt, .md, .pdf 文件，最大 50MB
        </div>
      </template>
    </el-upload>
  </div>
</template>
