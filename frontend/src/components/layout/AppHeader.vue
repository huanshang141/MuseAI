<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  ChatDotRound,
  Collection,
  Compass,
  MapLocation,
  Menu,
  Setting,
  SwitchButton,
  User,
} from '@element-plus/icons-vue'
import { api } from '../../api/index.js'
import { useAuth } from '../../composables/useAuth.js'
import { FishFaceSymbol } from '../../design-system/motifs/index.js'

defineProps({
  showSidebarToggle: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['toggle-sidebar'])

const showAuthModal = inject('showAuthModal', () => {})
const route = useRoute()
const { user, isAuthenticated, isAdmin, logout } = useAuth()

const navItems = [
  { path: '/', title: '工作台', icon: ChatDotRound, requiresAuth: false },
  { path: '/tour', title: 'AI 导览', icon: Compass, requiresAuth: false },
  { path: '/curator', title: '导览助手', icon: MapLocation, requiresAuth: true },
  { path: '/exhibits', title: '展品浏览', icon: Collection, requiresAuth: true },
  { path: '/admin', title: '管理后台', icon: Setting, requiresAuth: true, requiresAdmin: true },
]

const activeMenu = computed(() => {
  if (route.path.startsWith('/admin')) return '/admin'
  return route.path
})
const healthStatus = ref('checking')

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
  window.location.reload()
}

function handleLoginClick() {
  showAuthModal(true)
}

onMounted(checkHealth)
</script>

<template>
  <header class="app-header">
    <div class="header-left">
      <el-button
        v-if="showSidebarToggle"
        text
        class="sidebar-toggle"
        data-testid="sidebar-toggle"
        @click="emit('toggle-sidebar')"
      >
        <el-icon><Menu /></el-icon>
      </el-button>

      <div class="logo">
        <FishFaceSymbol :size="28" class="logo-mark" aria-label="MuseAI Logo" />
        <span class="logo-title">MuseAI · 半坡博物馆</span>
      </div>
    </div>

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
        v-show="!item.requiresAdmin || isAdmin"
        :disabled="item.requiresAuth && !isAuthenticated"
      >
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.title }}</span>
      </el-menu-item>
    </el-menu>

    <div class="header-actions">
      <el-tag
        :type="healthStatus === 'healthy' ? 'success' : healthStatus === 'checking' ? 'info' : 'danger'"
        size="small"
      >
        {{ healthStatus === 'healthy' ? '服务正常' : healthStatus === 'checking' ? '检测中...' : '服务异常' }}
      </el-tag>

      <template v-if="isAuthenticated">
        <el-dropdown>
          <div class="user-trigger">
            <el-icon><User /></el-icon>
            <span class="user-text">{{ user?.email || '用户' }}</span>
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

      <template v-else>
        <el-button type="primary" size="small" @click="handleLoginClick">
          登录 / 注册
        </el-button>
      </template>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-3);
  min-height: 64px;
  padding: 0 var(--space-5);
  border-bottom: 1px solid rgba(77, 51, 31, 0.08);
  background: rgba(255, 252, 247, 0.96);
  backdrop-filter: blur(12px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.nav-menu {
  min-width: 0;
  border-bottom: none;
  background: transparent;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  white-space: nowrap;
}

.logo-mark {
  flex: 0 0 auto;
  color: var(--color-accent);
}

.logo-title {
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: var(--font-family-base);
  font-weight: var(--font-weight-semibold);
  letter-spacing: 0;
}

.nav-menu .el-menu-item {
  font-size: var(--font-size-body);
}

.nav-menu .el-menu-item.is-disabled {
  opacity: 0.5;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
}

.user-text {
  font-size: var(--font-size-body);
}

.sidebar-toggle {
  color: var(--color-text-primary);
}

@media (max-width: 900px) {
  .app-header {
    grid-template-columns: auto 1fr;
    gap: var(--space-2);
    padding: 0 var(--space-3);
  }

  .nav-menu {
    display: none;
  }

  .header-actions {
    justify-content: flex-end;
  }
}

@media (max-width: 767px) {
  .logo-title {
    max-width: 160px;
    font-size: var(--font-size-body);
  }

  .header-actions .el-tag {
    display: none;
  }

  .user-text {
    display: none;
  }
}
</style>
