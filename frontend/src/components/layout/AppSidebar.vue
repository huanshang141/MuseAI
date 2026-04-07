<script setup>
import DocumentUpload from '../knowledge/DocumentUpload.vue'
import DocumentList from '../knowledge/DocumentList.vue'
import { useAuth } from '../../composables/useAuth.js'
import { useRoute } from 'vue-router'
import { computed } from 'vue'
import { MapLocation, Collection, Setting } from '@element-plus/icons-vue'

const route = useRoute()
const { isAuthenticated } = useAuth()

// Determine sidebar content based on route
const sidebarMode = computed(() => {
  const path = route.path
  if (path.startsWith('/admin')) return 'admin'
  if (path === '/curator') return 'curator'
  if (path === '/exhibits') return 'exhibits'
  return 'home'
})

function handleLogin() {
  // Emit event to show auth modal via App.vue's provide
  // This will be handled by the parent component
}
</script>

<template>
  <div class="app-sidebar">
    <!-- Home route: Knowledge base management -->
    <template v-if="sidebarMode === 'home'">
      <div style="padding: 16px; border-bottom: 1px solid #e4e7ed;">
        <h3 style="margin: 0; font-size: 16px;">知识库管理</h3>
      </div>

      <!-- Show documents when authenticated -->
      <template v-if="isAuthenticated">
        <DocumentUpload />
        <DocumentList />
      </template>

      <!-- Show login prompt when not authenticated -->
      <template v-else>
        <div style="padding: 20px; text-align: center; color: #909399;">
          <el-empty description="请先登录" :image-size="80" />
          <el-button type="primary" size="small" @click="handleLogin" style="margin-top: 12px;">
            登录
          </el-button>
        </div>
      </template>
    </template>

    <!-- Curator route: Tour planning tips -->
    <template v-else-if="sidebarMode === 'curator'">
      <div style="padding: 16px; border-bottom: 1px solid #e4e7ed;">
        <h3 style="margin: 0; font-size: 16px; display: flex; align-items: center; gap: 8px;">
          <el-icon><MapLocation /></el-icon>
          导览助手
        </h3>
      </div>
      <div style="padding: 16px; color: #606266; font-size: 14px; line-height: 1.6;">
        <p>欢迎使用导览助手！</p>
        <ul style="padding-left: 20px; margin: 12px 0;">
          <li>选择感兴趣的展品加入导览路线</li>
          <li>系统会为您规划最优参观路径</li>
          <li>支持语音讲解和多语言服务</li>
        </ul>
        <el-divider />
        <p style="color: #909399; font-size: 12px;">
          提示：点击地图上的展品可查看详情
        </p>
      </div>
    </template>

    <!-- Exhibits route: Filter info -->
    <template v-else-if="sidebarMode === 'exhibits'">
      <div style="padding: 16px; border-bottom: 1px solid #e4e7ed;">
        <h3 style="margin: 0; font-size: 16px; display: flex; align-items: center; gap: 8px;">
          <el-icon><Collection /></el-icon>
          展品浏览
        </h3>
      </div>
      <div style="padding: 16px; color: #606266; font-size: 14px; line-height: 1.6;">
        <p>浏览博物馆展品信息。</p>
        <el-divider />
        <p style="color: #909399; font-size: 12px;">
          使用上方搜索框和筛选器查找展品
        </p>
      </div>
    </template>

    <!-- Admin route: Admin sub-navigation -->
    <template v-else-if="sidebarMode === 'admin'">
      <div style="padding: 16px; border-bottom: 1px solid #e4e7ed;">
        <h3 style="margin: 0; font-size: 16px; display: flex; align-items: center; gap: 8px;">
          <el-icon><Setting /></el-icon>
          管理后台
        </h3>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        style="border-right: none;"
      >
        <el-menu-item index="/admin/exhibits">
          <el-icon><Collection /></el-icon>
          <span>展品管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/tour-paths">
          <el-icon><MapLocation /></el-icon>
          <span>路线管理</span>
        </el-menu-item>
      </el-menu>
    </template>
  </div>
</template>
