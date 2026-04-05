<script setup>
import { ref } from 'vue'
import { useAuth } from '../../composables/useAuth.js'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const emit = defineEmits(['success', 'switch-to-login'])

const { register } = useAuth()

const form = ref({
  email: '',
  password: '',
  confirmPassword: '',
})

const loading = ref(false)

const passwordRules = [
  { text: '至少8个字符', test: (p) => p.length >= 8 },
  { text: '包含大写字母', test: (p) => /[A-Z]/.test(p) },
  { text: '包含小写字母', test: (p) => /[a-z]/.test(p) },
  { text: '包含数字', test: (p) => /\d/.test(p) },
]

function getPasswordStrength(password) {
  return passwordRules.filter(rule => rule.test(password)).length
}

async function handleRegister() {
  if (!form.value.email || !form.value.password) {
    ElMessage.warning('请填写完整信息')
    return
  }

  if (form.value.password !== form.value.confirmPassword) {
    ElMessage.warning('两次密码输入不一致')
    return
  }

  if (getPasswordStrength(form.value.password) < 4) {
    ElMessage.warning('密码强度不足')
    return
  }

  loading.value = true
  const result = await register(form.value.email, form.value.password)
  loading.value = false

  if (result.ok) {
    ElMessage.success('注册成功，请登录')
    emit('switch-to-login')
  } else {
    ElMessage.error(result.data?.detail || '注册失败')
  }
}
</script>

<template>
  <el-form :model="form" label-position="top" @submit.prevent="handleRegister">
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

    <el-form-item label="确认密码">
      <el-input
        v-model="form.confirmPassword"
        type="password"
        placeholder="请再次输入密码"
        :prefix-icon="Lock"
        show-password
      />
    </el-form-item>

    <!-- Password strength indicator -->
    <div v-if="form.password" style="margin-bottom: 16px;">
      <div style="font-size: 12px; color: #606266; margin-bottom: 8px;">密码要求:</div>
      <div style="display: flex; flex-wrap: wrap; gap: 4px;">
        <el-tag
          v-for="rule in passwordRules"
          :key="rule.text"
          :type="rule.test(form.password) ? 'success' : 'info'"
          size="small"
        >
          {{ rule.text }}
        </el-tag>
      </div>
    </div>

    <el-form-item>
      <el-button
        type="primary"
        :loading="loading"
        style="width: 100%"
        native-type="submit"
      >
        注册
      </el-button>
    </el-form-item>
  </el-form>
</template>
