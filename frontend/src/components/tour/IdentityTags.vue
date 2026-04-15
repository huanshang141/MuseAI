<script setup>
const props = defineProps({
  tags: Array,
})

const tagColors = ['#d4a574', '#8fbc8f', '#6fa8dc']
</script>

<template>
  <div class="identity-tags">
    <h3 class="section-title">你的身份标签</h3>
    <div class="tags">
      <div v-for="(tag, i) in (tags || [])" :key="tag" class="tag-card" :style="{ borderColor: tagColors[i % 3] }">
        <span class="tag-text" :style="{ color: tagColors[i % 3] }">{{ tag }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.identity-tags {
  margin-bottom: 32px;
}

.section-title {
  font-size: 18px;
  color: #f0e6d3;
  margin-bottom: 16px;
}

.tags {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.tag-card {
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid;
  border-radius: 12px;
}

.tag-text {
  font-size: 15px;
  font-weight: 600;
}
</style>
