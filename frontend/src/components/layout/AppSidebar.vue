<script setup>
import ChatSessionsSidebar from './sidebars/ChatSessionsSidebar.vue'
import ExhibitFilterSidebar from './sidebars/ExhibitFilterSidebar.vue'
import TourPlanSidebar from './sidebars/TourPlanSidebar.vue'
import AdminNavSidebar from './sidebars/AdminNavSidebar.vue'

defineProps({
  type: {
    type: String,
    default: null,
  },
})
</script>

<template>
  <aside class="app-sidebar" data-testid="app-sidebar">
    <ChatSessionsSidebar v-if="type === 'chat-sessions'" />
    <ExhibitFilterSidebar v-else-if="type === 'exhibit-filters'" />
    <TourPlanSidebar v-else-if="type === 'tour-plan'" />
    <AdminNavSidebar v-else-if="type === 'admin-nav'" />
  </aside>
</template>
