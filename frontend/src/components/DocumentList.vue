<script setup>
import { ref } from 'vue'
import { api } from '../api/index.js'

const documents = ref(null)
const loading = ref(false)

async function fetchDocuments() {
  loading.value = true
  const result = await api.documents.list()
  documents.value = result
  loading.value = false
}
</script>

<template>
  <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <h3 style="margin: 0;">文档列表</h3>
      <button @click="fetchDocuments" :disabled="loading" style="padding: 8px 16px; cursor: pointer;">
        {{ loading ? '加载中...' : '刷新' }}
      </button>
    </div>
    
    <pre v-if="documents" style="background: #f5f5f5; padding: 8px; border-radius: 4px; overflow: auto;">{{ JSON.stringify(documents, null, 2) }}</pre>
  </div>
</template>
