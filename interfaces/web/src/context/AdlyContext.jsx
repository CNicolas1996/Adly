import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react'

// ─── Valid states ─────────────────────────────────────────────────────────────
export const ADLY_STATES = {
  IDLE:     'idle',
  THINKING: 'thinking',
  TYPING:   'typing',
  HAPPY:    'happy',
  ERROR:    'error',
  SLEEP:    'sleep',
}

const SLEEP_TIMEOUT_MS = 30_000 // 30 seconds of no interaction

// ─── Context ──────────────────────────────────────────────────────────────────
const AdlyContext = createContext(null)

// ─── Provider ─────────────────────────────────────────────────────────────────
export function AdlyProvider({ children }) {
  const [adlyState, setAdlyStateRaw] = useState(ADLY_STATES.IDLE)
  const sleepTimerRef = useRef(null)
  const stateTimerRef = useRef(null)

  // Reset sleep timer on any user interaction
  const resetSleepTimer = useCallback(() => {
    if (adlyState === ADLY_STATES.SLEEP) {
      setAdlyStateRaw(ADLY_STATES.IDLE)
    }
    clearTimeout(sleepTimerRef.current)
    sleepTimerRef.current = setTimeout(() => {
      setAdlyStateRaw(ADLY_STATES.SLEEP)
    }, SLEEP_TIMEOUT_MS)
  }, [adlyState])

  // Listen to user activity to reset sleep timer
  useEffect(() => {
    const events = ['mousemove', 'keydown', 'mousedown', 'touchstart']
    events.forEach(e => window.addEventListener(e, resetSleepTimer, { passive: true }))
    resetSleepTimer() // Start initial timer

    return () => {
      events.forEach(e => window.removeEventListener(e, resetSleepTimer))
      clearTimeout(sleepTimerRef.current)
    }
  }, [resetSleepTimer])

  /**
   * Set Adly state, optionally auto-reverting to idle after durationMs.
   * @param {string} newState - One of ADLY_STATES values
   * @param {number|null} durationMs - ms before reverting to idle (null = persist)
   */
  const setAdlyState = useCallback((newState, durationMs = null) => {
    clearTimeout(stateTimerRef.current)
    setAdlyStateRaw(newState)

    if (durationMs !== null) {
      stateTimerRef.current = setTimeout(() => {
        setAdlyStateRaw(ADLY_STATES.IDLE)
      }, durationMs)
    }
  }, [])

  // Wake Adly from sleep on click
  const wakeAdly = useCallback(() => {
    if (adlyState === ADLY_STATES.SLEEP) {
      setAdlyState(ADLY_STATES.IDLE)
      resetSleepTimer()
    }
  }, [adlyState, setAdlyState, resetSleepTimer])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearTimeout(sleepTimerRef.current)
      clearTimeout(stateTimerRef.current)
    }
  }, [])

  return (
    <AdlyContext.Provider value={{ adlyState, setAdlyState, wakeAdly, ADLY_STATES }}>
      {children}
    </AdlyContext.Provider>
  )
}

// ─── Hook ─────────────────────────────────────────────────────────────────────
export function useAdly() {
  const ctx = useContext(AdlyContext)
  if (!ctx) throw new Error('useAdly must be used inside <AdlyProvider>')
  return ctx
}

export default AdlyContext
