<script setup>
import DocumentUpload from '../knowledge/DocumentUpload.vue'
import DocumentList from '../knowledge/DocumentList.vue'
</script>

<template>
  <div class="document-manager">
    <div class="header">
      <h2>知识库管理</h2>
      <p>上传、查看并维护知识库文档索引状态。</p>
    </div>

    <el-card shadow="never" class="upload-card">
      <template #header>
        <span>上传文档</span>
      </template>
      <DocumentUpload />
    </el-card>

    <el-card shadow="never" class="list-card">
      <template #header>
        <span>文档列表</span>
      </template>
      <DocumentList />
    </el-card>
  </div>
</template>

<style scoped>
.document-manager {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header h2 {
  margin: 0;
  font-size: 20px;
  color: var(--el-text-color-primary);
}

.header p {
  margin: 8px 0 0;
  color: var(--el-text-color-regular);
  font-size: 14px;
}

.upload-card,
.list-card {
  border: 1px solid var(--el-border-color-lighter);
}
</style>
