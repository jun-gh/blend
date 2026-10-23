import React, { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { getSessionId } from '../utils/session.js'
import ThemeToggle from './ThemeToggle.jsx'

const API_BASE = import.meta.env.VITE_API_URL || ''

function SourceCard({ source }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden text-xs shadow-sm dark:shadow-none">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-100 hover:bg-gray-200/70 dark:bg-gray-800 dark:hover:bg-gray-700 text-left text-gray-700 dark:text-gray-300 transition-colors"
      >
        <span className="font-medium truncate">{source.document_title}</span>
        <span className="ml-2 text-gray-500 shrink-0">score {source.score.toFixed(3)} {open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 py-2 bg-gray-50 dark:bg-gray-900 text-gray-600 dark:text-gray-400 font-mono leading-relaxed border-t border-gray-200 dark:border-gray-700">
          {source.content}
        </div>
      )}
    </div>
  )
}

function hasNoContextNotice(content) {
  if (!content) return false
  const noContextRegex = /(?:do(?:es)?\s+not\s+contain|not\s+(?:found|mentioned|stated|discussed|provided)\s+in\s+the\s+(?:provided\s+|context\s+)?document|no\s+information\s+(?:found|provided|available|regarding|about|on)?.*in\s+the\s+(?:provided\s+|context\s+)?document|(?:provided\s+|context\s+)?documents?\s+(?:do(?:es)?\s+not|never)\s+(?:contain|mention|state|provide|have)|cannot\s+(?:find|determine|answer).*based\s+on\s+the\s+(?:provided\s+)?document|could\s+not\s+find\s+any\s+relevant\s+information|insufficient\s+information\s+in\s+the\s+(?:provided\s+)?document|no\s+relevant\s+context\s+found)/i
  return noContextRegex.test(content)
}

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-2 sm:gap-3 animate-slide-up ${ isUser ? 'justify-end' : 'justify-start' }`}>
      {!isUser && (
        <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-brand-600 flex items-center justify-center text-[10px] sm:text-xs font-bold text-white shrink-0 mt-0.5 shadow-sm">
          B
        </div>
      )}
      <div className={`max-w-[85%] sm:max-w-2xl ${ isUser ? 'sm:max-w-lg' : '' }`}>
        <div
          className={`px-3.5 py-2.5 sm:px-4 sm:py-3 rounded-2xl text-xs sm:text-sm leading-relaxed ${
            isUser
              ? 'bg-brand-600 text-white rounded-br-sm shadow-sm'
              : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-sm border border-gray-200 dark:border-transparent shadow-sm'
          }`}
        >
          {isUser ? (
            msg.content
          ) : (
            <>
              {msg.content ? (
                <div className="relative">
                  <ReactMarkdown className="prose dark:prose-invert prose-xs sm:prose-sm max-w-none text-gray-800 dark:text-gray-100">
                    {msg.content}
                  </ReactMarkdown>
                  {msg.streaming && (
                    <span className="inline-block w-1.5 h-3.5 ml-1 bg-brand-500 dark:bg-brand-400 animate-pulse align-middle" />
                  )}
                </div>
              ) : (
                <div className="flex gap-1 items-center h-4 py-1">
                  {[0, 1, 2].map(i => (
                    <span
                      key={i}
                      className="block w-1.5 h-1.5 rounded-full bg-brand-500 dark:bg-brand-400 animate-pulse-slow"
                      style={{ animationDelay: `${i * 200}ms` }}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
        {msg.sources && msg.sources.length > 0 && !hasNoContextNotice(msg.content) && (
          <div className="mt-2 space-y-1 animate-fade-in">
            <p className="text-[11px] sm:text-xs text-gray-500 dark:text-gray-400 px-1 font-medium flex items-center justify-between">
              <span>Sources</span>
              {msg.streaming && (
                <span className="text-[10px] text-brand-600 dark:text-brand-400 font-normal animate-pulse">
                  ⚡ Generating answer…
                </span>
              )}
            </p>
            {msg.sources.map(s => <SourceCard key={s.chunk_id} source={s} />)}
          </div>
        )}
        {msg.meta && (
          <p className="text-[10px] sm:text-xs text-gray-500 dark:text-gray-400 mt-1.5 px-1 flex items-center gap-1.5 flex-wrap">
            {msg.meta.model_name && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700/60 font-mono text-[9px] sm:text-[10px]">
                {msg.meta.model_name}
              </span>
            )}
            <span>
              retrieval {msg.meta.retrieval_ms}ms
              {typeof msg.meta.generation_ms === 'number'
                ? ` · generation ${msg.meta.generation_ms}ms`
                : msg.streaming
                ? ' · streaming…'
                : ''}
            </span>
          </p>
        )}
      </div>
      {isUser && (
        <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200 flex items-center justify-center text-[10px] sm:text-xs shrink-0 mt-0.5 shadow-sm">
          👤
        </div>
      )}
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-2 sm:gap-3 justify-start animate-fade-in">
      <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-brand-600 flex items-center justify-center text-[10px] sm:text-xs font-bold text-white shrink-0 shadow-sm">
        B
      </div>
      <div className="px-3.5 py-2.5 sm:px-4 sm:py-3 rounded-2xl rounded-bl-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-transparent shadow-sm">
        <div className="flex gap-1 items-center h-4">
          {[0, 1, 2].map(i => (
            <span
              key={i}
              className="block w-1.5 h-1.5 rounded-full bg-brand-500 dark:bg-brand-400 animate-pulse-slow"
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

    // Generate distinct, collision-free IDs for user and assistant
    const userMsgId = `user_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
    const assistantMsgId = `assistant_${Date.now() + 1}_${Math.random().toString(36).slice(2, 9)}`

    // Avoid duplicate user message if retrying the same query
    setMessages(prev => {
      const last = prev[prev.length - 1]
      if (last && last.role === 'user' && last.content === text) {
        return prev
      }
      return [...prev, { role: 'user', content: text, id: userMsgId }]
    })
    setLoading(true)

    try {
      const token = localStorage.getItem('blend_access_token')
      const headers = {
        'Content-Type': 'application/json',
        'X-Session-ID': getSessionId(),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      }
      const res = await fetch(`${API_BASE}/api/query/stream`, {
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

      // Add active assistant message placeholder
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: '',
          sources: [],
          meta: null,
          id: assistantMsgId,
          streaming: true,
        },
      ])
      // Turn off generic bottom loading indicator as assistant bubble is active
      setLoading(false)

      const reader = res.body?.getReader()
      if (!reader) {
        throw new Error('Streaming not supported by browser.')
      }

      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed) {
            currentEvent = null
            continue
          }
          if (trimmed.startsWith('event:')) {
            currentEvent = trimmed.slice(6).trim()
            continue
          }
          if (trimmed.startsWith('data:')) {
            const dataStr = trimmed.slice(5).trim()
            try {
              const data = JSON.parse(dataStr)
              if (currentEvent === 'sources') {
                // Instant Source Hydration!
                setMessages(prev =>
                  prev.map(m =>
                    m.id === assistantMsgId && m.role === 'assistant'
                      ? {
                          ...m,
                          sources: data.sources || [],
                          meta: {
                            retrieval_ms: data.retrieval_ms,
                            model: data.model,
                            model_name: data.model_name || activeModel.name || data.model,
                          },
                        }
                      : m
                  )
                )
              } else if (currentEvent === 'delta') {
                setMessages(prev =>
                  prev.map(m =>
                    m.id === assistantMsgId && m.role === 'assistant'
                      ? { ...m, content: m.content + (data.text || '') }
                      : m
                  )
                )
              } else if (currentEvent === 'done') {
                setMessages(prev =>
                  prev.map(m => {
                    if (m.id === assistantMsgId && m.role === 'assistant') {
                      const clearSources = data.clear_sources || hasNoContextNotice(m.content)
                      const finalSources = clearSources ? [] : (data.sources !== undefined ? data.sources : m.sources)
                      return {
                        ...m,
                        streaming: false,
                        sources: finalSources,
                        meta: {
                          ...(m.meta || {}),
                          generation_ms: data.generation_ms,
                          total_ms: data.total_ms,
                        },
                      }
                    }
                    return m
                  })
                )
              } else if (currentEvent === 'error') {
                throw new Error(data.detail || 'Streaming generation error')
              }
            } catch (jsonErr) {
              if (currentEvent === 'error') throw jsonErr
            }
          }
        }
      }
    } catch (err) {
      // Remove empty assistant placeholder if failed prior to receiving any output
      setMessages(prev =>
        prev.filter(
          m =>
            !(
              m.id === assistantMsgId &&
              m.role === 'assistant' &&
              !m.content &&
              (!m.sources || m.sources.length === 0)
            )
        )
      )
      const isRateLimit =
        err.status === 429 ||
        /quota|rate limit|resource_exhausted|limit exceeded/i.test(err.message)
      setError({
        message: err.message,
        isRateLimit,
        queryText: text,
      })
    } finally {
      setMessages(prev =>
        prev.map(m => (m.id === assistantMsgId && m.role === 'assistant' ? { ...m, streaming: false } : m))
      )
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
    <div className="flex flex-col h-full overflow-hidden bg-transparent">
      {/* Header */}
      <header className="px-4 sm:px-6 py-2.5 sm:py-3 border-b border-gray-200 dark:border-gray-800 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          <h1 className="font-semibold text-sm sm:text-base text-gray-800 dark:text-gray-200">Chat</h1>
        </div>
        <div className="hidden md:flex items-center gap-2">
          <ThemeToggle />
        </div>
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
      <div className="px-3 sm:px-6 py-2.5 sm:py-4 border-t border-gray-200 dark:border-gray-800 bg-white/90 dark:bg-gray-900/80 backdrop-blur-sm shrink-0">
        <div className="max-w-4xl mx-auto space-y-2.5">
          {error && (
            <div
              role="alert"
              className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 sm:p-3.5 rounded-xl border text-xs sm:text-sm animate-fade-in ${
                error.isRateLimit
                  ? 'bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-600/60 text-amber-900 dark:text-amber-200'
                  : 'bg-red-50 dark:bg-red-950/40 border-red-300 dark:border-red-700/60 text-red-900 dark:text-red-200'
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
                  className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-gray-100 text-gray-700 border border-gray-200 dark:bg-gray-800/80 dark:hover:bg-gray-700 dark:text-gray-300 dark:border-gray-700/60 transition-colors shadow-sm"
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
              placeholder="Ask anything about your documents…"
              rows={1}
              className="flex-1 resize-none bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-xl px-3.5 py-2.5 sm:px-4 sm:py-3 text-base sm:text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-colors shadow-sm"
              style={{ minHeight: '44px', maxHeight: '140px', overflowY: 'auto' }}
            />
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
              className="px-4 sm:px-5 py-2.5 sm:py-3 rounded-xl bg-brand-600 text-white text-xs sm:text-sm font-medium hover:bg-brand-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0 flex items-center justify-center min-w-[56px] sm:min-w-[64px] shadow-sm"
            >
              {loading ? '⏳' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
