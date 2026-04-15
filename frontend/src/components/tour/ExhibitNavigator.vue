<script setup>
const props = defineProps({ hasNext: Boolean, nextExhibit: Object, isLast: Boolean })
const emit = defineEmits(['next', 'complete', 'deep-dive'])
</script>

<template>
  <div class="navigator">
    <el-button @click="emit('deep-dive')" text class="nav-btn deep-dive">💡 继续深入了解</el-button>
    <el-button v-if="hasNext" @click="emit('next')" type="primary" class="nav-btn next-btn">下一个展品 → {{ nextExhibit?.name || '' }}</el-button>
    <el-button v-if="isLast" @click="emit('complete')" type="success" class="nav-btn complete-btn">完成本展厅 ✓</el-button>
  </div>
</template>

<style scoped>
.navigator { display: flex; justify-content: center; gap: 16px; padding: 12px 24px; border-top: 1px solid rgba(255,255,255,0.08); background: rgba(0,0,0,0.2); }
.nav-btn { border-radius: 20px; }
.deep-dive { color: #d4a574; }
.next-btn { background: #d4a574; border-color: #d4a574; }
.complete-btn { background: #8fbc8f; border-color: #8fbc8f; }
</style>
