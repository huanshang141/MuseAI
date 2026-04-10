import vLazyImg from './vLazyImg.js'

export const directives = {
  'lazy-img': vLazyImg,
}

export function registerDirectives(app) {
  for (const [name, directive] of Object.entries(directives)) {
    app.directive(name, directive)
  }
}
