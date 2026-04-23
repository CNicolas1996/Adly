import { useRef } from 'react'
import { motion } from 'framer-motion'

function getColor(pct) {
  if (pct >= 80) return '#4ade80'
  if (pct >= 50) return '#e8742a'
  return '#f87171'
}

// Cat paw shape — fits in 32×36 viewBox
function PawShape() {
  return (
    <>
      {/* Main central pad */}
      <ellipse cx="16" cy="28.5" rx="7.5" ry="6.5" />
      {/* Toe pads — arc above main pad */}
      <ellipse cx="5"   cy="18.5" rx="3.5" ry="3" transform="rotate(-18 5 18.5)"     />
      <ellipse cx="10.5" cy="13"  rx="3.5" ry="3" transform="rotate(-6 10.5 13)"     />
      <ellipse cx="21.5" cy="13"  rx="3.5" ry="3" transform="rotate(6 21.5 13)"      />
      <ellipse cx="27"  cy="18.5" rx="3.5" ry="3" transform="rotate(18 27 18.5)"     />
    </>
  )
}

/**
 * Vertical paw progress indicator.
 * confidence: 0–1 float → fills paw from bottom to top.
 */
export default function ConfidenceBar({ confidence, note }) {
  // Stable unique id per instance — no SSR so Math.random is fine
  const clipId = useRef(`paw-${Math.random().toString(36).slice(2, 7)}`).current

  const pct    = Math.round((confidence ?? 0) * 100)
  const color  = getColor(pct)

  // SVG viewBox height = 36. Clip rect starts at fillY and goes to bottom.
  const VIEW_H   = 36
  const fillY    = VIEW_H * (1 - pct / 100)
  const fillH    = VIEW_H - fillY

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>

        {/* Paw SVG — fills from bottom to top */}
        <svg
          viewBox="0 0 32 36"
          width="32"
          height="36"
          style={{ flexShrink: 0 }}
          aria-hidden="true"
        >
          <defs>
            <clipPath id={clipId}>
              <motion.rect
                x={0}
                width={32}
                initial={{ y: VIEW_H, height: 0 }}
                animate={{ y: fillY, height: fillH }}
                transition={{ duration: 0.7, ease: [0.25, 1, 0.5, 1], delay: 0.1 }}
              />
            </clipPath>
          </defs>

          {/* Dim background paw (full shape, low opacity) */}
          <g fill={color} opacity={0.13}>
            <PawShape />
          </g>

          {/* Colored fill — clipped from bottom up */}
          <g fill={color} clipPath={`url(#${clipId})`}>
            <PawShape />
          </g>
        </svg>

        {/* Label + percentage + note */}
        <div style={{ flex: 1 }}>
          <div style={{
            display:        'flex',
            justifyContent: 'space-between',
            alignItems:     'center',
            marginBottom:   note ? 4 : 0,
          }}>
            <span style={{ fontSize: 11, color: '#555555', fontFamily: 'Inter, sans-serif' }}>
              Confianza del dato
            </span>
            <span style={{ fontSize: 12, fontWeight: 600, color, fontFamily: 'JetBrains Mono, monospace' }}>
              {pct}%
            </span>
          </div>

          {note && (
            <p style={{
              fontSize:    11,
              color:       '#555555',
              margin:      0,
              fontStyle:   'italic',
              fontFamily:  'Inter, sans-serif',
              lineHeight:  1.5,
            }}>
              {note}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
