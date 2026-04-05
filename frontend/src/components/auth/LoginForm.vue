<script setup>
import { ref } from 'vue'
import { useAuth } from '../../composables/useAuth.js'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

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
  <el-form :model="form" label-position="top" @submit.prevent="handleLogin">
    <el-form-item label="邮箱">
      <el-input
        v-model="form.email"
        type="email"
        placeholder="请输入邮箱"
        :prefix-icon="User"
      />
    </el-form-item>

    <el-form-item label="密码">
      <el-input
        v-model="form.password"
        type="password"
        placeholder="请输入密码"
        :prefix-icon="Lock"
        show-password
      />
    </el-form-item>

    <el-form-item>
      <el-button
        type="primary"
        :loading="loading"
        style="width: 100%"
        native-type="submit"
      >
        登录
      </el-button>
    </el-form-item>
  </el-form>
</template>
