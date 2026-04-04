<script setup>
import { ref } from 'vue'
import { api } from '../api/index.js'

const selectedFile = ref(null)
const uploadResult = ref(null)
const loading = ref(false)

function handleFileChange(event) {
  selectedFile.value = event.target.files[0]
}

async function uploadFile() {
  if (!selectedFile.value) return
  loading.value = true
  uploadResult.value = await api.documents.upload(selectedFile.value)
  loading.value = false
}
</script>

<template>
  <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px;">
    <h3 style="margin: 0 0 12px 0;">上传文档</h3>
    
    <div style="display: flex; gap: 12px; align-items: center;">
      <input type="file" @change="handleFileChange" style="flex: 1;" />
      <button @click="uploadFile" :disabled="!selectedFile || loading" style="padding: 8px 16px; cursor: pointer;">
        {{ loading ? '上传中...' : '上传' }}
      </button>
    </div>
    
    <pre v-if="uploadResult" style="background: #f5f5f5; padding: 8px; border-radius: 4px; margin-top: 12px; overflow: auto;">{{ JSON.stringify(uploadResult, null, 2) }}</pre>
  </div>
</template>
