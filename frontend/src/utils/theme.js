/**
 * Theme management utility for Blend.
 * Supports 'dark' and 'light' themes with 'dark' as default.
 */

const THEME_KEY = 'blend_theme'

export function getTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved === 'light' || saved === 'dark') {
      return saved
    }
  } catch {
    // LocalStorage unavailable
  }
  return 'dark'
}

export function applyTheme(theme) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (theme === 'dark') {
    root.classList.add('dark')
    root.classList.remove('light')
    root.style.colorScheme = 'dark'
  } else {
    root.classList.remove('dark')
    root.classList.add('light')
    root.style.colorScheme = 'light'
  }
}

export function setTheme(theme) {
  try {
    localStorage.setItem(THEME_KEY, theme)
  } catch {
    // Ignore storage errors
  }
  applyTheme(theme)
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('blend-theme-change', { detail: { theme } }))
  }
  return theme
}

export function toggleTheme() {
  const current = getTheme()
  const next = current === 'dark' ? 'light' : 'dark'
  return setTheme(next)
}

// Initialise immediately
if (typeof window !== 'undefined') {
  applyTheme(getTheme())
}
