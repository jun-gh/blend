import React, { useState } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || ''

export default function LockScreen({ onUnlock }) {
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!password.trim() || loading) return

    setLoading(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/api/auth/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: password.trim() }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Incorrect password')
      }

      const data = await res.json()
      onUnlock(data.token)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col justify-center items-center px-4 select-none">
      <div className="w-full max-w-sm">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-brand-950 border border-brand-800/60 shadow-inner mb-4">
            <span className="text-3xl">🔐</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center justify-center gap-2">
            <span>Blend</span>
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            This site is protected. Enter the access password to continue.
          </p>
        </div>

        {/* Lock Card */}
        <form
          onSubmit={handleSubmit}
          className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-2xl space-y-4"
        >
          {error && (
            <div className="bg-red-950/70 border border-red-800/80 text-red-200 text-xs px-3.5 py-2.5 rounded-xl flex items-center gap-2 animate-fade-in">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5">
              Access Password
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password…"
                autoFocus
                required
                className="w-full bg-gray-950 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-colors pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-200 text-xs p-1"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={!password.trim() || loading}
            className="w-full py-3 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-500 active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-lg shadow-brand-600/20"
          >
            {loading ? 'Verifying…' : 'Unlock Access'}
          </button>
        </form>

        <p className="text-center text-xs text-gray-600 mt-6">
          Blend Hybrid Search RAG · v0.1.0
        </p>
      </div>
    </div>
  )
}
