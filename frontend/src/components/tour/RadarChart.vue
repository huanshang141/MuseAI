<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({
  scores: Object,
})

const canvasRef = ref(null)

const dimensions = [
  { key: 'civilization_resonance', label: '文明共鸣度' },
  { key: 'imagination_breadth', label: '脑洞广度' },
  { key: 'history_collection', label: '历史碎片' },
  { key: 'life_experience', label: '生活体验' },
  { key: 'ceramic_aesthetics', label: '彩陶审美' },
]

function drawChart() {
  const canvas = canvasRef.value
  if (!canvas || !props.scores) return

  const ctx = canvas.getContext('2d')
  const w = canvas.width = canvas.offsetWidth * 2
  const h = canvas.height = canvas.offsetHeight * 2
  ctx.scale(2, 2)
  const cw = canvas.offsetWidth
  const ch = canvas.offsetHeight
  const cx = cw / 2
  const cy = ch / 2
  const maxR = Math.min(cx, cy) - 40

  ctx.clearRect(0, 0, cw, ch)

  const n = dimensions.length
  const angleStep = (Math.PI * 2) / n

  for (let level = 1; level <= 3; level++) {
    const r = (maxR * level) / 3
    ctx.beginPath()
    for (let i = 0; i <= n; i++) {
      const angle = i * angleStep - Math.PI / 2
      const x = cx + r * Math.cos(angle)
      const y = cy + r * Math.sin(angle)
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)'
    ctx.stroke()
  }

  for (let i = 0; i < n; i++) {
    const angle = i * angleStep - Math.PI / 2
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.lineTo(cx + maxR * Math.cos(angle), cy + maxR * Math.sin(angle))
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)'
    ctx.stroke()

    const labelR = maxR + 20
    const lx = cx + labelR * Math.cos(angle)
    const ly = cy + labelR * Math.sin(angle)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.6)'
    ctx.font = '12px sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(dimensions[i].label, lx, ly)
  }

  ctx.beginPath()
  for (let i = 0; i <= n; i++) {
    const idx = i % n
    const score = props.scores[dimensions[idx].key] || 1
    const r = (maxR * score) / 3
    const angle = idx * angleStep - Math.PI / 2
    const x = cx + r * Math.cos(angle)
    const y = cy + r * Math.sin(angle)
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  }
  ctx.fillStyle = 'rgba(212, 165, 116, 0.2)'
  ctx.fill()
  ctx.strokeStyle = '#d4a574'
  ctx.lineWidth = 2
  ctx.stroke()

  for (let i = 0; i < n; i++) {
    const score = props.scores[dimensions[i].key] || 1
    const r = (maxR * score) / 3
    const angle = i * angleStep - Math.PI / 2
    const x = cx + r * Math.cos(angle)
    const y = cy + r * Math.sin(angle)
    ctx.beginPath()
    ctx.arc(x, y, 4, 0, Math.PI * 2)
    ctx.fillStyle = '#d4a574'
    ctx.fill()
  }
}

onMounted(drawChart)
watch(() => props.scores, drawChart, { deep: true })
</script>

<template>
  <div class="radar-chart">
    <h3 class="section-title">游览五型图</h3>
    <canvas ref="canvasRef" class="chart-canvas" />
    <div class="level-legend">
      <span>B级</span><span>A级</span><span>S级</span>
    </div>
  </div>
</template>

<style scoped>
.radar-chart {
  margin-bottom: 32px;
  text-align: center;
}

.section-title {
  font-size: 18px;
  color: #f0e6d3;
  margin-bottom: 16px;
}

.chart-canvas {
  width: 300px;
  height: 300px;
  margin: 0 auto;
  display: block;
}

.level-legend {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-top: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
}
</style>
