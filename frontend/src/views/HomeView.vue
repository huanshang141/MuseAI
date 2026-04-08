<script setup>
import ChatPanel from '../components/ChatPanel.vue'
</script>

<template>
  <div class="home-view">
    <!-- ChatPanel works for both guests and authenticated users -->
    <ChatPanel />
  </div>
</template>

<style scoped>
.home-view {
  height: 100%;
}
</style>
