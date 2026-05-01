<script setup>
import { computed, provide, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/layout/AppHeader.vue'
import AppSidebar from './components/layout/AppSidebar.vue'
import AuthModal from './components/auth/AuthModal.vue'
import { AppDrawer } from './design-system/components/index.js'
import { useMediaQuery } from './composables/useMediaQuery.js'

const showAuthModal = ref(false)
provide('showAuthModal', (show = true) => {
  showAuthModal.value = show
})

const route = useRoute()
const isTourRoute = computed(() => route.path.startsWith('/tour'))
const sidebarType = computed(() => route.meta?.sidebar ?? null)
const hasSidebar = computed(() => !!sidebarType.value)

const isMobile = useMediaQuery('(max-width: 767px)')
const isSidebarDrawerOpen = ref(false)

watch(
  () => route.fullPath,
  () => {
    isSidebarDrawerOpen.value = false
  },
)

function toggleSidebarDrawer() {
  if (!hasSidebar.value) return
  isSidebarDrawerOpen.value = !isSidebarDrawerOpen.value
}

function reloadPage() {
  window.location.reload()
}
</script>

<template>
  <div class="app-container">
    <AppHeader
      :show-sidebar-toggle="isMobile && hasSidebar"
      @toggle-sidebar="toggleSidebarDrawer"
    />

    <div class="app-body">
      <AppSidebar v-if="hasSidebar && !isMobile" :type="sidebarType" />

      <AppDrawer
        v-if="hasSidebar && isMobile"
        :open="isSidebarDrawerOpen"
        title="侧边栏"
        @update:open="isSidebarDrawerOpen = $event"
      >
        <AppSidebar :type="sidebarType" />
      </AppDrawer>

      <div class="app-main" :class="{ 'app-main--no-padding': isTourRoute }">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </div>

    <AuthModal v-model:visible="showAuthModal" @success="reloadPage" />
  </div>
</template>

<style>
@import './styles/custom.css';

.app-main {
  overflow: auto;
  padding: var(--space-fluid-md);
  background: var(--color-bg-base);
}

.app-main--no-padding {
  padding: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-slow) var(--ease-default);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 767px) {
  .app-main {
    padding: var(--space-3);
  }
}
</style>
