import { ref } from 'vue'
import { api } from '../api/index.js'

export function useCurator() {
  const loading = ref(false)
  const error = ref(null)

  async function planTour(availableTime, interests) {
    loading.value = true
    error.value = null
    try {
      const result = await api.curator.planTour(availableTime, interests)
      if (!result.ok) {
        error.value = result.data?.detail || '规划路线失败'
        return null
      }
      return result.data
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function generateNarrative(exhibitId) {
    loading.value = true
    error.value = null
    try {
      const result = await api.curator.generateNarrative(exhibitId)
      if (!result.ok) {
        error.value = result.data?.detail || '生成讲解失败'
        return null
      }
      return result.data
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function getReflectionPrompts(exhibitId) {
    loading.value = true
    error.value = null
    try {
      const result = await api.curator.getReflectionPrompts(exhibitId)
      if (!result.ok) {
        error.value = result.data?.detail || '获取思考引导失败'
        return null
      }
      return result.data
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    planTour,
    generateNarrative,
    getReflectionPrompts,
  }
}
