<script setup>
import ChatPanel from '../components/ChatPanel.vue'
import { Compass } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

const router = useRouter()

function startTour() {
  router.push('/tour')
}
</script>

<template>
  <div class="home-view">
    <div class="tour-banner" @click="startTour">
      <div class="banner-content">
        <el-icon class="banner-icon"><Compass /></el-icon>
        <div class="banner-text">
          <h3>半坡博物馆 AI 智能导览</h3>
          <p>选择你的导览身份，开启沉浸式博物馆之旅</p>
        </div>
      </div>
      <el-button type="warning" round>
        开始导览
      </el-button>
    </div>
    <ChatPanel />
  </div>
</template>

<style scoped>
.home-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.tour-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  margin-bottom: 16px;
  background: linear-gradient(135deg, #2c1810 0%, #5a3a28 100%);
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.tour-banner:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(44, 24, 16, 0.3);
}

.banner-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.banner-icon {
  font-size: 36px;
  color: #d4a574;
}

.banner-text h3 {
  margin: 0;
  font-size: 16px;
  color: #f0e6d3;
  font-weight: 600;
}

.banner-text p {
  margin: 4px 0 0;
  font-size: 13px;
  color: rgba(240, 230, 211, 0.7);
}
</style>
