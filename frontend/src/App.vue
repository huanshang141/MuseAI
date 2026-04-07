<script setup>
import { ref, provide } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/layout/AppHeader.vue'
import AppSidebar from './components/layout/AppSidebar.vue'
import AuthModal from './components/auth/AuthModal.vue'
import { useAuth } from './composables/useAuth.js'

const route = useRoute()
const { isAuthenticated } = useAuth()

const showAuthModal = ref(false)
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
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </div>
    <AuthModal v-model:visible="showAuthModal" />
  </div>
</template>

<style>
@import './styles/custom.css';

.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.app-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.app-main {
  flex: 1;
  overflow: auto;
  padding: 20px;
  background: #f5f7fa;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
