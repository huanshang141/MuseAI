<script setup>
import { Collection, Document, MapLocation, OfficeBuilding, Cpu } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const adminItems = [
  { path: '/admin/documents', label: '知识库管理', icon: Document },
  { path: '/admin/halls', label: '展厅设置', icon: OfficeBuilding },
  { path: '/admin/exhibits', label: '展品管理', icon: Collection },
  { path: '/admin/tour-paths', label: '路线管理', icon: MapLocation },
  { path: '/admin/prompts', label: '提示词管理', icon: Document },
  { path: '/admin/llm-traces', label: 'LLM 调用追踪', icon: Cpu },
]
</script>

<template>
  <section class="sidebar-section admin-nav-sidebar">
    <header class="sidebar-header">
      <h3>管理后台</h3>
    </header>

    <el-menu :default-active="route.path" router class="admin-menu">
      <el-menu-item v-for="item in adminItems" :key="item.path" :index="item.path">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </el-menu-item>
    </el-menu>
  </section>
</template>

<style scoped>
.sidebar-section {
  padding: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
}

.admin-menu {
  border-right: 0;
}
</style>
