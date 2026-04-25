<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import { MuseumButton, MuseumInput } from '../../design-system/components/index.js'
import { useAuth } from '../../composables/useAuth.js'

const emit = defineEmits(['success', 'switch-to-login'])

const { register } = useAuth()

const form = ref({
  email: '',
  password: '',
  confirmPassword: '',
})

const loading = ref(false)

const passwordRules = [
  { text: '至少8个字符', test: (password) => password.length >= 8 },
  { text: '包含大写字母', test: (password) => /[A-Z]/.test(password) },
  { text: '包含小写字母', test: (password) => /[a-z]/.test(password) },
  { text: '包含数字', test: (password) => /\d/.test(password) },
]

function getPasswordStrength(password) {
  return passwordRules.filter((rule) => rule.test(password)).length
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
  <el-form :model="form" label-position="top" class="auth-form" @submit.prevent="handleRegister">
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

    <el-form-item label="确认密码">
      <MuseumInput
        v-model="form.confirmPassword"
        type="password"
        placeholder="请再次输入密码"
        :prefix-icon="Lock"
        show-password
      />
    </el-form-item>

    <div v-if="form.password" class="password-rules">
      <div class="rules-title">密码要求:</div>
      <div class="rule-tags">
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

    <MuseumButton
      variant="primary"
      full-width
      native-type="submit"
      :loading="loading"
      :disabled="loading"
    >
      注册
    </MuseumButton>
  </el-form>
</template>

<style scoped>
.auth-form {
  display: grid;
  gap: 8px;
}

.password-rules {
  margin-bottom: 4px;
}

.rules-title {
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.rule-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
