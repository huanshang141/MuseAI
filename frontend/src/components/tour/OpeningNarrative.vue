<script setup>
import { ref, onMounted, computed } from 'vue'
import { useTour } from '../../composables/useTour.js'
import { useTourWorkbench } from '../../composables/useTourWorkbench.js'
import { useTTSPlayer } from '../../composables/useTTSPlayer.js'
import { api } from '../../api/index.js'

const { tourSession, tourStep, fetchHalls, sendTourMessage, streamingContent, chatMessages, loading } = useTour()
const { ttsPreferences } = useTourWorkbench()
const { feedChunk, stop: stopTTS } = useTTSPlayer()

const displayedText = ref('')
const isTyping = ref(true)
const ttsPlaying = ref(false)

const openingTexts = {
  A: '你好，我是本次带你勘探的考古队长。你现在站立的地方，不仅是西安半坡博物馆，更是中国第一座史前遗址博物馆。收起那些走马观花的游览心思吧，在我们脚下，是一座距今6000多年的母系氏族繁荣期村落。从1953年春天在浐河岸边发现它开始，老一辈考古人在这里进行了五次大规模的科学发掘，揭露面积整整达到1万平方米。直到今天，馆内依然保留着未发掘的探方。带好你的求知欲，跟紧我的脚步，我们马上进入这片国家一级遗址的核心区，用文物和地层数据说话。',
  B: '哎呀，稀客稀客！欢迎来到我的家——浐河边的半坡村。听说你们现在管这里叫"国家AAAA级景区"？哈哈，太客气了。对我来说，这里就是我们部落六千年前生息繁衍的地方。那时候，可是我们女人当家作主的母系氏族哦！我刚刚看了你们的历书，说是从1953年起，你们花了整整四年时间，扒开了这1万平方米的泥土，把我当年用过的陶罐和住过的房子都挖出来了。走吧，远道而来的朋友，去看看我现在被装在玻璃柜里的"家"，我讲给你听当年的故事。',
  C: '各位同学，欢迎来到西安半坡博物馆！导览开始前，老师先考考大家：你们知道中国"第一座"史前遗址博物馆是哪里吗？没错，就是我们脚下！请大家闭上眼睛想象一下，如果把时间往前推六千年，回到那个繁荣的母系氏族社会，生活在浐河岸边的先民们，每天都在忙些什么呢？自1958年建馆以来，这里展出了1万平方米的真实发掘现场。但在咱们今天的游览中，老师希望大家不仅要看那些已经出土的丰富遗存，更要留意那些"未发掘"的神秘区域。准备好开启今天的历史寻宝了吗？我们出发！',
}

const fullText = computed(() => openingTexts[tourSession.value?.persona] || openingTexts.A)

onMounted(() => {
  let index = 0
  const timer = setInterval(() => {
    if (index < fullText.value.length) {
      displayedText.value += fullText.value[index]
      index++
    } else {
      isTyping.value = false
      clearInterval(timer)
      // Auto-play TTS when typewriter finishes
      if (ttsPreferences.value.enabled) {
        playOpeningTTS()
      }
    }
  }, 30)
})

async function playOpeningTTS() {
  if (ttsPlaying.value) {
    stopTTS()
    ttsPlaying.value = false
    return
  }

  ttsPlaying.value = true
  try {
    const persona = tourSession.value?.persona || 'A'
    const result = await api.tts.synthesize(fullText.value, null, null, persona)
    if (result.ok && result.data?.audio) {
      stopTTS()
      feedChunk(result.data.audio)
      ttsPlaying.value = false
    } else {
      ttsPlaying.value = false
    }
  } catch (err) {
    console.error('Opening TTS error:', err)
    ttsPlaying.value = false
  }
}

async function startExplore() {
  await fetchHalls()
  tourStep.value = 'hall-select'
}
</script>

<template>
  <div class="opening">
    <div class="opening-inner">
      <div class="persona-badge">
        {{ tourSession?.persona === 'B' ? '🏠 半坡原住民' : tourSession?.persona === 'C' ? '📚 历史老师' : '⛏️ 考古队长' }}
      </div>
      <button
        v-if="!isTyping && ttsPreferences.enabled"
        class="tts-play-btn"
        :class="{ playing: ttsPlaying }"
        title="语音播放"
        @click="playOpeningTTS"
      >
        <svg v-if="!ttsPlaying" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
        <span>{{ ttsPlaying ? '暂停' : '播放' }}</span>
      </button>
      <div class="narrative-text">
        {{ displayedText }}
        <span v-if="isTyping" class="cursor">|</span>
      </div>
      <el-button
        v-if="!isTyping"
        type="primary"
        size="large"
        class="start-btn"
        @click="startExplore"
      >
        开始探索 →
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.opening {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100%;
  padding: 40px 20px;
}

.opening-inner {
  max-width: 640px;
  width: 100%;
  text-align: center;
}

.persona-badge {
  display: inline-block;
  padding: 8px 24px;
  background: var(--color-accent-muted);
  border: 1px solid var(--color-accent);
  border-radius: 20px;
  color: var(--color-accent);
  font-size: 16px;
  margin-bottom: 32px;
}

.narrative-text {
  font-size: 17px;
  line-height: 2;
  text-align: left;
  color: var(--color-text-primary);
  white-space: pre-wrap;
}

.cursor {
  animation: blink 0.8s infinite;
  color: var(--color-accent);
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.start-btn {
  margin-top: 40px;
  padding: 14px 48px;
  font-size: 18px;
  border-radius: 24px;
  background: var(--color-accent);
  border-color: var(--color-accent);
}

.start-btn:hover {
  background: var(--color-accent-soft);
}

.tts-play-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  margin-bottom: 24px;
  background: var(--color-accent-muted);
  border: 1px solid var(--color-accent);
  border-radius: 20px;
  color: var(--color-accent);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.tts-play-btn:hover {
  background: var(--color-accent-muted);
  border-color: var(--color-accent);
}

.tts-play-btn.playing {
  background: var(--color-accent-muted);
  border-color: var(--color-accent);
}
</style>
