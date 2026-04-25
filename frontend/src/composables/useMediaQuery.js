import { onMounted, onUnmounted, ref } from 'vue'

export function useMediaQuery(query) {
  const matches = ref(false)
  let mediaQueryList

  const syncMatches = () => {
    matches.value = !!mediaQueryList?.matches
  }

  onMounted(() => {
    mediaQueryList = window.matchMedia(query)
    syncMatches()
    mediaQueryList.addEventListener('change', syncMatches)
  })

  onUnmounted(() => {
    mediaQueryList?.removeEventListener('change', syncMatches)
  })

  return matches
}
