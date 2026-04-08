<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
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
  } catch (err) {
    ElMessage.error('加载个人资料失败: ' + err.message)
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
  } catch (err) {
    ElMessage.error('保存失败: ' + err.message)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadProfile()
})
</script>

<template>
  <div class="profile-settings">
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>个人偏好设置</span>
        </div>
      </template>

      <el-form label-position="top" :model="profile">
        <!-- Interest Tags -->
        <el-form-item label="感兴趣的文物类型">
          <el-checkbox-group v-model="profile.interests">
            <el-checkbox
              v-for="option in interestOptions"
              :key="option.value"
              :label="option.value"
            >
              {{ option.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <!-- Knowledge Level -->
        <el-form-item label="知识水平">
          <el-radio-group v-model="profile.knowledge_level">
            <el-radio
              v-for="level in knowledgeLevels"
              :key="level.value"
              :label="level.value"
            >
              {{ level.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- Narrative Preference -->
        <el-form-item label="叙事风格偏好">
          <el-radio-group v-model="profile.narrative_preference">
            <el-radio
              v-for="pref in narrativePreferences"
              :key="pref.value"
              :label="pref.value"
            >
              {{ pref.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- Reflection Depth -->
        <el-form-item label="反思深度 ({{ profile.reflection_depth }}/5)">
          <el-slider
            v-model="profile.reflection_depth"
            :min="1"
            :max="5"
            :step="1"
            show-stops
          />
          <div class="slider-labels">
            <span>浅层</span>
            <span>深层</span>
          </div>
        </el-form-item>

        <!-- Save Button -->
        <el-form-item>
          <el-button
            type="primary"
            :loading="saving"
            @click="saveProfile"
          >
            保存设置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.profile-settings {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
}

.card-header {
  font-size: 18px;
  font-weight: bold;
}

.el-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.el-checkbox {
  margin-right: 0;
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}
</style>
