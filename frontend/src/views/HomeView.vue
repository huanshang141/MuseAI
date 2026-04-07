<script setup>
import ChatPanel from '../components/ChatPanel.vue'
import { useAuth } from '../composables/useAuth.js'
import { inject } from 'vue'

const { isAuthenticated } = useAuth()
const showAuthModal = inject('showAuthModal')
</script>

<template>
  <div class="home-view">
    <!-- Show auth required message if not authenticated -->
    <div v-if="!isAuthenticated" class="auth-required-notice">
      <el-empty description="请先登录以使用完整功能">
        <el-button type="primary" @click="showAuthModal(true)">
          立即登录
        </el-button>
      </el-empty>
    </div>
    <!-- Show main content when authenticated -->
    <ChatPanel v-else />
  </div>
</template>

<style scoped>
.home-view {
  height: 100%;
}

.auth-required-notice {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 400px;
}
</style>
