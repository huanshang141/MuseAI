import { ref } from 'vue'
import { api } from '../api/index.js'

export function useDocuments() {
  const documents = ref([])
  const loading = ref(false)

  async function fetchDocuments() {
    loading.value = true
    const result = await api.documents.list()
    loading.value = false
    if (result.ok) {
      documents.value = result.data.documents
    }
    return result
  }

  async function uploadDocument(file) {
    const result = await api.documents.upload(file)
    if (result.ok) {
      documents.value.unshift(result.data)
    }
    return result
  }

  async function deleteDocument(docId) {
    const result = await api.documents.delete(docId)
    if (result.ok) {
      documents.value = documents.value.filter(d => d.id !== docId)
    }
    return result
  }

  async function getDocumentStatus(docId) {
    return await api.documents.status(docId)
  }

  return {
    documents,
    loading,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    getDocumentStatus,
  }
}
