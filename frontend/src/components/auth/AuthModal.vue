<script setup>
import { computed, ref, watch } from 'vue'
import LoginForm from './LoginForm.vue'
import RegisterForm from './RegisterForm.vue'
import { MuseumButton, MuseumDialog } from '../../design-system/components/index.js'

const visible = defineModel('visible', { type: Boolean, default: false })
const emit = defineEmits(['success'])

const mode = ref('login')

const dialogTitle = computed(() =>
  mode.value === 'login' ? '欢迎回到半坡' : '创建你的导览身份',
)

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

watch(visible, (nextVisible) => {
  if (nextVisible) {
    mode.value = 'login'
  }
})
</script>

<template>
  <MuseumDialog
    v-model:visible="visible"
    :title="dialogTitle"
    width="420px"
    mobile-fullscreen
    :close-on-click-modal="false"
  >
    <LoginForm v-if="mode === 'login'" @success="handleSuccess" />
    <RegisterForm v-else @success="handleSuccess" @switch-to-login="switchToLogin" />

    <div class="switch-row">
      <span v-if="mode === 'login'">
        还没有账号？
        <MuseumButton variant="text" @click="switchToRegister">立即注册</MuseumButton>
      </span>
      <span v-else>
        已有账号？
        <MuseumButton variant="text" @click="switchToLogin">立即登录</MuseumButton>
      </span>
    </div>
  </MuseumDialog>
</template>

<style scoped>
.switch-row {
  margin-top: 8px;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.switch-row .museum-button {
  padding-left: 4px;
}
</style>
