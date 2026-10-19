import React, { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { getSessionId } from '../utils/session.js'

const API_BASE = import.meta.env.VITE_API_URL || ''

function SourceCard({ source }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden text-xs">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-800 hover:bg-gray-750 text-left text-gray-300 transition-colors"
      >
        <span className="font-medium truncate">{source.document_title}</span>
        <span className="ml-2 text-gray-500 shrink-0">score {source.score.toFixed(3)} {open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 py-2 bg-gray-850 text-gray-400 font-mono leading-relaxed">
          {source.content}
        </div>
      )}
    </div>
  )
}

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-2 sm:gap-3 animate-slide-up ${ isUser ? 'justify-end' : 'justify-start' }`}>
      {!isUser && (
        <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-brand-600 flex items-center justify-center text-[10px] sm:text-xs font-bold text-white shrink-0 mt-0.5">
          B
        </div>
      )}
      <div className={`max-w-[85%] sm:max-w-2xl ${ isUser ? 'sm:max-w-lg' : '' }`}>
        <div
          className={`px-3.5 py-2.5 sm:px-4 sm:py-3 rounded-2xl text-xs sm:text-sm leading-relaxed ${
            isUser
              ? 'bg-brand-600 text-white rounded-br-sm'
              : 'bg-gray-800 text-gray-100 rounded-bl-sm'
          }`}
        >
          {isUser ? (
            msg.content
          ) : (
            <ReactMarkdown className="prose prose-invert prose-xs sm:prose-sm max-w-none">
              {msg.content}
            </ReactMarkdown>
          )}
        </div>
        {msg.sources && msg.sources.length > 0 && (
          <div className="mt-2 space-y-1">
            <p className="text-[11px] sm:text-xs text-gray-500 px-1">Sources</p>
            {msg.sources.map(s => <SourceCard key={s.chunk_id} source={s} />)}
          </div>
        )}
        {msg.meta && (
          <p className="text-[10px] sm:text-xs text-gray-500 mt-1.5 px-1 flex items-center gap-1.5 flex-wrap">
            {msg.meta.model_name && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 border border-gray-700/60 font-mono text-[9px] sm:text-[10px]">
                {msg.meta.model_name}
              </span>
            )}
            <span>retrieval {msg.meta.retrieval_ms}ms · generation {msg.meta.generation_ms}ms</span>
          </p>
        )}
      </div>
      {isUser && (
        <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-gray-700 flex items-center justify-center text-[10px] sm:text-xs shrink-0 mt-0.5">
          👤
        </div>
      )}
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-2 sm:gap-3 justify-start animate-fade-in">
      <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-brand-600 flex items-center justify-center text-[10px] sm:text-xs font-bold text-white shrink-0">
        B
      </div>
      <div className="px-3.5 py-2.5 sm:px-4 sm:py-3 rounded-2xl rounded-bl-sm bg-gray-800">
        <div className="flex gap-1 items-center h-4">
          {[0, 1, 2].map(i => (
            <span
              key={i}
              className="block w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-slow"
              style={{ animationDelay: `${i * 200}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

export default function ChatPage({ modelInfo }) {
  const [activeModel, setActiveModel] = useState(() => modelInfo || { model: '', name: '' })
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! I am **Blend**, your hybrid search research assistant. Upload documents via the Documents page, then ask me anything about them.',
      id: 'welcome',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const scrollerRef = useRef(null)
  const inputRef = useRef(null)

  // Sync modelInfo from props or fetch as fallback
  useEffect(() => {
    if (modelInfo?.name) {
      setActiveModel(modelInfo)
    } else {
      fetch(`${API_BASE}/api/config/model`)
        .then(res => (res.ok ? res.json() : null))
        .then(data => {
          if (data?.model) {
            setActiveModel({ model: data.model, name: data.model_name || data.model })
          }
        })
        .catch(() => {})
    }
  }, [modelInfo])

  // Auto-scroll to latest message
  const scrollToBottom = useCallback(() => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight
    }
  }, [])

  useEffect(() => { scrollToBottom() }, [messages, loading])

  useEffect(() => {
    const handleReset = () => {
      setMessages([
        {
          role: 'assistant',
          content: 'Session reset! I am ready to search your new session documents.',
          id: 'welcome-reset',
        },
      ])
      setError(null)
    }
    window.addEventListener('blend-session-reset', handleReset)
    return () => window.removeEventListener('blend-session-reset', handleReset)
  }, [])

  const sendMessage = async (overrideText = null) => {
    const text = (typeof overrideText === 'string' ? overrideText : input).trim()
    if (!text || loading) return
    if (!overrideText) setInput('')
    setError(null)

    // Avoid duplicate user message if retrying the same query
    setMessages(prev => {
      const last = prev[prev.length - 1]
      if (last && last.role === 'user' && last.content === text) {
        return prev
      }
      return [...prev, { role: 'user', content: text, id: Date.now() }]
    })
    setLoading(true)

    try {
      const token = localStorage.getItem('blend_access_token')
      const headers = {
        'Content-Type': 'application/json',
        'X-Session-ID': getSessionId(),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      }
      const res = await fetch(`${API_BASE}/api/query/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ query: text, top_k: 5 }),
      })
      if (res.status === 401) {
        window.dispatchEvent(new Event('blend-unauthorized'))
        throw new Error('Session expired. Please re-enter the site password.')
      }
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        const errorDetail = errData.detail || `API error ${res.status}`
        const err = new Error(errorDetail)
        err.status = res.status
        throw err
      }
      const data = await res.json()
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          sources: data.sources,
          meta: {
            retrieval_ms: data.retrieval_ms,
            generation_ms: data.generation_ms,
            model: data.model,
            model_name: data.model_name || activeModel.name || data.model,
          },
          id: Date.now() + 1,
        },
      ])
    } catch (err) {
      const isRateLimit =
        err.status === 429 ||
        /quota|rate limit|resource_exhausted|limit exceeded/i.test(err.message)
      setError({
        message: err.message,
        isRateLimit,
        queryText: text,
      })
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <header className="px-4 sm:px-6 py-2.5 sm:py-3 border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          <h1 className="font-semibold text-sm sm:text-base text-gray-200">Chat</h1>
          {activeModel?.name && (
            <span
              title={`Configured via GEMINI_CHAT_MODEL: ${activeModel.model}`}
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-gray-800 border border-gray-700/80 text-[11px] font-medium text-gray-300"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>{activeModel.name}</span>
            </span>
          )}
        </div>
        <span className="text-[11px] sm:text-xs text-gray-500 hidden sm:inline">Hybrid RAG · Gemini</span>
      </header>

      {/* Messages */}
      <div ref={scrollerRef} className="chat-scroller flex-1 px-3.5 sm:px-6 py-3.5 sm:py-6 space-y-3 sm:space-y-4 relative">
        {messages.map(msg => <Message key={msg.id} msg={msg} />)}
        {loading && <TypingIndicator />}
        {/* Scroll-to-bottom FAB (scroll-state aware) */}
        <button
          onClick={scrollToBottom}
          className="scroll-to-bottom sticky bottom-3 float-right mr-1 sm:mr-2 w-8 h-8 rounded-full bg-brand-600 text-white text-xs sm:text-sm shadow-lg hover:bg-brand-500 transition-colors flex items-center justify-center"
          aria-label="Scroll to bottom"
        >
          ↓
        </button>
      </div>

      {/* Input bar */}
      <div className="px-3 sm:px-6 py-2.5 sm:py-4 border-t border-gray-800 bg-gray-900/80 backdrop-blur-sm shrink-0">
        <div className="max-w-4xl mx-auto space-y-2.5">
          {error && (
            <div
              role="alert"
              className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 sm:p-3.5 rounded-xl border text-xs sm:text-sm animate-fade-in ${
                error.isRateLimit
                  ? 'bg-amber-950/40 border-amber-600/60 text-amber-200'
                  : 'bg-red-950/40 border-red-700/60 text-red-200'
              }`}
            >
              <div className="flex items-start gap-2.5 min-w-0">
                <span className="text-base shrink-0 mt-0.5">
                  {error.isRateLimit ? '⏳' : '⚠️'}
                </span>
                <div className="min-w-0">
                  <p className="font-semibold text-xs sm:text-sm">
                    {error.isRateLimit
                      ? 'AI Model Limit Reached'
                      : 'Unable to Generate Response'}
                  </p>
                  <p className="text-[11px] sm:text-xs opacity-90 mt-0.5 leading-relaxed break-words">
                    {error.message}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                {error.queryText && (
                  <button
                    onClick={() => sendMessage(error.queryText)}
                    disabled={loading}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 shadow-sm ${
                      error.isRateLimit
                        ? 'bg-amber-600 hover:bg-amber-500 text-white'
                        : 'bg-red-600 hover:bg-red-500 text-white'
                    } disabled:opacity-50`}
                  >
                    <span>🔄</span> Retry
                  </button>
                )}
                <button
                  onClick={() => setError(null)}
                  className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-gray-800/80 hover:bg-gray-750 text-gray-300 border border-gray-700/60 transition-colors"
                  aria-label="Dismiss error"
                >
                  ✕ Dismiss
                </button>
              </div>
            </div>
          )}

          <div className="flex gap-2 sm:gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask anything about your documents… (Enter to send)"
              rows={1}
              className="flex-1 resize-none bg-gray-800 border border-gray-700 rounded-xl px-3.5 py-2.5 sm:px-4 sm:py-3 text-base sm:text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-colors"
              style={{ minHeight: '44px', maxHeight: '140px', overflowY: 'auto' }}
            />
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
              className="px-4 sm:px-5 py-2.5 sm:py-3 rounded-xl bg-brand-600 text-white text-xs sm:text-sm font-medium hover:bg-brand-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0 flex items-center justify-center min-w-[56px] sm:min-w-[64px]"
            >
              {loading ? '⏳' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
