import React, { useState, useEffect, useCallback } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import ChatPage from './components/ChatPage.jsx'
import DocumentsPage from './components/DocumentsPage.jsx'
import LockScreen from './components/LockScreen.jsx'
import ThemeToggle from './components/ThemeToggle.jsx'

const API_BASE = import.meta.env.VITE_API_URL || ''

const NAV_ITEMS = [
  { to: '/', label: 'Chat', icon: '💬' },
  { to: '/documents', label: 'Documents', icon: '📂' },
]

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('blend_access_token') || '')
  const [authRequired, setAuthRequired] = useState(false)
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [modelInfo, setModelInfo] = useState({ model: '', name: '' })

  // Check backend auth status & active AI model on mount
  useEffect(() => {
    let isMounted = true
    const checkAuthStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/auth/status`)
        if (res.ok) {
          const data = await res.json()
          if (isMounted) {
            setAuthRequired(Boolean(data.required))
            if (data.model) {
              setModelInfo({ model: data.model, name: data.model_name || data.model })
            }
          }
        }
      } catch {
        if (isMounted && token) setAuthRequired(true)
      } finally {
        if (isMounted) setCheckingAuth(false)
      }
    }
    checkAuthStatus()
    return () => {
      isMounted = false
    }
  }, [token])

  // Global listener for 401 Unauthorized events from any API call
  useEffect(() => {
    const handleUnauthorized = () => {
      localStorage.removeItem('blend_access_token')
      setToken('')
      setAuthRequired(true)
    }

    window.addEventListener('blend-unauthorized', handleUnauthorized)
    return () => {
      window.removeEventListener('blend-unauthorized', handleUnauthorized)
    }
  }, [])

  const handleUnlock = useCallback((newToken) => {
    localStorage.setItem('blend_access_token', newToken)
    setToken(newToken)
  }, [])

  const handleLock = useCallback(() => {
    localStorage.removeItem('blend_access_token')
    setToken('')
    setMobileMenuOpen(false)
  }, [])

  if (checkingAuth) {
    return (
      <div className="min-h-[100dvh] bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <div className="flex items-center gap-3 text-brand-600 dark:text-brand-400 text-sm font-medium animate-pulse">
          <span className="w-6 h-6 rounded-md bg-brand-600 text-white flex items-center justify-center text-xs font-bold">
            B
          </span>
          <span>Loading Blend…</span>
        </div>
      </div>
    )
  }

  // If password protection is enabled and user is not unlocked
  if (authRequired && !token) {
    return <LockScreen onUnlock={handleUnlock} />
  }

  return (
    <BrowserRouter>
      <div className="h-[100dvh] w-full flex flex-col md:flex-row overflow-hidden bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
        {/* Mobile Backdrop */}
        {mobileMenuOpen && (
          <div
            onClick={() => setMobileMenuOpen(false)}
            className="md:hidden fixed inset-0 bg-black/40 dark:bg-black/60 backdrop-blur-sm z-40 animate-fade-in"
          />
        )}

        {/* Sidebar (Desktop static + Mobile slide-over) */}
        <aside
          className={`
            fixed md:static inset-y-0 left-0 z-50
            w-64 md:w-56 shrink-0 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col
            transition-transform duration-200 ease-in-out
            ${mobileMenuOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full md:translate-x-0'}
          `}
        >
          <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <img src="/favicon.svg" alt="Blend Logo" className="w-8 h-8 rounded-lg shadow-sm shrink-0" />
              <div>
                <span className="text-xl font-bold tracking-tight text-brand-600 dark:text-brand-400">Blend</span>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Hybrid Search</p>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              {authRequired && (
                <button
                  onClick={handleLock}
                  className="text-xs text-gray-400 hover:text-red-500 transition-colors p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center justify-center"
                  title="Lock site"
                  aria-label="Lock site"
                >
                  <span className="text-sm">🔒</span>
                </button>
              )}
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="md:hidden text-gray-400 hover:text-gray-700 dark:hover:text-white p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Close navigation menu"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          <nav className="flex-1 px-2 py-4 space-y-1">
            {NAV_ITEMS.map(({ to, label, icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-brand-600 text-white'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-100'
                  }`
                }
              >
                <span className="text-base">{icon}</span>
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="px-5 py-3 border-t border-gray-200 dark:border-gray-800 text-center">
            <p className="text-[10px] text-gray-400 dark:text-gray-500 leading-normal break-words">
              Powered by{' '}
              <span
                title={modelInfo.model ? `Configured via GEMINI_CHAT_MODEL: ${modelInfo.model}` : undefined}
                className="font-medium text-gray-600 dark:text-gray-400"
              >
                {modelInfo.name || 'Gemini'}
              </span>
            </p>
          </div>
        </aside>

        {/* Content Wrapper */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Mobile Top Navigation Bar */}
          <header className="md:hidden flex items-center justify-between px-4 py-2.5 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 shrink-0">
            <div className="flex items-center gap-2.5">
              <button
                onClick={() => setMobileMenuOpen(true)}
                className="p-1.5 -ml-1 text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-white rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Open navigation menu"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <img src="/favicon.svg" alt="Blend Logo" className="w-6 h-6 rounded-md shadow-sm shrink-0" />
              <span className="text-base font-bold tracking-tight text-brand-600 dark:text-brand-400">Blend</span>
            </div>

            <div className="flex items-center gap-2">
              <ThemeToggle />
              {authRequired && (
                <button
                  onClick={handleLock}
                  className="text-xs text-gray-500 dark:text-gray-400 hover:text-red-500 flex items-center gap-1 px-2 py-1 rounded bg-gray-100 dark:bg-gray-800/80 border border-gray-200 dark:border-gray-700/60"
                  title="Lock site"
                >
                  <span>🔒</span>
                  <span>Lock</span>
                </button>
              )}
            </div>
          </header>

          {/* Main View Area */}
          <main className="flex-1 min-w-0 overflow-hidden">
            <Routes>
              <Route path="/" element={<ChatPage modelInfo={modelInfo} />} />
              <Route path="/documents" element={<DocumentsPage />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}
