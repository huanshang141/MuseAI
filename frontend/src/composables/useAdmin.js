import { ref } from 'vue'
import { api } from '../api/index.js'

export function useAdmin() {
  const loading = ref(false)
  const error = ref(null)

  // Exhibit management
  async function createExhibit(data) {
    loading.value = true
    error.value = null
    try {
      const result = await api.admin.createExhibit(data)
      if (!result.ok) {
        error.value = result.data?.detail || '创建展品失败'
      }
      return result
    } finally {
      loading.value = false
    }
  }

  async function updateExhibit(id, data) {
    loading.value = true
    error.value = null
    try {
      const result = await api.admin.updateExhibit(id, data)
      if (!result.ok) {
        error.value = result.data?.detail || '更新展品失败'
      }
      return result
    } finally {
      loading.value = false
    }
  }

  async function deleteExhibit(id) {
    loading.value = true
    error.value = null
    try {
      const result = await api.admin.deleteExhibit(id)
      if (!result.ok) {
        error.value = result.data?.detail || '删除展品失败'
      }
      return result
    } finally {
      loading.value = false
    }
  }

  // Tour path management (backend endpoints to be implemented)
  async function createTourPath(data) {
    loading.value = true
    error.value = null
    try {
      const result = await api.admin.createTourPath(data)
      if (!result.ok) {
        error.value = result.data?.detail || '创建路线失败'
      }
      return result
    } finally {
      loading.value = false
    }
  }

  async function updateTourPath(id, data) {
    loading.value = true
    error.value = null
    try {
      const result = await api.admin.updateTourPath(id, data)
      if (!result.ok) {
        error.value = result.data?.detail || '更新路线失败'
      }
      return result
    } finally {
      loading.value = false
    }
  }

  async function deleteTourPath(id) {
    loading.value = true
    error.value = null
    try {
      const result = await api.admin.deleteTourPath(id)
      if (!result.ok) {
        error.value = result.data?.detail || '删除路线失败'
      }
      return result
    } finally {
      loading.value = false
    }
  }

  // Hall settings management
  async function createHall(data) {
    loading.value = true
    error.value = null
    try {
      const result = await api.admin.createHall(data)
      if (!result.ok) {
        error.value = result.data?.detail || '创建展厅失败'
      }
      return result
    } finally {
      loading.value = false
    }
  }

  async function updateHall(slug, data) {
    loading.value = true
    error.value = null
    try {
      const result = await api.admin.updateHall(slug, data)
      if (!result.ok) {
        error.value = result.data?.detail || '更新展厅失败'
      }
      return result
    } finally {
      loading.value = false
    }
  }

  async function deleteHall(slug) {
    loading.value = true
    error.value = null
    try {
      const result = await api.admin.deleteHall(slug)
      if (!result.ok) {
        error.value = result.data?.detail || '删除展厅失败'
      }
      return result
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    createExhibit,
    updateExhibit,
    deleteExhibit,
    createTourPath,
    updateTourPath,
    deleteTourPath,
    createHall,
    updateHall,
    deleteHall,
  }
}