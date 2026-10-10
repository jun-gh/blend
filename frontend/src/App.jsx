import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import ChatPage from './components/ChatPage.jsx'
import DocumentsPage from './components/DocumentsPage.jsx'

const NAV_ITEMS = [
  { to: '/',          label: 'Chat',      icon: '💬' },
  { to: '/documents', label: 'Documents', icon: '📂' },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden">
        {/* Sidebar */}
        <aside className="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
          <div className="px-5 py-4 border-b border-gray-800">
            <span className="text-xl font-bold tracking-tight text-brand-400">⚗️ Blend</span>
            <p className="text-xs text-gray-500 mt-0.5">Hybrid Search RAG</p>
          </div>
          <nav className="flex-1 px-2 py-4 space-y-1">
            {NAV_ITEMS.map(({ to, label, icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-brand-600 text-white'
                      : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
                  }`
                }
              >
                <span>{icon}</span>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="px-4 py-3 border-t border-gray-800">
            <p className="text-xs text-gray-600">v0.1.0</p>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
