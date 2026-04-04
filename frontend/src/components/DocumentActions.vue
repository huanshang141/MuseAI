<script setup>
import { ref } from 'vue'
import { api } from '../api/index.js'

const docId = ref('')
const result = ref(null)
const loading = ref({ get: false, status: false, delete: false })

async function getDocument() {
  if (!docId.value) return
  loading.value.get = true
  result.value = await api.documents.get(docId.value)
  loading.value.get = false
}

async function getStatus() {
  if (!docId.value) return
  loading.value.status = true
  result.value = await api.documents.status(docId.value)
  loading.value.status = false
}

async function deleteDocument() {
  if (!docId.value) return
  if (!confirm('确定删除此文档？')) return
  loading.value.delete = true
  result.value = await api.documents.delete(docId.value)
  loading.value.delete = false
}
</script>

<template>
  <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px;">
    <h3 style="margin: 0 0 12px 0;">文档操作</h3>
    
    <div style="display: flex; gap: 8px; margin-bottom: 12px;">
      <input 
        v-model="docId" 
        placeholder="输入文档 ID" 
        style="flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
      />
      <button @click="getDocument" :disabled="!docId || loading.get" style="padding: 8px 16px; cursor: pointer;">
        {{ loading.get ? '...' : '查询' }}
      </button>
      <button @click="getStatus" :disabled="!docId || loading.status" style="padding: 8px 16px; cursor: pointer;">
        {{ loading.status ? '...' : '状态' }}
      </button>
      <button @click="deleteDocument" :disabled="!docId || loading.delete" style="padding: 8px 16px; cursor: pointer; background: #ff4444; color: white; border: none; border-radius: 4px;">
        {{ loading.delete ? '...' : '删除' }}
      </button>
    </div>
    
    <pre v-if="result" style="background: #f5f5f5; padding: 8px; border-radius: 4px; overflow: auto;">{{ JSON.stringify(result, null, 2) }}</pre>
  </div>
</template>
