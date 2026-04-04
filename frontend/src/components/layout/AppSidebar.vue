<script setup>
import DocumentUpload from '../knowledge/DocumentUpload.vue'
import DocumentList from '../knowledge/DocumentList.vue'
</script>

<template>
  <div class="app-sidebar">
    <div style="padding: 16px; border-bottom: 1px solid #e4e7ed;">
      <h3 style="margin: 0; font-size: 16px;">知识库管理</h3>
    </div>
    <DocumentUpload />
    <DocumentList />
  </div>
</template>
