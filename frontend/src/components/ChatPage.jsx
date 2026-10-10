import React, { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'

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
    <div className={`flex gap-3 animate-slide-up ${ isUser ? 'justify-end' : 'justify-start' }`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-brand-600 flex items-center justify-center text-xs shrink-0 mt-0.5">⚗️</div>
      )}
      <div className={`max-w-2xl ${ isUser ? 'max-w-lg' : '' }`}>
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? 'bg-brand-600 text-white rounded-br-sm'
              : 'bg-gray-800 text-gray-100 rounded-bl-sm'
          }`}
        >
          {isUser ? (
            msg.content
          ) : (
            <ReactMarkdown className="prose prose-invert prose-sm max-w-none">
              {msg.content}
            </ReactMarkdown>
          )}
        </div>
        {msg.sources && msg.sources.length > 0 && (
          <div className="mt-2 space-y-1">
            <p className="text-xs text-gray-500 px-1">Sources</p>
            {msg.sources.map(s => <SourceCard key={s.chunk_id} source={s} />)}
          </div>
        )}
        {msg.meta && (
          <p className="text-xs text-gray-600 mt-1 px-1">
            retrieval {msg.meta.retrieval_ms}ms · generation {msg.meta.generation_ms}ms
          </p>
        )}
      </div>
      {isUser && (
        <div className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center text-xs shrink-0 mt-0.5">👤</div>
      )}
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-3 justify-start animate-fade-in">
      <div className="w-7 h-7 rounded-full bg-brand-600 flex items-center justify-center text-xs shrink-0">⚗️</div>
      <div className="px-4 py-3 rounded-2xl rounded-bl-sm bg-gray-800">
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

export default function ChatPage() {
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

  // Auto-scroll to latest message
  const scrollToBottom = useCallback(() => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight
    }
  }, [])

  useEffect(() => { scrollToBottom() }, [messages, loading])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setError(null)

    const userMsg = { role: 'user', content: text, id: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/api/query/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text, top_k: 5 }),
      })
      if (!res.ok) throw new Error(`API error ${res.status}`)
      const data = await res.json()
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          sources: data.sources,
          meta: { retrieval_ms: data.retrieval_ms, generation_ms: data.generation_ms },
          id: Date.now() + 1,
        },
      ])
    } catch (err) {
      setError(err.message)
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
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="px-6 py-3 border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm flex items-center justify-between">
        <h1 className="font-semibold text-gray-200">Chat</h1>
        <span className="text-xs text-gray-500">Hybrid RAG · Gemini + FTS5</span>
      </header>

      {/* Messages */}
      <div ref={scrollerRef} className="chat-scroller flex-1 px-6 py-6 space-y-4 relative">
        {messages.map(msg => <Message key={msg.id} msg={msg} />)}
        {loading && <TypingIndicator />}
        {error && (
          <div
            popover="manual"
            className="[&:is(:popover-open,.\\:popover-open)]:block fixed bottom-20 right-6 bg-red-900/90 text-red-200 text-sm px-4 py-2 rounded-lg border border-red-700 max-w-xs"
          >
            ⚠️ {error}
          </div>
        )}
        {/* Scroll-to-bottom FAB (scroll-state aware) */}
        <button
          onClick={scrollToBottom}
          className="scroll-to-bottom sticky bottom-4 float-right mr-2 w-8 h-8 rounded-full bg-brand-600 text-white text-sm shadow-lg hover:bg-brand-500 transition-colors"
          aria-label="Scroll to bottom"
        >
          ↓
        </button>
      </div>

      {/* Input bar */}
      <div className="px-6 py-4 border-t border-gray-800 bg-gray-900/80 backdrop-blur-sm">
        <div className="flex gap-3 max-w-4xl mx-auto">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask anything about your documents… (Enter to send, Shift+Enter for newline)"
            rows={1}
            className="flex-1 resize-none bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-colors"
            style={{ minHeight: '48px', maxHeight: '160px', overflowY: 'auto' }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            className="px-5 py-3 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
          >
            {loading ? '⏳' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}
