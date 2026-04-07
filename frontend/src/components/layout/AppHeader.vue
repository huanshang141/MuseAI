<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuth } from '../../composables/useAuth.js'
import AuthModal from '../auth/AuthModal.vue'
import { api } from '../../api/index.js'
import { User, SwitchButton, ChatDotRound, MapLocation, Collection } from '@element-plus/icons-vue'

const route = useRoute()
const { user, isAuthenticated, logout } = useAuth()

// Navigation items
const navItems = [
  { path: '/', title: '智能问答', icon: ChatDotRound, requiresAuth: false },
  { path: '/curator', title: '导览助手', icon: MapLocation, requiresAuth: true },
  { path: '/exhibits', title: '展品浏览', icon: Collection, requiresAuth: true }
]

// Compute active menu index
const activeMenu = computed(() => route.path)

const healthStatus = ref('checking')
const showAuthModal = ref(false)

async function checkHealth() {
  healthStatus.value = 'checking'
  try {
    const result = await api.health()
    healthStatus.value = result.ok ? 'healthy' : 'unhealthy'
  } catch {
    healthStatus.value = 'error'
  }
}

async function handleLogout() {
  await logout()
  checkHealth()
}

onMounted(checkHealth)
</script>

<template>
  <div class="app-header">
    <div class="logo">
      <el-icon class="logo-icon"><Collection /></el-icon>
      <span>MuseAI - 博物馆展品问答助手</span>
    </div>

    <!-- Navigation Menu -->
    <el-menu
      :default-active="activeMenu"
      mode="horizontal"
      :ellipsis="false"
      router
      class="nav-menu"
    >
      <el-menu-item
        v-for="item in navItems"
        :key="item.path"
        :index="item.path"
        :disabled="item.requiresAuth && !isAuthenticated"
      >
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.title }}</span>
      </el-menu-item>
    </el-menu>

    <div style="display: flex; align-items: center; gap: 12px;">
      <el-tag
        :type="healthStatus === 'healthy' ? 'success' : healthStatus === 'checking' ? 'info' : 'danger'"
        size="small"
      >
        {{ healthStatus === 'healthy' ? '服务正常' : healthStatus === 'checking' ? '检测中...' : '服务异常' }}
      </el-tag>

      <!-- User info when authenticated -->
      <template v-if="isAuthenticated">
        <el-dropdown>
          <div style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
            <el-icon><User /></el-icon>
            <span style="font-size: 14px;">{{ user?.email || '用户' }}</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleLogout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>

      <!-- Login button when not authenticated -->
      <template v-else>
        <el-button type="primary" size="small" @click="showAuthModal = true">
          登录 / 注册
        </el-button>
      </template>
    </div>

    <!-- Auth Modal -->
    <AuthModal
      v-model:visible="showAuthModal"
      @success="checkHealth"
    />
  </div>
</template>

<style scoped>
.nav-menu {
  flex: 1;
  border-bottom: none;
  background: transparent;
}

.nav-menu .el-menu-item {
  font-size: 14px;
}

.nav-menu .el-menu-item.is-disabled {
  opacity: 0.5;
}
</style>
