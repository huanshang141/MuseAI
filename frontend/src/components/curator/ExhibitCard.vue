<script setup>
import { Picture } from '@element-plus/icons-vue'

defineProps({
  exhibit: {
    type: Object,
    required: true
  }
})
</script>

<template>
  <el-card class="exhibit-card" shadow="hover">
    <div class="exhibit-image" v-if="exhibit.image_url">
      <img :src="exhibit.image_url" :alt="exhibit.name" />
    </div>
    <div class="exhibit-image placeholder" v-else>
      <el-icon :size="40"><Picture /></el-icon>
    </div>
    <div class="exhibit-info">
      <h4>{{ exhibit.name }}</h4>
      <p class="description">{{ exhibit.description }}</p>
      <div class="meta">
        <el-tag size="small">{{ exhibit.category }}</el-tag>
        <span class="era" v-if="exhibit.era">{{ exhibit.era }}</span>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.exhibit-card {
  height: 100%;
}

.exhibit-image {
  height: 200px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-light);
}

.exhibit-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.exhibit-info {
  padding: 12px 0;
}

.exhibit-info h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
}

.description {
  color: var(--el-text-color-secondary);
  font-size: 14px;
  line-height: 1.5;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.era {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
