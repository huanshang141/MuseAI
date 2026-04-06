import { ref } from 'vue'

const API_BASE = '/api/v1'

function getToken() {
  return localStorage.getItem('access_token')
}

function handleError(response) {
  const error = new Error(response.data?.detail || `HTTP ${response.status}`)
  error.status = response.status
  error.data = response.data
  throw error
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    handleError({ status: response.status, data })
  }

  return { ok: response.ok, status: response.status, data }
}

export function useCurator() {
  const loading = ref(false)
  const error = ref(null)

  async function planTour(availableTime, interests) {
    loading.value = true
    error.value = null
    try {
      const result = await request('/curator/plan-tour', {
        method: 'POST',
        body: JSON.stringify({ available_time: availableTime, interests }),
      })
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
      const result = await request('/curator/narrative', {
        method: 'POST',
        body: JSON.stringify({ exhibit_id: exhibitId }),
      })
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
      const result = await request('/curator/reflection', {
        method: 'POST',
        body: JSON.stringify({ exhibit_id: exhibitId }),
      })
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
