import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useTTSPlayer } from '../useTTSPlayer.js'

// Mock AudioContext
const mockConnect = vi.fn()
const mockStart = vi.fn()
const mockStop = vi.fn()
const mockDestination = {}

const mockBufferSource = {
  buffer: null,
  connect: mockConnect,
  start: mockStart,
  stop: mockStop,
  onended: null,
}

class MockAudioContext {
  constructor() {
    this.currentTime = 0
    this.destination = mockDestination
    this.sampleRate = 24000
  }
  createBuffer(channels, length, sampleRate) {
    return {
      getChannelData: () => new Float32Array(length),
      duration: length / sampleRate,
    }
  }
  createBufferSource() {
    return { ...mockBufferSource, connect: mockConnect, start: mockStart, stop: mockStop, onended: null }
  }
}

describe('useTTSPlayer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.AudioContext = MockAudioContext
  })

  it('initializes with isPlaying false', () => {
    const { isPlaying } = useTTSPlayer()
    expect(isPlaying.value).toBe(false)
  })

  it('feedChunk schedules audio playback', () => {
    const { feedChunk, isPlaying } = useTTSPlayer()

    // Create a simple PCM16 base64 chunk (2 samples)
    const int16 = new Int16Array([16000, -16000])
    const bytes = new Uint8Array(int16.buffer)
    const base64 = btoa(String.fromCharCode(...bytes))

    feedChunk(base64)
    expect(isPlaying.value).toBe(true)
    expect(mockStart).toHaveBeenCalled()
  })

  it('stop resets state', () => {
    const { feedChunk, stop, isPlaying } = useTTSPlayer()

    const int16 = new Int16Array([16000])
    const bytes = new Uint8Array(int16.buffer)
    const base64 = btoa(String.fromCharCode(...bytes))

    feedChunk(base64)
    stop()
    expect(isPlaying.value).toBe(false)
  })

  it('feedChunk with empty string does nothing', () => {
    const { feedChunk, isPlaying } = useTTSPlayer()

    feedChunk('')
    expect(isPlaying.value).toBe(false)
    expect(mockStart).not.toHaveBeenCalled()
  })

  it('feedChunk with null does nothing', () => {
    const { feedChunk, isPlaying } = useTTSPlayer()

    feedChunk(null)
    expect(isPlaying.value).toBe(false)
    expect(mockStart).not.toHaveBeenCalled()
  })

  it('multiple feedChunk calls schedule sequentially', () => {
    const { feedChunk, isPlaying } = useTTSPlayer()

    const int16 = new Int16Array([16000, -16000])
    const bytes = new Uint8Array(int16.buffer)
    const base64 = btoa(String.fromCharCode(...bytes))

    feedChunk(base64)
    feedChunk(base64)
    expect(isPlaying.value).toBe(true)
    expect(mockStart).toHaveBeenCalledTimes(2)
  })

  it('stop calls source.stop() on active sources', () => {
    const { feedChunk, stop } = useTTSPlayer()

    const int16 = new Int16Array([16000])
    const bytes = new Uint8Array(int16.buffer)
    const base64 = btoa(String.fromCharCode(...bytes))

    feedChunk(base64)
    stop()
    expect(mockStop).toHaveBeenCalled()
  })
})
