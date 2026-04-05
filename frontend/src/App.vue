<script setup>
import { ref, provide } from 'vue'
import AppHeader from './components/layout/AppHeader.vue'
import AppSidebar from './components/layout/AppSidebar.vue'
import ChatPanel from './components/ChatPanel.vue'
import AuthModal from './components/auth/AuthModal.vue'
import { useAuth } from './composables/useAuth.js'

const { isAuthenticated } = useAuth()

// Global auth modal state
const showAuthModal = ref(false)

// Provide a function to show auth modal from any component
provide('showAuthModal', (show = true) => {
  showAuthModal.value = show
})
</script>

<template>
  <div class="app-container">
    <AppHeader />
    <div class="app-body">
      <AppSidebar />
      <div class="app-main">
        <!-- Show auth required message if not authenticated -->
        <div v-if="!isAuthenticated" class="auth-required-notice">
          <el-empty description="请先登录以使用完整功能">
            <el-button type="primary" @click="showAuthModal = true">
              立即登录
            </el-button>
          </el-empty>
        </div>
        <!-- Show main content when authenticated -->
        <ChatPanel v-else />
      </div>
    </div>

    <!-- Global Auth Modal -->
    <AuthModal v-model:visible="showAuthModal" />
  </div>
</template>

<style>
@import './styles/custom.css';

.auth-required-notice {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 400px;
}
</style>
