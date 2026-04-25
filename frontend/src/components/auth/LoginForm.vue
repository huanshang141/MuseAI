<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import { MuseumButton, MuseumInput } from '../../design-system/components/index.js'
import { useAuth } from '../../composables/useAuth.js'

const emit = defineEmits(['success'])

const { login } = useAuth()

const form = ref({
  email: '',
  password: '',
})

const loading = ref(false)

async function handleLogin() {
  if (!form.value.email || !form.value.password) {
    ElMessage.warning('请输入邮箱和密码')
    return
  }

  loading.value = true
  const result = await login(form.value.email, form.value.password)
  loading.value = false

  if (result.ok) {
    ElMessage.success('登录成功')
    emit('success')
  } else {
    ElMessage.error(result.data?.detail || '登录失败')
  }
}
</script>

<template>
  <el-form :model="form" label-position="top" class="auth-form" @submit.prevent="handleLogin">
    <el-form-item label="邮箱">
      <MuseumInput v-model="form.email" type="email" placeholder="请输入邮箱" :prefix-icon="User" />
    </el-form-item>

    <el-form-item label="密码">
      <MuseumInput
        v-model="form.password"
        type="password"
        placeholder="请输入密码"
        :prefix-icon="Lock"
        show-password
      />
    </el-form-item>

    <MuseumButton
      variant="primary"
      full-width
      native-type="submit"
      :loading="loading"
      :disabled="loading"
    >
      登录
    </MuseumButton>
  </el-form>
</template>

<style scoped>
.auth-form {
  display: grid;
  gap: 8px;
}
</style>
