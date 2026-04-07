<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <div class="admin-view">
    <el-card>
      <template #header>
        <span>管理后台</span>
      </template>
      <div class="admin-content">
        <router-view />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.admin-view {
  height: 100%;
}

.admin-content {
  min-height: 400px;
}
</style>
