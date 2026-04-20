import { ref } from 'vue'
import { api } from '../api/index.js'
import { useAuth } from './useAuth.js'

const documents = ref([])
const loading = ref(false)
const error = ref(null)

export function useDocuments() {
  const { isAdmin, isAuthenticated } = useAuth()

  function handleError(result) {
    if (result.status === 401) {
      error.value = '请先登录'
    } else if (result.status === 403) {
      error.value = '需要管理员权限'
    } else {
      error.value = result.data?.detail || '请求失败'
    }
    return result
  }

  async function fetchDocuments() {
    if (!isAuthenticated.value) {
      error.value = '请先登录'
      return { ok: false, status: 401, data: { detail: '未认证' } }
    }

    if (!isAdmin.value) {
      error.value = '需要管理员权限'
      return { ok: false, status: 403, data: { detail: '需要管理员权限' } }
    }

    loading.value = true
    error.value = null
    const result = await api.admin.documents.list()
    loading.value = false

    if (!result.ok) {
      return handleError(result)
    }

    documents.value = result.data.documents
    return result
  }

  async function uploadDocument(file) {
    if (!isAuthenticated.value) {
      error.value = '请先登录'
      return { ok: false, status: 401, data: { detail: '未认证' } }
    }

    if (!isAdmin.value) {
      error.value = '需要管理员权限'
      return { ok: false, status: 403, data: { detail: '需要管理员权限' } }
    }

    const result = await api.admin.documents.upload(file)
    if (!result.ok) {
      return handleError(result)
    }

    documents.value.unshift(result.data)
    return result
  }

  async function deleteDocument(docId) {
    if (!isAuthenticated.value) {
      error.value = '请先登录'
      return { ok: false, status: 401, data: { detail: '未认证' } }
    }

    if (!isAdmin.value) {
      error.value = '需要管理员权限'
      return { ok: false, status: 403, data: { detail: '需要管理员权限' } }
    }

    const result = await api.admin.documents.delete(docId)
    if (!result.ok) {
      return handleError(result)
    }

    documents.value = documents.value.filter(d => d.id !== docId)
    return result
  }

  async function getDocumentStatus(docId) {
    if (!isAuthenticated.value) {
      error.value = '请先登录'
      return { ok: false, status: 401, data: { detail: '未认证' } }
    }

    if (!isAdmin.value) {
      error.value = '需要管理员权限'
      return { ok: false, status: 403, data: { detail: '需要管理员权限' } }
    }

    const result = await api.admin.documents.status(docId)
    if (!result.ok) {
      return handleError(result)
    }
    return result
  }

  return {
    documents,
    loading,
    error,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    getDocumentStatus,
  }
}
