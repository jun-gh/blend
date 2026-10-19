/**
 * Session management for Blend.
 *
 * Provides a 7-day rolling or fixed session ID stored in localStorage.
 * Automatically rotates after 7 days or upon explicit reset.
 */

const SESSION_KEY = 'blend_session_id'
const CREATED_KEY = 'blend_session_created_at'
const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000

function generateId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return `sess_${crypto.randomUUID()}`
  }
  return `sess_${Math.random().toString(36).slice(2, 11)}_${Date.now()}`
}

/**
 * Retrieve the current session ID, creating a new one if expired or absent.
 */
export function getSessionId() {
  try {
    const existingId = localStorage.getItem(SESSION_KEY)
    const createdAtStr = localStorage.getItem(CREATED_KEY)

    if (existingId && createdAtStr) {
      const createdAt = parseInt(createdAtStr, 10)
      const now = Date.now()
      if (!Number.isNaN(createdAt) && (now - createdAt) < SEVEN_DAYS_MS) {
        return existingId
      }
    }
  } catch {
    // Fallback if localStorage is inaccessible
  }

  // Create a new session
  return resetSession()
}

/**
 * Force-reset the session to a new UUID and timestamp.
 */
export function resetSession() {
  const newId = generateId()
  const now = Date.now()
  try {
    localStorage.setItem(SESSION_KEY, newId)
    localStorage.setItem(CREATED_KEY, now.toString())
  } catch {
    // Ignore storage errors in restricted contexts
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('blend-session-reset', { detail: { sessionId: newId } }))
  }
  return newId
}

/**
 * Return headers with the current X-Session-ID attached.
 */
export function getSessionHeaders(extraHeaders = {}) {
  return {
    ...extraHeaders,
    'X-Session-ID': getSessionId(),
  }
}
