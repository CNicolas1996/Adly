import { useAdly, ADLY_STATES } from '@/context/AdlyContext'

/**
 * Convenience hook that exposes adlyState + typed trigger helpers.
 * Components use triggerState() instead of calling setAdlyState directly.
 */
export function useAdlyState() {
  const { adlyState, setAdlyState, wakeAdly } = useAdly()

  return {
    adlyState,
    wakeAdly,

    /** Switch to a state, optionally reverting to idle after durationMs */
    triggerState: (state, durationMs = null) => setAdlyState(state, durationMs),

    // Shorthand helpers used by useAnalysis and InputZone
    setThinking: () => setAdlyState(ADLY_STATES.THINKING),
    setTyping:   () => setAdlyState(ADLY_STATES.TYPING),
    setHappy:    () => setAdlyState(ADLY_STATES.HAPPY, 2000),
    setError:    () => setAdlyState(ADLY_STATES.ERROR, 3000),
    setIdle:     () => setAdlyState(ADLY_STATES.IDLE),

    // State checks
    isIdle:     adlyState === ADLY_STATES.IDLE,
    isThinking: adlyState === ADLY_STATES.THINKING,
    isTyping:   adlyState === ADLY_STATES.TYPING,
    isHappy:    adlyState === ADLY_STATES.HAPPY,
    isError:    adlyState === ADLY_STATES.ERROR,
    isSleeping: adlyState === ADLY_STATES.SLEEP,
  }
}

export default useAdlyState
