<script setup>
import { ref } from 'vue'
import { api } from '../api/index.js'

const healthResult = ref(null)
const readyResult = ref(null)
const loading = ref({ health: false, ready: false })

async function checkHealth() {
  loading.value.health = true
  healthResult.value = await api.health()
  loading.value.health = false
}

async function checkReady() {
  loading.value.ready = true
  readyResult.value = await api.ready()
  loading.value.ready = false
}
</script>

<template>
  <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px;">
    <h3 style="margin: 0 0 12px 0;">健康检查</h3>
    
    <div style="margin-bottom: 12px;">
      <button @click="checkHealth" :disabled="loading.health" style="padding: 8px 16px; cursor: pointer;">
        {{ loading.health ? '检查中...' : '/health' }}
      </button>
      <pre v-if="healthResult" style="background: #f5f5f5; padding: 8px; border-radius: 4px; margin-top: 8px; overflow: auto;">{{ JSON.stringify(healthResult, null, 2) }}</pre>
    </div>
    
    <div>
      <button @click="checkReady" :disabled="loading.ready" style="padding: 8px 16px; cursor: pointer;">
        {{ loading.ready ? '检查中...' : '/ready' }}
      </button>
      <pre v-if="readyResult" style="background: #f5f5f5; padding: 8px; border-radius: 4px; margin-top: 8px; overflow: auto;">{{ JSON.stringify(readyResult, null, 2) }}</pre>
    </div>
  </div>
</template>
