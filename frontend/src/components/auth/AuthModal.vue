<script setup>
import { ref } from 'vue'
import LoginForm from './LoginForm.vue'
import RegisterForm from './RegisterForm.vue'

const visible = defineModel('visible', { type: Boolean, default: false })
const emit = defineEmits(['success'])

const mode = ref('login') // 'login' or 'register'

function handleSuccess() {
  emit('success')
  visible.value = false
}

function switchToRegister() {
  mode.value = 'register'
}

function switchToLogin() {
  mode.value = 'login'
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="mode === 'login' ? '登录' : '注册'"
    width="400px"
    :close-on-click-modal="false"
  >
    <LoginForm
      v-if="mode === 'login'"
      @success="handleSuccess"
    />
    <RegisterForm
      v-else
      @success="handleSuccess"
      @switch-to-login="switchToLogin"
    />

    <div style="text-align: center; margin-top: 16px;">
      <span v-if="mode === 'login'" style="color: #606266; font-size: 14px;">
        还没有账号？
        <el-link type="primary" @click="switchToRegister">立即注册</el-link>
      </span>
      <span v-else style="color: #606266; font-size: 14px;">
        已有账号？
        <el-link type="primary" @click="switchToLogin">立即登录</el-link>
      </span>
    </div>
  </el-dialog>
</template>
