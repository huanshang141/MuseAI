<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../api/index.js'

const healthStatus = ref('checking')

async function checkHealth() {
  healthStatus.value = 'checking'
  try {
    const result = await api.health()
    healthStatus.value = result.ok ? 'healthy' : 'unhealthy'
  } catch (error) {
    healthStatus.value = 'error'
  }
}

onMounted(checkHealth)
</script>

<template>
  <div class="app-header">
    <div class="logo">
      <el-icon class="logo-icon"><Collection /></el-icon>
      <span>MuseAI - 博物馆展品问答助手</span>
    </div>
    <div style="display: flex; align-items: center; gap: 12px;">
      <el-tag 
        :type="healthStatus === 'healthy' ? 'success' : healthStatus === 'checking' ? 'info' : 'danger'" 
        size="small"
      >
        {{ healthStatus === 'healthy' ? '服务正常' : healthStatus === 'checking' ? '检测中...' : '服务异常' }}
      </el-tag>
    </div>
  </div>
</template>
