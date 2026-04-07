<script setup>
import { ref } from 'vue'

const emit = defineEmits(['filter'])

const filters = ref({
  category: null,
  hall: null,
  keyword: '',
})

const categoryOptions = [
  { label: '全部', value: null },
  { label: '青铜器', value: 'bronze' },
  { label: '陶瓷', value: 'ceramic' },
  { label: '书画', value: 'painting' },
  { label: '玉器', value: 'jade' },
  { label: '雕塑', value: 'sculpture' },
]

const hallOptions = [
  { label: '全部', value: null },
  { label: '一楼展厅', value: '1F' },
  { label: '二楼展厅', value: '2F' },
  { label: '三楼展厅', value: '3F' },
]

function handleFilter() {
  emit('filter', {
    category: filters.value.category,
    hall: filters.value.hall,
    keyword: filters.value.keyword,
  })
}

function handleReset() {
  filters.value = {
    category: null,
    hall: null,
    keyword: '',
  }
  handleFilter()
}
</script>

<template>
  <el-card class="exhibit-filter">
    <template #header>
      <span>筛选条件</span>
    </template>

    <el-form label-position="top" size="small">
      <el-form-item label="展品类别">
        <el-select
          v-model="filters.category"
          placeholder="选择类别"
          clearable
          @change="handleFilter"
        >
          <el-option
            v-for="opt in categoryOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="展厅位置">
        <el-select
          v-model="filters.hall"
          placeholder="选择展厅"
          clearable
          @change="handleFilter"
        >
          <el-option
            v-for="opt in hallOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="关键词">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索展品名称"
          clearable
          @keyup.enter="handleFilter"
        />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="handleFilter" style="width: 100%">
          应用筛选
        </el-button>
        <el-button @click="handleReset" style="width: 100%; margin-top: 8px">
          重置
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.exhibit-filter {
  height: 100%;
}

.el-select {
  width: 100%;
}
</style>
