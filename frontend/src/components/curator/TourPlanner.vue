<script setup>
import { ref } from 'vue'

const props = defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['plan'])

const availableTime = ref(60)
const interests = ref([])

const interestOptions = [
  { label: '青铜器', value: 'bronze' },
  { label: '陶瓷', value: 'ceramic' },
  { label: '书画', value: 'painting' },
  { label: '玉器', value: 'jade' },
  { label: '雕塑', value: 'sculpture' },
]

function handlePlan() {
  emit('plan', {
    availableTime: availableTime.value,
    interests: interests.value,
  })
}
</script>

<template>
  <el-card class="tour-planner">
    <template #header>
      <span>导览规划</span>
    </template>

    <el-form label-position="top">
      <el-form-item label="可用时间（分钟）">
        <el-slider v-model="availableTime" :min="15" :max="180" :step="15" show-input />
      </el-form-item>

      <el-form-item label="兴趣方向">
        <el-checkbox-group v-model="interests">
          <el-checkbox
            v-for="opt in interestOptions"
            :key="opt.value"
            :label="opt.value"
          >
            {{ opt.label }}
          </el-checkbox>
        </el-checkbox-group>
      </el-form-item>

      <el-form-item>
        <el-button
          type="primary"
          :loading="loading"
          @click="handlePlan"
          style="width: 100%"
        >
          生成导览路线
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.tour-planner {
  margin-bottom: 20px;
}
</style>
