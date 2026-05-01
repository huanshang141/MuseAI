<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { MuseumCard } from '../../design-system/components/index.js'
import { api } from '../../api/index.js'

const loading = ref(false)
const saving = ref(false)

const interestOptions = [
  { label: '青铜器', value: 'bronze' },
  { label: '书画', value: 'painting' },
  { label: '陶瓷', value: 'ceramics' },
  { label: '玉器', value: 'jade' },
  { label: '金银器', value: 'gold_silver' },
  { label: '雕塑', value: 'sculpture' },
  { label: '古籍', value: 'ancient_books' },
  { label: '织绣', value: 'textiles' },
]

const knowledgeLevels = [
  { label: '入门级', value: 'beginner' },
  { label: '进阶级', value: 'intermediate' },
  { label: '专家级', value: 'expert' },
]

const narrativePreferences = [
  { label: '故事型', value: 'storytelling' },
  { label: '学术型', value: 'academic' },
  { label: '互动型', value: 'interactive' },
]

const profile = ref({
  interests: [],
  knowledge_level: 'beginner',
  narrative_preference: 'storytelling',
  reflection_depth: 3,
})

async function loadProfile() {
  loading.value = true

  try {
    const result = await api.profile.get()

    if (result.ok && result.data) {
      profile.value = {
        interests: result.data.interests || [],
        knowledge_level: result.data.knowledge_level || 'beginner',
        narrative_preference: result.data.narrative_preference || 'storytelling',
        reflection_depth: result.data.reflection_depth || 3,
      }
    } else {
      ElMessage.error('加载个人资料失败: ' + (result.data?.detail || `HTTP ${result.status}`))
    }
  } catch (error) {
    ElMessage.error('加载个人资料失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  saving.value = true

  try {
    const result = await api.profile.update(profile.value)

    if (result.ok) {
      ElMessage.success('个人资料已保存')
    } else {
      ElMessage.error('保存失败: ' + (result.data?.detail || `HTTP ${result.status}`))
    }
  } catch (error) {
    ElMessage.error('保存失败: ' + error.message)
  } finally {
    saving.value = false
  }
}

onMounted(loadProfile)
</script>

<template>
  <div class="profile-settings" v-loading="loading">
    <header class="profile-hero">
      <h1>个人设置</h1>
      <p>告诉我们你的兴趣和叙事偏好，MuseAI 会据此优化问答与导览体验。</p>
    </header>

    <el-form label-position="top" :model="profile" class="profile-form">
      <MuseumCard title="兴趣偏好" subtitle="选择你想优先探索的文物类型">
        <el-form-item label="感兴趣的文物类型">
          <el-checkbox-group v-model="profile.interests" class="interest-group">
            <el-checkbox v-for="option in interestOptions" :key="option.value" :label="option.value">
              {{ option.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </MuseumCard>

      <MuseumCard title="学习层级" subtitle="调整讲解深度和表达方式">
        <el-form-item label="知识水平">
          <el-radio-group v-model="profile.knowledge_level">
            <el-radio v-for="level in knowledgeLevels" :key="level.value" :label="level.value">
              {{ level.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="叙事风格偏好">
          <el-radio-group v-model="profile.narrative_preference">
            <el-radio v-for="preference in narrativePreferences" :key="preference.value" :label="preference.value">
              {{ preference.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
      </MuseumCard>

      <MuseumCard title="反思深度" subtitle="决定导览中的问题挑战强度">
        <el-form-item label="反思深度 ({{ profile.reflection_depth }}/5)">
          <el-slider v-model="profile.reflection_depth" :min="1" :max="5" :step="1" show-stops />
          <div class="slider-labels">
            <span>浅层</span>
            <span>深层</span>
          </div>
        </el-form-item>
      </MuseumCard>

      <div class="profile-actions">
        <el-button
          data-testid="profile-save"
          type="primary"
          :loading="saving"
          @click="saveProfile"
        >
          保存设置
        </el-button>
      </div>
    </el-form>
  </div>
</template>

<style scoped>
.profile-settings {
  max-width: 840px;
  margin: 0 auto;
  padding: 8px 0 24px;
}

.profile-hero h1 {
  margin: 0;
  font-size: clamp(24px, 2.8vw, 32px);
  font-family: var(--font-family-base);
}

.profile-hero p {
  margin: 8px 0 0;
  color: var(--color-text-secondary);
  line-height: 1.7;
  max-width: 620px;
}

.profile-form {
  margin-top: 16px;
  display: grid;
  gap: 16px;
}

.interest-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 5px;
}

.profile-actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 767px) {
  .profile-settings {
    padding-bottom: 12px;
  }

  .profile-actions {
    justify-content: stretch;
  }

  .profile-actions .el-button {
    width: 100%;
  }
}
</style>
