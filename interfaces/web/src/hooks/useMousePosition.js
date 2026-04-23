import { useState, useEffect, useRef } from 'react'

/**
 * Tracks mouse position, throttled to ~60fps via requestAnimationFrame.
 * Returns { x, y } in pixels relative to the viewport.
 */
export function useMousePosition() {
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const rafRef = useRef(null)
  const latestPos = useRef({ x: 0, y: 0 })

  useEffect(() => {
    function onMouseMove(e) {
      latestPos.current = { x: e.clientX, y: e.clientY }
      if (rafRef.current) return
      rafRef.current = requestAnimationFrame(() => {
        setPosition({ ...latestPos.current })
        rafRef.current = null
      })
    }

    window.addEventListener('mousemove', onMouseMove, { passive: true })
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [])

  return position
}

export default useMousePosition
