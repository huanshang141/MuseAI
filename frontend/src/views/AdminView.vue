<script setup>
import { Collection, MapLocation } from '@element-plus/icons-vue'
</script>

<template>
  <div class="admin-view">
    <el-container>
      <el-aside width="200px">
        <el-menu
          :default-active="$route.path"
          router
          class="admin-menu"
        >
          <el-menu-item index="/admin/exhibits">
            <el-icon><Collection /></el-icon>
            <span>展品管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/tour-paths">
            <el-icon><MapLocation /></el-icon>
            <span>路线管理</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<style scoped>
.admin-view {
  height: 100%;
}

.admin-menu {
  height: 100%;
  border-right: none;
}
</style>
