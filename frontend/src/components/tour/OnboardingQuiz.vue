<script setup>
import { ref } from 'vue'
import { useTour } from '../../composables/useTour.js'

const { createTourSession, tourStep } = useTour()

const currentQuestion = ref(0)
const answers = ref({ interest_type: null, persona: null, assumption: null })
const loading = ref(false)

const questions = [
  {
    key: 'interest_type',
    title: '如果你穿越回了6000年前的半坡，你第一件想搞清楚的事是？',
    options: [
      { value: 'A', label: '半坡人平时吃什么？房屋如何构建？', desc: '生存与技术' },
      { value: 'B', label: '陶器上那些诡异的人面鱼纹到底象征着什么？', desc: '符号与艺术' },
      { value: 'C', label: '谁是首领？打来的猎物怎么分？', desc: '社会与权力' },
    ],
  },
  {
    key: 'persona',
    title: '接下来的半个小时，你希望陪你逛展的AI导览员是什么人设？',
    options: [
      { value: 'A', label: '严谨求实的考古队长', desc: '硬核发掘数据与学术推论' },
      { value: 'B', label: '穿越来的半坡原住民', desc: '村民视角的第一人称沉浸' },
      { value: 'C', label: '爱提问的历史老师', desc: '多观点引导思考' },
    ],
  },
  {
    key: 'assumption',
    title: '凭直觉，你认为6000年前的原始社会更接近哪种状态？',
    options: [
      { value: 'A', label: '没有压迫，人人平等的纯真年代', desc: '' },
      { value: 'B', label: '饥寒交迫的荒野求生', desc: '' },
      { value: 'C', label: '已经出现贫富分化和阶级的雏形', desc: '' },
    ],
  },
]

async function selectOption(value) {
  const q = questions[currentQuestion.value]
  answers.value[q.key] = value

  if (currentQuestion.value < questions.length - 1) {
    currentQuestion.value++
  } else {
    loading.value = true
    const session = await createTourSession(
      answers.value.interest_type,
      answers.value.persona,
      answers.value.assumption,
    )
    loading.value = false
    if (session) {
      tourStep.value = 'opening'
    }
  }
}
</script>

<template>
  <div class="onboarding">
    <div class="onboarding-inner">
      <div class="progress">
        <span v-for="i in 3" :key="i" class="dot" :class="{ active: i <= currentQuestion + 1, done: i < currentQuestion + 1 }" />
      </div>

      <transition name="fade" mode="out-in">
        <div :key="currentQuestion" class="question-card">
          <h2 class="question-title">{{ questions[currentQuestion].title }}</h2>
          <div class="options">
            <div
              v-for="opt in questions[currentQuestion].options"
              :key="opt.value"
              class="option-card"
              @click="selectOption(opt.value)"
            >
              <span class="option-letter">{{ opt.value }}</span>
              <div class="option-content">
                <span class="option-label">{{ opt.label }}</span>
                <span v-if="opt.desc" class="option-desc">{{ opt.desc }}</span>
              </div>
            </div>
          </div>
        </div>
      </transition>

      <div v-if="loading" class="loading-overlay">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <span>正在为你准备专属导览...</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.onboarding {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100%;
  padding: 40px 20px;
}

.onboarding-inner {
  max-width: 640px;
  width: 100%;
}

.progress {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 40px;
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  transition: all 0.3s;
}

.dot.active {
  background: #d4a574;
}

.dot.done {
  background: #8fbc8f;
}

.question-card {
  text-align: center;
}

.question-title {
  font-size: 22px;
  line-height: 1.6;
  margin-bottom: 32px;
  color: #f0e6d3;
}

.options {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.option-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.option-card:hover {
  background: rgba(212, 165, 116, 0.15);
  border-color: #d4a574;
  transform: translateX(4px);
}

.option-letter {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(212, 165, 116, 0.2);
  color: #d4a574;
  font-weight: 700;
  font-size: 16px;
  flex-shrink: 0;
}

.option-content {
  display: flex;
  flex-direction: column;
  text-align: left;
}

.option-label {
  font-size: 16px;
  line-height: 1.5;
}

.option-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 4px;
}

.loading-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: rgba(26, 26, 46, 0.9);
  z-index: 100;
  color: #d4a574;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
