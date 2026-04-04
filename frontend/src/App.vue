<script setup>
import HealthCard from './components/HealthCard.vue'
import DocumentUpload from './components/DocumentUpload.vue'
import DocumentList from './components/DocumentList.vue'
import DocumentActions from './components/DocumentActions.vue'
</script>

<template>
  <div style="max-width: 1200px; margin: 0 auto; padding: 20px; font-family: system-ui, sans-serif;">
    <h1 style="margin-bottom: 24px; color: #333;">MuseAI API 测试面板</h1>
    
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 16px;">
      <HealthCard />
    </div>
    
    <div style="display: grid; gap: 16px;">
      <DocumentUpload />
      <DocumentList />
      <DocumentActions />
    </div>
  </div>
</template>
