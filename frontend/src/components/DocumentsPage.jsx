import React, { useState, useEffect, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || ''

function getAuthHeaders(extraHeaders = {}) {
  const token = localStorage.getItem('blend_access_token')
  return {
    ...extraHeaders,
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
    <div className="bg-gray-800 rounded-xl p-4 border border-gray-700 hover:border-brand-600/50 transition-colors animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-100 truncate">{doc.title}</h3>
          {doc.source && (
            <p className="text-xs text-gray-500 mt-0.5 truncate">{doc.source}</p>
          )}
          <p className="text-xs text-gray-600 mt-1">
            {new Date(doc.created_at).toLocaleString()}
          </p>
        </div>
        <button
          onClick={() => onDelete(doc.id)}
          className="shrink-0 text-xs text-red-400 hover:text-red-300 transition-colors px-2 py-1 rounded hover:bg-red-900/30"
          aria-label={`Delete ${doc.title}`}
        >
          Delete
        </button>
      </div>
    </div>
  )
}

function UploadForm({ onSuccess }) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [source, setSource] = useState('')
  const [loading, setLoading] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [error, setError] = useState(null)
  const fileRef = useRef(null)

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
    if (!title.trim() || !content.trim()) return
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
      if (!res.ok) throw new Error(`Upload failed (${res.status})`)
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
    <form onSubmit={handleSubmit} className="bg-gray-800/60 rounded-xl sm:rounded-2xl border border-gray-700 p-4 sm:p-6 space-y-4">
      <h2 className="text-base font-semibold text-gray-200">Add Document</h2>

      {error && (
        <p className="text-xs sm:text-sm text-red-400 bg-red-900/20 rounded-lg px-3 py-2 border border-red-800">
          {error}
        </p>
      )}

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Title *</label>
        <input
          type="text"
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="My Research Paper"
          required
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-base sm:text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Source URL (optional)</label>
        <input
          type="text"
          value={source}
          onChange={e => setSource(e.target.value)}
          placeholder="https://..."
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-base sm:text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">
          Upload file (.pdf, .txt, .md, .csv, .json)
          {extracting && (
            <span className="ml-2 text-brand-400 animate-pulse font-normal">
              ⏳ Extracting text from PDF…
            </span>
          )}
        </label>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.txt,.md,.csv,.json,application/pdf"
          onChange={handleFile}
          disabled={extracting}
          className="text-xs sm:text-sm text-gray-400 file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-brand-600 file:text-white file:text-xs file:cursor-pointer hover:file:bg-brand-500 disabled:opacity-50"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Content * (or paste text)</label>
        <textarea
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder="Paste your document content here or upload a file above…"
          required
          rows={6}
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-base sm:text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 font-mono resize-y"
        />
      </div>

      <button
        type="submit"
        disabled={loading || extracting || !title.trim() || !content.trim()}
        className="w-full py-2.5 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {extracting ? 'Extracting PDF…' : loading ? 'Ingesting…' : 'Ingest Document'}
      </button>
    </form>
  )
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState([])
  const [total, setTotal] = useState(0)
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
      }
    } catch {
      // Handled
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchDocs() }, [])

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
    <div className="flex flex-col lg:flex-row h-full overflow-hidden">
      {/* Mobile Tab Switcher */}
      <div className="lg:hidden flex border-b border-gray-800 bg-gray-900/90 p-2 shrink-0 gap-2">
        <button
          onClick={() => setMobileTab('upload')}
          className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 ${
            mobileTab === 'upload'
              ? 'bg-brand-600 text-white shadow-sm'
              : 'bg-gray-800/80 text-gray-400 hover:text-gray-200'
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
              : 'bg-gray-800/80 text-gray-400 hover:text-gray-200'
          }`}
        >
          <span>📂</span>
          <span>Documents ({total})</span>
        </button>
      </div>

      {/* Left: Upload form */}
      <div
        className={`w-full lg:w-96 shrink-0 lg:border-r border-gray-800 p-4 sm:p-6 overflow-y-auto ${
          mobileTab === 'upload' ? 'block' : 'hidden lg:block'
        }`}
      >
        <UploadForm
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
        <div className="flex items-center justify-between mb-4">
          <h1 className="font-semibold text-gray-200 text-base sm:text-lg">
            Knowledge Base
            <span className="ml-2 text-xs sm:text-sm font-normal text-gray-500">
              {total} document{total !== 1 ? 's' : ''}
            </span>
          </h1>
          <button
            onClick={fetchDocs}
            className="text-xs text-gray-400 hover:text-gray-200 transition-colors px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-750"
          >
            ↺ Refresh
          </button>
        </div>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-20 bg-gray-800 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : docs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-600">
            <p className="text-4xl mb-3">📂</p>
            <p className="text-sm">No documents yet.</p>
            <p className="text-xs mt-1">Upload your first document to get started.</p>
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
