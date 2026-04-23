import { useState, useEffect, useCallback } from 'react'
import { getMessages, sendMessage as apiSend, getDatasetInfo } from '@/api/client'
import { useAdlyState } from '@/hooks/useAdlyState'

/**
 * Manages chat messages + dataset info for a single analysis.
 * Drives Adly state transitions automatically:
 *   user sends → typing
 *   waiting response → thinking
 *   response arrives → happy (2s) → idle
 *   error → error (3s) → idle
 */
export function useAnalysis(analysisId) {
  const [messages, setMessages]     = useState([])
  const [dataset, setDataset]       = useState(null)
  const [loading, setLoading]       = useState(true)
  const [sending, setSending]       = useState(false)
  const [error, setError]           = useState(null)

  const { setThinking, setTyping, setHappy, setError: setAdlyError, setIdle } = useAdlyState()

  // Load initial messages + dataset info
  useEffect(() => {
    if (!analysisId) return
    setLoading(true)
    setError(null)

    Promise.all([
      getMessages(analysisId),
      getDatasetInfo(analysisId),
    ])
      .then(([msgs, ds]) => {
        setMessages(msgs)
        setDataset(ds)
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [analysisId])

  /**
   * Send a user message.
   * Optimistically appends user msg, then awaits bot response.
   */
  const sendMessage = useCallback(async (text) => {
    if (!text.trim() || sending) return

    // Optimistic user message
    const userMsg = {
      id:        `u_${Date.now()}`,
      role:      'user',
      content:   text.trim(),
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    setSending(true)
    setTyping()

    // Short delay before switching to "thinking" to feel natural
    const thinkTimer = setTimeout(() => setThinking(), 400)

    try {
      const botMsg = await apiSend(analysisId, text.trim())
      clearTimeout(thinkTimer)
      setMessages(prev => [...prev, botMsg])
      setHappy()
    } catch (err) {
      clearTimeout(thinkTimer)
      setError(err.message)
      setAdlyError()
      // Append error bubble
      setMessages(prev => [
        ...prev,
        {
          id:        `err_${Date.now()}`,
          role:      'bot',
          content:   `⚠️ Error al conectar con el servidor: ${err.message}`,
          confidence: 0,
          timestamp: new Date().toISOString(),
        },
      ])
    } finally {
      setSending(false)
    }
  }, [analysisId, sending, setTyping, setThinking, setHappy, setAdlyError])

  /** Called by InputZone when user starts typing (focus/keystroke) */
  const onUserTyping = useCallback(() => {
    if (!sending) setTyping()
  }, [sending, setTyping])

  /** Called by InputZone when user clears/blurs without sending */
  const onUserStopTyping = useCallback(() => {
    if (!sending) setIdle()
  }, [sending, setIdle])

  return {
    messages,
    dataset,
    loading,
    sending,
    error,
    sendMessage,
    onUserTyping,
    onUserStopTyping,
  }
}

export default useAnalysis
