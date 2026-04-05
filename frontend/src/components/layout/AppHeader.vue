<script setup>
import { ref, onMounted } from 'vue'
import { useAuth } from '../../composables/useAuth.js'
import AuthModal from '../auth/AuthModal.vue'
import { api } from '../../api/index.js'
import { User, SwitchButton } from '@element-plus/icons-vue'

const { user, isAuthenticated, logout } = useAuth()

const healthStatus = ref('checking')
const showAuthModal = ref(false)

async function checkHealth() {
  healthStatus.value = 'checking'
  try {
    const result = await api.health()
    healthStatus.value = result.ok ? 'healthy' : 'unhealthy'
  } catch (error) {
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
