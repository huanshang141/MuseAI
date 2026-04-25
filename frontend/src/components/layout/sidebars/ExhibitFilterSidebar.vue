<script setup>
const quickFilters = ['彩陶', '骨器', '陶俑', '聚落遗址']
</script>

<template>
  <section class="sidebar-section exhibit-filters-sidebar">
    <header class="sidebar-header">
      <h3>展品筛选</h3>
      <p>可在展品页使用搜索与楼层筛选。</p>
    </header>

    <div class="filter-group">
      <span class="filter-label">推荐主题</span>
      <div class="filter-tags">
        <el-tag v-for="item in quickFilters" :key="item" effect="plain" type="info">{{ item }}</el-tag>
      </div>
    </div>

    <p class="hint">提示：在地图视图中点击标记可快速定位展品。</p>
  </section>
</template>

<style scoped>
.sidebar-section {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
}

.sidebar-header p {
  margin: 6px 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-label {
  font-size: 12px;
  color: var(--color-text-muted);
}

.filter-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.hint {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-muted);
  line-height: 1.6;
}
</style>
