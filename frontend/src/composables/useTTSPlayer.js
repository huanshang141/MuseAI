import { ref } from 'vue'

export function useTTSPlayer() {
  const isPlaying = ref(false)

  let audioContext = null
  let scheduledEndTime = 0
  let currentSources = []

  function initContext() {
    if (!audioContext) {
      audioContext = new AudioContext({ sampleRate: 24000 })
    }
  }

  function feedChunk(base64Chunk) {
    if (!base64Chunk) return
    initContext()

    if (audioContext.state === 'suspended') {
      audioContext.resume()
    }

    // Decode base64 -> Int16 -> Float32
    const raw = atob(base64Chunk)
    const int16 = new Int16Array(raw.length / 2)
    for (let i = 0; i < int16.length; i++) {
      int16[i] = (raw.charCodeAt(i * 2 + 1) << 8) | raw.charCodeAt(i * 2)
    }
    const float32 = Float32Array.from(int16, (v) => v / 32768)

    // Create AudioBuffer and schedule gapless playback
    const buffer = audioContext.createBuffer(1, float32.length, 24000)
    buffer.getChannelData(0).set(float32)
    const source = audioContext.createBufferSource()
    source.buffer = buffer
    source.connect(audioContext.destination)

    const startTime = Math.max(audioContext.currentTime, scheduledEndTime)
    source.start(startTime)
    scheduledEndTime = startTime + buffer.duration

    currentSources.push(source)
    source.onended = () => {
      currentSources = currentSources.filter((s) => s !== source)
      if (currentSources.length === 0) {
        isPlaying.value = false
      }
    }
    isPlaying.value = true
  }

  function stop() {
    for (const source of currentSources) {
      try {
        source.stop()
      } catch { /* source may already be stopped */ }
    }
    currentSources = []
    isPlaying.value = false
    scheduledEndTime = 0
  }

  return { isPlaying, feedChunk, stop }
}
