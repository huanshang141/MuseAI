<script setup>
import { useTourWorkbench } from '../../../composables/useTourWorkbench.js'

const { uiPreferences, stylePreferences, ttsPreferences, resetPreferences } = useTourWorkbench()

const fontScaleOptions = [
  { label: '小', value: 'sm' },
  { label: '中', value: 'md' },
  { label: '大', value: 'lg' },
]

const densityOptions = [
  { label: '紧凑', value: 'compact' },
  { label: '舒适', value: 'comfortable' },
]

const answerLengthOptions = [
  { label: '简短', value: 'brief' },
  { label: '适中', value: 'balanced' },
  { label: '详细', value: 'detailed' },
]

const depthOptions = [
  { label: '入门', value: 'introductory' },
  { label: '标准', value: 'standard' },
  { label: '深入', value: 'deep' },
]

const terminologyOptions = [
  { label: '通俗', value: 'plain' },
  { label: '专业', value: 'professional' },
  { label: '学术', value: 'academic' },
]
</script>

<template>
  <div class="tour-settings-panel">
    <div class="settings-section">
      <h4 class="settings-heading">界面偏好</h4>

      <div class="settings-row">
        <span class="settings-label">字体大小</span>
        <el-select v-model="uiPreferences.fontScale" size="small">
          <el-option v-for="opt in fontScaleOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </div>

      <div class="settings-row">
        <span class="settings-label">消息密度</span>
        <el-select v-model="uiPreferences.messageDensity" size="small">
          <el-option v-for="opt in densityOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </div>

      <div class="settings-row">
        <span class="settings-label">自动滚动</span>
        <el-switch v-model="uiPreferences.autoScroll" />
      </div>

      <div class="settings-row">
        <span class="settings-label">快捷提问</span>
        <el-switch v-model="uiPreferences.showQuickPrompts" />
      </div>

      <div class="settings-row">
        <span class="settings-label">草稿记忆</span>
        <el-switch v-model="uiPreferences.rememberDraft" />
      </div>
    </div>

    <div class="settings-section">
      <h4 class="settings-heading">风格偏好</h4>

      <div class="settings-row">
        <span class="settings-label">启用风格</span>
        <el-switch v-model="stylePreferences.enabled" />
      </div>

      <div class="settings-row">
        <span class="settings-label">回答长度</span>
        <el-select v-model="stylePreferences.answerLength" size="small" :disabled="!stylePreferences.enabled">
          <el-option v-for="opt in answerLengthOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </div>

      <div class="settings-row">
        <span class="settings-label">讲解深浅</span>
        <el-select v-model="stylePreferences.depth" size="small" :disabled="!stylePreferences.enabled">
          <el-option v-for="opt in depthOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </div>

      <div class="settings-row">
        <span class="settings-label">术语难度</span>
        <el-select v-model="stylePreferences.terminology" size="small" :disabled="!stylePreferences.enabled">
          <el-option v-for="opt in terminologyOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </div>
    </div>

    <div class="settings-section tts-section">
      <h4 class="settings-heading">语音朗读</h4>
      <div class="settings-row">
        <span class="settings-label">启用语音朗读</span>
        <el-switch v-model="ttsPreferences.enabled" />
      </div>
      <div class="settings-row" v-if="ttsPreferences.enabled">
        <span class="settings-label">自动播放</span>
        <el-switch v-model="ttsPreferences.autoPlay" />
      </div>
      <div class="settings-row" v-if="ttsPreferences.enabled">
        <span class="settings-label">音色</span>
        <el-select v-model="ttsPreferences.voice" size="small">
          <el-option label="冰糖 (女)" value="冰糖" />
          <el-option label="茉莉 (女)" value="茉莉" />
          <el-option label="苏打 (男)" value="苏打" />
          <el-option label="白桦 (男)" value="白桦" />
          <el-option label="Mia (EN/F)" value="Mia" />
          <el-option label="Chloe (EN/F)" value="Chloe" />
          <el-option label="Milo (EN/M)" value="Milo" />
          <el-option label="Dean (EN/M)" value="Dean" />
        </el-select>
      </div>
    </div>

    <div class="settings-section">
      <el-button data-testid="reset-prefs-btn" @click="resetPreferences">
        恢复默认设置
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.tour-settings-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.settings-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.settings-heading {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary, #2a2420);
  padding-bottom: 4px;
  border-bottom: 1px solid var(--color-border, #d9c9a8);
}

.settings-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.settings-label {
  color: var(--color-text-secondary, #5a5248);
}
</style>
