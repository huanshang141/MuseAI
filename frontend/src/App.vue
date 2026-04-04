<script setup>
import AppHeader from './components/layout/AppHeader.vue'
import AppSidebar from './components/layout/AppSidebar.vue'
import ChatPanel from './components/ChatPanel.vue'
</script>

<template>
  <div class="app-container">
    <AppHeader />
    <div class="app-body">
      <AppSidebar />
      <div class="app-main">
        <ChatPanel />
      </div>
    </div>
  </div>
</template>

<style>
@import './styles/custom.css';
</style>
