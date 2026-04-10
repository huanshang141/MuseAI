/**
 * v-lazy-img directive for lazy loading images using IntersectionObserver.
 * Usage: <img v-lazy-img="imageUrl" />
 */
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const img = entry.target
        const src = img.dataset.lazySrc
        if (src) {
          img.src = src
          img.removeAttribute('data-lazy-src')
          img.classList.remove('lazy-loading')
          img.classList.add('lazy-loaded')
        }
        observer.unobserve(img)
      }
    })
  },
  { rootMargin: '100px' }
)

export default {
  mounted(el, binding) {
    el.dataset.lazySrc = binding.value
    el.classList.add('lazy-loading')
    observer.observe(el)
  },
  updated(el, binding) {
    if (binding.value !== el.dataset.lazySrc) {
      el.dataset.lazySrc = binding.value
      el.src = ''
      el.classList.add('lazy-loading')
      el.classList.remove('lazy-loaded')
      observer.observe(el)
    }
  },
  unmounted(el) {
    observer.unobserve(el)
  },
}
