import { useState, useEffect } from 'react'
import { getTheme, toggleTheme } from '../utils/theme.js'

export default function ThemeToggle({ className = '' }) {
  const [theme, setThemeState] = useState(() => getTheme())

  useEffect(() => {
    const handleThemeChange = (e) => {
      setThemeState(e.detail?.theme || getTheme())
    }
    window.addEventListener('blend-theme-change', handleThemeChange)
    return () => window.removeEventListener('blend-theme-change', handleThemeChange)
  }, [])

  const handleToggle = () => {
    const next = toggleTheme()
    setThemeState(next)
  }

  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      onClick={handleToggle}
      className={`p-1.5 sm:p-2 rounded-lg border transition-all duration-200 flex items-center justify-center shrink-0 ${
        isDark
          ? 'bg-gray-800 hover:bg-gray-700 text-amber-400 border-gray-700 hover:border-gray-600'
          : 'bg-white hover:bg-gray-100 text-gray-700 border-gray-200 hover:border-gray-300 shadow-sm'
      } ${className}`}
      title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      {isDark ? (
        // Sun icon for dark mode (click to switch to light)
        <svg
          className="w-4 h-4 sm:w-4 sm:h-4 transition-transform duration-200 hover:rotate-45"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
          />
        </svg>
      ) : (
        // Moon icon for light mode (click to switch to dark)
        <svg
          className="w-4 h-4 sm:w-4 sm:h-4 transition-transform duration-200 hover:-rotate-12 text-slate-700"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
          />
        </svg>
      )}
    </button>
  )
}
