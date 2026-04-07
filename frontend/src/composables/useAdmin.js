import { ref } from 'vue'
import { api } from '../api/index.js'

export function useAdmin() {
  const loading = ref(false)
  const error = ref(null)

  // Exhibit management
  async function createExhibit(data) {
    loading.value = true
    const result = await api.admin.createExhibit(data)
    loading.value = false
    return result
  }

  async function updateExhibit(id, data) {
    loading.value = true
    const result = await api.admin.updateExhibit(id, data)
    loading.value = false
    return result
  }

  async function deleteExhibit(id) {
    loading.value = true
    const result = await api.admin.deleteExhibit(id)
    loading.value = false
    return result
  }

  // Tour path management
  async function createTourPath(data) {
    loading.value = true
    const result = await api.admin.createTourPath(data)
    loading.value = false
    return result
  }

  async function updateTourPath(id, data) {
    loading.value = true
    const result = await api.admin.updateTourPath(id, data)
    loading.value = false
    return result
  }

  async function deleteTourPath(id) {
    loading.value = true
    const result = await api.admin.deleteTourPath(id)
    loading.value = false
    return result
  }

  return {
    loading,
    error,
    createExhibit,
    updateExhibit,
    deleteExhibit,
    createTourPath,
    updateTourPath,
    deleteTourPath
  }
}