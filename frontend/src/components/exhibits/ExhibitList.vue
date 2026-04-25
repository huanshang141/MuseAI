<script setup>
import { Picture } from '@element-plus/icons-vue'
import { EmptyState, MuseumCard } from '../../design-system/components/index.js'

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

    <EmptyState
      v-else-if="!exhibits.length"
      icon="jar"
      title="暂无展品数据"
      description="稍后再来看看，或切换筛选条件。"
    />

    <div v-else class="exhibits-grid">
      <MuseumCard
        v-for="exhibit in exhibits"
        :key="exhibit.id"
        class="exhibit-card"
        :title="exhibit.name"
        :subtitle="exhibit.location || '馆内展区'"
        motif="pot"
        @click="emit('select', exhibit)"
      >
        <div class="exhibit-image" v-if="exhibit.image_url">
          <img :src="exhibit.image_url" :alt="exhibit.name" />
        </div>
        <div class="exhibit-image placeholder" v-else>
          <el-icon :size="40"><Picture /></el-icon>
        </div>

        <div class="exhibit-meta">
          <el-tag size="small" v-if="exhibit.category">{{ exhibit.category }}</el-tag>
          <span v-if="exhibit.period">{{ exhibit.period }}</span>
        </div>
      </MuseumCard>
    </div>
  </div>
</template>

<style scoped>
.exhibit-list {
  padding: 4px 0;
}

.exhibits-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.exhibit-card {
  cursor: pointer;
  transition: transform 0.2s ease;
}

.exhibit-card:hover {
  transform: translateY(-3px);
}

.exhibit-image {
  aspect-ratio: 16 / 9;
  width: 100%;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--color-bg-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}

.exhibit-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.exhibit-image.placeholder {
  color: var(--color-text-muted);
}

.exhibit-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--color-text-secondary);
  font-size: 12px;
}

@media (max-width: 1023px) {
  .exhibits-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .exhibits-grid {
    grid-template-columns: 1fr;
  }
}
</style>
