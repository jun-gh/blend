import React, { useState, useEffect, useRef } from 'react'
import { getSessionId, resetSession } from '../utils/session.js'
import ThemeToggle from './ThemeToggle.jsx'

const API_BASE = import.meta.env.VITE_API_URL || ''

function getAuthHeaders(extraHeaders = {}) {
  const token = localStorage.getItem('blend_access_token')
  return {
    ...extraHeaders,
    'X-Session-ID': getSessionId(),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

function handleAuthResponse(res) {
  if (res.status === 401) {
    window.dispatchEvent(new Event('blend-unauthorized'))
    throw new Error('Session expired. Please re-enter the site password.')
  }
  return res
}

function DocumentCard({ doc, onDelete }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 hover:border-brand-500/50 dark:hover:border-brand-600/50 shadow-sm dark:shadow-none transition-colors animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 dark:text-gray-100 truncate">{doc.title}</h3>
          {doc.source && (
            <p className="text-xs text-gray-500 mt-0.5 truncate">{doc.source}</p>
          )}
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            {new Date(doc.created_at).toLocaleString()}
          </p>
        </div>
        <button
          onClick={() => onDelete(doc.id)}
          className="shrink-0 text-xs text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300 transition-colors px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-900/30"
          aria-label={`Delete ${doc.title}`}
        >
          Delete
        </button>
      </div>
    </div>
  )
}

function UploadForm({ onSuccess, total = 0, maxDocs = 10 }) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [source, setSource] = useState('')
  const [loading, setLoading] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [error, setError] = useState(null)
  const fileRef = useRef(null)

  const isAtQuota = total >= maxDocs

  const handleFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    const nameWithoutExt = file.name.replace(/\.[^/.]+$/, '')
    if (!title) setTitle(nameWithoutExt)

    if (file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf') {
      setExtracting(true)
      setError(null)
      try {
        const formData = new FormData()
        formData.append('file', file)
        const res = await fetch(`${API_BASE}/api/documents/extract-text`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: formData,
        })
        handleAuthResponse(res)
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}))
          throw new Error(errData.detail || `PDF extraction failed (${res.status})`)
        }
        const data = await res.json()
        setContent(data.text)
      } catch (err) {
        setError(err.message)
      } finally {
        setExtracting(false)
      }
    } else {
      try {
        const text = await file.text()
        setContent(text)
      } catch (err) {
        setError(`Failed to read file: ${err.message}`)
      }
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (isAtQuota || !title.trim() || !content.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/documents/`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          title: title.trim(),
          content: content.trim(),
          source: source.trim() || null,
        }),
      })
      handleAuthResponse(res)
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Upload failed (${res.status})`)
      }
      setTitle('')
      setContent('')
      setSource('')
      if (fileRef.current) fileRef.current.value = ''
      onSuccess()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800/60 rounded-xl sm:rounded-2xl border border-gray-200 dark:border-gray-700 p-4 sm:p-6 space-y-4 shadow-sm dark:shadow-none">
      <h2 className="text-base font-semibold text-gray-900 dark:text-gray-200">Add Document</h2>

      {isAtQuota && (
        <div className="text-xs sm:text-sm text-amber-900 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 rounded-lg p-3 border border-amber-200 dark:border-amber-800/80 space-y-1">
          <div className="font-semibold flex items-center gap-1.5">
            <span>⚠️</span>
            <span>Session Limit Reached ({total}/{maxDocs})</span>
          </div>
          <p className="text-amber-800/90 dark:text-amber-200/80 leading-relaxed">
            You have reached the maximum limit of {maxDocs} documents for this session. Delete existing documents or start a new session to upload more.
          </p>
        </div>
      )}

      {error && (
        <p className="text-xs sm:text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg px-3 py-2 border border-red-200 dark:border-red-800">
          {error}
        </p>
      )}

      <div>
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-400 mb-1">Title *</label>
        <input
          type="text"
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="My Research Paper"
          required
          disabled={isAtQuota || loading}
          className="w-full bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-base sm:text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm dark:shadow-none"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-400 mb-1">Source URL (optional)</label>
        <input
          type="text"
          value={source}
          onChange={e => setSource(e.target.value)}
          placeholder="https://..."
          disabled={isAtQuota || loading}
          className="w-full bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-base sm:text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm dark:shadow-none"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-400 mb-1">
          Upload file (.pdf, .txt, .md, .csv, .json)
          {extracting && (
            <span className="ml-2 text-brand-600 dark:text-brand-400 animate-pulse font-normal">
              ⏳ Extracting text from PDF…
            </span>
          )}
        </label>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.txt,.md,.csv,.json,application/pdf"
          onChange={handleFile}
          disabled={isAtQuota || extracting}
          className="text-xs sm:text-sm text-gray-600 dark:text-gray-400 file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-brand-600 file:text-white file:text-xs file:cursor-pointer hover:file:bg-brand-500 disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-400 mb-1">Content * (or paste text)</label>
        <textarea
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder="Paste your document content here or upload a file above…"
          required
          rows={6}
          disabled={isAtQuota || loading}
          className="w-full bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-base sm:text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 font-mono resize-y disabled:opacity-50 disabled:cursor-not-allowed shadow-sm dark:shadow-none"
        />
      </div>

      <button
        type="submit"
        disabled={isAtQuota || loading || extracting || !title.trim() || !content.trim()}
        className="w-full py-2.5 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-sm"
      >
        {isAtQuota
          ? `Limit Reached (${total}/${maxDocs})`
          : extracting
          ? 'Extracting PDF…'
          : loading
          ? 'Ingesting…'
          : 'Ingest Document'}
      </button>
    </form>
  )
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState([])
  const [total, setTotal] = useState(0)
  const [maxDocs, setMaxDocs] = useState(10)
  const [loading, setLoading] = useState(true)
  const [mobileTab, setMobileTab] = useState('upload')

  const fetchDocs = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/documents/?limit=50`, {
        headers: getAuthHeaders(),
      })
      handleAuthResponse(res)
      if (res.ok) {
        const data = await res.json()
        setDocs(data.items)
        setTotal(data.total)
        if (typeof data.max_documents === 'number') {
          setMaxDocs(data.max_documents)
        }
      }
    } catch {
      // Handled
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchDocs() }, [])

  useEffect(() => {
    const handleSessionReset = () => {
      fetchDocs()
    }
    window.addEventListener('blend-session-reset', handleSessionReset)
    return () => window.removeEventListener('blend-session-reset', handleSessionReset)
  }, [])

  const handleResetSession = () => {
    if (
      window.confirm(
        'Start a new session? This provides a fresh 10-document quota and isolates new uploads from your previous session.'
      )
    ) {
      resetSession()
      fetchDocs()
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this document and all its chunks?')) return
    try {
      const res = await fetch(`${API_BASE}/api/documents/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      })
      handleAuthResponse(res)
      fetchDocs()
    } catch {
      // Handled
    }
  }

  return (
    <div className="flex flex-col lg:flex-row h-full overflow-hidden bg-transparent">
      {/* Mobile Tab Switcher */}
      <div className="lg:hidden flex border-b border-gray-200 dark:border-gray-800 bg-white/90 dark:bg-gray-900/90 p-2 shrink-0 gap-2">
        <button
          onClick={() => setMobileTab('upload')}
          className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 ${
            mobileTab === 'upload'
              ? 'bg-brand-600 text-white shadow-sm'
              : 'bg-gray-100 dark:bg-gray-800/80 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
          }`}
        >
          <span>➕</span>
          <span>Add Document</span>
        </button>
        <button
          onClick={() => setMobileTab('list')}
          className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 ${
            mobileTab === 'list'
              ? 'bg-brand-600 text-white shadow-sm'
              : 'bg-gray-100 dark:bg-gray-800/80 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
          }`}
        >
          <span>📂</span>
          <span>Documents ({total}/{maxDocs})</span>
        </button>
      </div>

      {/* Left: Upload form */}
      <div
        className={`w-full lg:w-96 shrink-0 lg:border-r border-gray-200 dark:border-gray-800 p-4 sm:p-6 overflow-y-auto ${
          mobileTab === 'upload' ? 'block' : 'hidden lg:block'
        }`}
      >
        <UploadForm
          total={total}
          maxDocs={maxDocs}
          onSuccess={() => {
            fetchDocs()
            setMobileTab('list')
          }}
        />
      </div>

      {/* Right: Document list */}
      <div
        className={`flex-1 p-4 sm:p-6 overflow-y-auto ${
          mobileTab === 'list' ? 'block' : 'hidden lg:block'
        }`}
      >
        {/* Session Quota Card */}
        <div className="mb-4 bg-white dark:bg-gray-800/80 rounded-xl border border-gray-200 dark:border-gray-700/80 p-3 sm:p-4 shadow-sm dark:shadow-none">
          <div className="flex items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
                Session Storage
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  total >= maxDocs
                    ? 'bg-red-100 text-red-700 border border-red-200 dark:bg-red-900/60 dark:text-red-300 dark:border-red-700/50'
                    : total >= maxDocs * 0.8
                    ? 'bg-amber-100 text-amber-800 border border-amber-200 dark:bg-amber-900/60 dark:text-amber-300 dark:border-amber-700/50'
                    : 'bg-brand-50 text-brand-700 border border-brand-200 dark:bg-brand-900/60 dark:text-brand-300 dark:border-brand-700/50'
                }`}
              >
                {total} of {maxDocs} used
              </span>
            </div>
            <button
              onClick={handleResetSession}
              title="Start a new anonymous session with fresh quota"
              className="text-xs text-brand-600 dark:text-brand-400 hover:text-brand-700 dark:hover:text-brand-300 font-medium px-2.5 py-1 rounded bg-brand-50 hover:bg-brand-100 dark:bg-brand-950/40 dark:hover:bg-brand-900/60 border border-brand-200 dark:border-brand-800/60 transition-colors shrink-0"
            >
              Start New Session
            </button>
          </div>
          {/* Progress Bar */}
          <div className="w-full bg-gray-100 dark:bg-gray-900 h-2 rounded-full overflow-hidden border border-gray-200 dark:border-gray-700/50">
            <div
              className={`h-full transition-all duration-300 ${
                total >= maxDocs
                  ? 'bg-red-500'
                  : total >= maxDocs * 0.8
                  ? 'bg-amber-500'
                  : 'bg-brand-500'
              }`}
              style={{ width: `${Math.min(100, (total / Math.max(1, maxDocs)) * 100)}%` }}
            />
          </div>
          <div className="text-[11px] text-gray-400 dark:text-gray-500 mt-1.5 flex items-center justify-between">
            <span>Documents auto-expire after 7 days</span>
            <span>Isolated to your browser session</span>
          </div>
        </div>

        <div className="flex items-center justify-between mb-4">
          <h1 className="font-semibold text-gray-900 dark:text-gray-200 text-base sm:text-lg">
            Knowledge Base
            <span className="ml-2 text-xs sm:text-sm font-normal text-gray-500 dark:text-gray-400">
              {total} document{total !== 1 ? 's' : ''}
            </span>
          </h1>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchDocs}
              className="text-xs text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200 transition-colors px-2.5 py-1.5 rounded-lg bg-white hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 shadow-sm"
            >
              ↺ Refresh
            </button>
            <div className="hidden md:flex items-center">
              <ThemeToggle />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-20 bg-gray-200 dark:bg-gray-800 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : docs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-400 dark:text-gray-600">
            <p className="text-4xl mb-3">📂</p>
            <p className="text-sm font-medium text-gray-600 dark:text-gray-400">No documents in this session yet.</p>
            <p className="text-xs mt-1">Upload a document to get started.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {docs.map(doc => (
              <DocumentCard key={doc.id} doc={doc} onDelete={handleDelete} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
