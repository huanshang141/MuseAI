<script setup>
import { Picture } from '@element-plus/icons-vue'

defineProps({
  exhibits: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['select'])
</script>

<template>
  <div class="exhibit-list">
    <el-skeleton v-if="loading" :rows="5" animated />

    <el-empty v-else-if="!exhibits.length" description="暂无展品数据" />

    <el-row v-else :gutter="16">
      <el-col
        v-for="exhibit in exhibits"
        :key="exhibit.id"
        :span="8"
        class="exhibit-col"
      >
        <el-card
          shadow="hover"
          class="exhibit-card"
          @click="emit('select', exhibit)"
        >
          <div class="exhibit-image" v-if="exhibit.image_url">
            <img :src="exhibit.image_url" :alt="exhibit.name" />
          </div>
          <div class="exhibit-image placeholder" v-else>
            <el-icon :size="40"><Picture /></el-icon>
          </div>
          <div class="exhibit-info">
            <div class="exhibit-name">{{ exhibit.name }}</div>
            <div class="exhibit-meta">
              <el-tag size="small" v-if="exhibit.category">
                {{ exhibit.category }}
              </el-tag>
              <span class="exhibit-location" v-if="exhibit.location">
                {{ exhibit.location }}
              </span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.exhibit-list {
  padding: 16px;
}

.exhibit-col {
  margin-bottom: 16px;
}

.exhibit-card {
  cursor: pointer;
  transition: all 0.3s;
}

.exhibit-card:hover {
  transform: translateY(-4px);
}

.exhibit-image {
  height: 160px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}

.exhibit-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.exhibit-image.placeholder {
  color: var(--el-text-color-placeholder);
}

.exhibit-info {
  padding: 12px 0;
}

.exhibit-name {
  font-weight: 500;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.exhibit-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.exhibit-location {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
