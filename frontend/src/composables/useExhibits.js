import { ref } from 'vue'
import { api } from '../api/index.js'

export function useExhibits() {
  // State is now encapsulated within each useExhibits instance
  const exhibits = ref([])
  const currentExhibit = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function fetchExhibits(params = {}) {
    loading.value = true
    error.value = null

    const result = await api.exhibits.list(params)
    if (result.ok) {
      exhibits.value = result.data.exhibits || result.data
    } else {
      error.value = result.data?.detail || '获取展品失败'
    }

    loading.value = false
    return result
  }

  async function getExhibit(id) {
    loading.value = true
    const result = await api.exhibits.get(id)
    if (result.ok) {
      currentExhibit.value = result.data
    }
    loading.value = false
    return result
  }

  async function filterByCategory(category) {
    return fetchExhibits({ category })
  }

  async function filterByHall(hall) {
    return fetchExhibits({ hall })
  }

  return {
    exhibits,
    currentExhibit,
    loading,
    error,
    fetchExhibits,
    getExhibit,
    filterByCategory,
    filterByHall
  }
}
