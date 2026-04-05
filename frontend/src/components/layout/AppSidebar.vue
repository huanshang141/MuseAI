<script setup>
import DocumentUpload from '../knowledge/DocumentUpload.vue'
import DocumentList from '../knowledge/DocumentList.vue'
import { useAuth } from '../../composables/useAuth.js'
import { inject } from 'vue'

const { isAuthenticated } = useAuth()
const showAuthModal = inject('showAuthModal')
</script>

<template>
  <div class="app-sidebar">
    <div style="padding: 16px; border-bottom: 1px solid #e4e7ed;">
      <h3 style="margin: 0; font-size: 16px;">知识库管理</h3>
    </div>

    <!-- Show documents when authenticated -->
    <template v-if="isAuthenticated">
      <DocumentUpload />
      <DocumentList />
    </template>

    <!-- Show login prompt when not authenticated -->
    <template v-else>
      <div style="padding: 20px; text-align: center; color: #909399;">
        <el-empty description="请先登录" :image-size="80" />
        <el-button type="primary" size="small" @click="showAuthModal(true)" style="margin-top: 12px;">
          登录
        </el-button>
      </div>
    </template>
  </div>
</template>
