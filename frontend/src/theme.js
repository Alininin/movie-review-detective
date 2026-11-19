// 明暗主题：默认跟随系统，可手动切换，选择记在 localStorage 里。
// 支持用 URL 指定（方便分享某个主题下的截图）：?theme=light / ?theme=dark
import { computed, ref } from 'vue'

const STORAGE_KEY = 'mrd-theme'
const VALID = new Set(['auto', 'light', 'dark'])

function readFromUrl() {
  const candidates = [window.location.search, window.location.hash.includes('?')
    ? window.location.hash.slice(window.location.hash.indexOf('?'))
    : '']
  for (const raw of candidates) {
    if (!raw) continue
    const value = new URLSearchParams(raw).get('theme')
    if (value && VALID.has(value)) return value
  }
  return null
}

function readStored() {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value && VALID.has(value) ? value : null
  } catch (error) {
    return null
  }
}

const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null
const systemDark = ref(media ? media.matches : false)

// mode 是用户的选择（auto / light / dark），resolved 是真正生效的主题
const mode = ref(readFromUrl() || readStored() || 'auto')
const resolved = computed(() =>
  mode.value === 'auto' ? (systemDark.value ? 'dark' : 'light') : mode.value
)

function apply() {
  const root = document.documentElement
  root.dataset.theme = resolved.value
  root.style.colorScheme = resolved.value
}

function persist(value) {
  try {
    localStorage.setItem(STORAGE_KEY, value)
  } catch (error) {
    /* 隐私模式下写不了 localStorage，不影响使用 */
  }
}

export function setTheme(next) {
  if (!VALID.has(next)) return
  mode.value = next
  persist(next)
  apply()
}

export function toggleTheme() {
  setTheme(resolved.value === 'dark' ? 'light' : 'dark')
}

if (media) {
  const onSystemChange = (event) => {
    systemDark.value = event.matches
    if (mode.value === 'auto') apply()
  }
  if (media.addEventListener) media.addEventListener('change', onSystemChange)
  else if (media.addListener) media.addListener(onSystemChange)
}

apply()

export function useTheme() {
  return { mode, resolved, setTheme, toggleTheme }
}
