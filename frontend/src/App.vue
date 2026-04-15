<script setup>
import { ref, provide, computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/layout/AppHeader.vue'
import AppSidebar from './components/layout/AppSidebar.vue'
import AuthModal from './components/auth/AuthModal.vue'

const showAuthModal = ref(false)
provide('showAuthModal', (show = true) => {
  showAuthModal.value = show
})

const route = useRoute()
const isTourMode = computed(() => route.path.startsWith('/tour'))
</script>

<template>
  <div class="app-container">
    <AppHeader v-if="!isTourMode" />
    <div class="app-body">
      <AppSidebar v-if="!isTourMode" />
      <div class="app-main" :class="{ 'tour-mode': isTourMode }">
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

.app-main.tour-mode {
  padding: 0;
  background: #1a1a2e;
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
