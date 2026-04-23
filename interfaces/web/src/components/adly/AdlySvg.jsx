import { useRef, useEffect, useState, useCallback } from 'react'
import { motion, animate, useMotionValue, useTransform } from 'framer-motion'
import { useMousePosition } from '@/hooks/useMousePosition'
import { useAdly } from '@/context/AdlyContext'
import { ADLY_STATE_CONFIG, MOUTH_PATHS } from './adlyStates'

// ─── Constants ────────────────────────────────────────────────────────────────
const SVG_W = 120
const SVG_H = 120
// Head center in SVG coords
const HEAD_CX = 50
const HEAD_CY = 38
const EYE_MAX_TRAVEL = 2.8  // max px pupils can move from eye center

// ─── Spark particle ───────────────────────────────────────────────────────────
function Spark({ x, y, delay }) {
  return (
    <motion.circle
      cx={x} cy={y} r={2}
      fill="#e8742a"
      initial={{ opacity: 0, scale: 0 }}
      animate={{ opacity: [0, 1, 0], scale: [0, 1.4, 0], y: [0, -8] }}
      transition={{ duration: 0.7, delay, repeat: Infinity, repeatDelay: 0.3 }}
    />
  )
}

// ─── ZZZ letters ─────────────────────────────────────────────────────────────
function ZzzLetters() {
  return (
    <>
      {[
        { letter: 'z', x: 72, y: 28, size: 8,  delay: 0 },
        { letter: 'z', x: 79, y: 20, size: 10, delay: 0.4 },
        { letter: 'z', x: 87, y: 11, size: 12, delay: 0.8 },
      ].map((z, i) => (
        <motion.text
          key={i} x={z.x} y={z.y}
          fontSize={z.size} fill="#aaaaaa"
          fontFamily="Inter, sans-serif" fontWeight="600"
          initial={{ opacity: 0, y: z.y + 4 }}
          animate={{ opacity: [0, 0.7, 0], y: [z.y + 4, z.y - 4] }}
          transition={{ duration: 2, delay: z.delay, repeat: Infinity, repeatDelay: 0.5 }}
        >
          {z.letter}
        </motion.text>
      ))}
    </>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function AdlySvg({ size = 80 }) {
  const { adlyState } = useAdly()
  const mouse = useMousePosition()
  const svgRef = useRef(null)
  const [blinkKey, setBlinkKey] = useState(0)
  const cfg = ADLY_STATE_CONFIG[adlyState] ?? ADLY_STATE_CONFIG.idle

  // ── Pupil tracking ─────────────────────────────────────────────────────────
  const [pupils, setPupils] = useState({ lx: 0, ly: 0, rx: 0, ry: 0 })

  useEffect(() => {
    if (!svgRef.current) return
    const rect = svgRef.current.getBoundingClientRect()
    const scale = rect.width / SVG_W

    // Head center in screen coords
    const headScreenX = rect.left + HEAD_CX * scale
    const headScreenY = rect.top  + HEAD_CY * scale

    const dx = mouse.x - headScreenX
    const dy = mouse.y - headScreenY
    const dist = Math.sqrt(dx * dx + dy * dy) || 1
    const nx = dx / dist
    const ny = dy / dist

    const travel = Math.min(EYE_MAX_TRAVEL, dist / (scale * 12))
    setPupils({
      lx: nx * travel,
      ly: ny * travel,
      rx: nx * travel,
      ry: ny * travel,
    })
  }, [mouse])

  // ── Random blink ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (adlyState === 'sleep') return
    let id
    function scheduleBlink() {
      const wait = 3000 + Math.random() * 5000
      id = setTimeout(() => {
        setBlinkKey(k => k + 1)
        scheduleBlink()
      }, wait)
    }
    scheduleBlink()
    return () => clearTimeout(id)
  }, [adlyState])

  const scale = size / SVG_W

  return (
    <svg
      ref={svgRef}
      width={size}
      height={size}
      viewBox={`0 0 ${SVG_W} ${SVG_H}`}
      style={{ overflow: 'visible', display: 'block' }}
    >
      {/* ── Body ───────────────────────────────────────────────────────────── */}
      <motion.g
        animate={{ scale: cfg.bodyScale, originX: '50px', originY: '68px' }}
        transition={{ duration: cfg.bodyDuration, repeat: Infinity, ease: 'easeInOut' }}
      >
        {/* Body ellipse */}
        <ellipse cx="50" cy="80" rx="34" ry="28" fill="#e8742a" stroke="#2a1208" strokeWidth="2.5"/>

        {/* Tail */}
        <motion.path
          d={cfg.tailPath[0]}
          animate={{ d: cfg.tailPath }}
          transition={{ duration: cfg.tailDuration, repeat: Infinity, ease: 'easeInOut', repeatType: 'mirror' }}
          fill="none" stroke="#e8742a" strokeWidth="7" strokeLinecap="round"
        />
        <motion.path
          d={cfg.tailPath[0]}
          animate={{ d: cfg.tailPath }}
          transition={{ duration: cfg.tailDuration, repeat: Infinity, ease: 'easeInOut', repeatType: 'mirror' }}
          fill="none" stroke="#2a1208" strokeWidth="2" strokeLinecap="round"
        />

        {/* ── Head ─────────────────────────────────────────────────────────── */}
        {/* Left ear */}
        <motion.g
          animate={{ rotate: cfg.earAngle }}
          style={{ originX: '22px', originY: '22px' }}
          transition={{ type: 'spring', stiffness: 200, damping: 12 }}
        >
          <polygon points="22,24 14,6 32,16" fill="#e8742a" stroke="#2a1208" strokeWidth="2"/>
          <polygon points="24,22 17,9 30,17" fill="#f5a06a"/>
        </motion.g>
        {/* Right ear */}
        <motion.g
          animate={{ rotate: -cfg.earAngle }}
          style={{ originX: '78px', originY: '22px' }}
          transition={{ type: 'spring', stiffness: 200, damping: 12 }}
        >
          <polygon points="78,24 86,6 68,16" fill="#e8742a" stroke="#2a1208" strokeWidth="2"/>
          <polygon points="76,22 83,9 70,17" fill="#f5a06a"/>
        </motion.g>

        {/* Head circle */}
        <circle cx="50" cy="38" r="26" fill="#e8742a" stroke="#2a1208" strokeWidth="2.5"/>

        {/* ── Brows ──────────────────────────────────────────────────────── */}
        <motion.g
          animate={{ y: cfg.browsY }}
          transition={{ type: 'spring', stiffness: 300, damping: 20 }}
        >
          {/* Left brow */}
          <motion.line
            x1="28" y1="26" x2="42" y2="29"
            animate={{ rotate: cfg.browAngle }}
            style={{ originX: '35px', originY: '27.5px' }}
            stroke="#2a1208" strokeWidth="3.5" strokeLinecap="round"
            transition={{ type: 'spring', stiffness: 200, damping: 15 }}
          />
          {/* Right brow */}
          <motion.line
            x1="58" y1="29" x2="72" y2="26"
            animate={{ rotate: -cfg.browAngle }}
            style={{ originX: '65px', originY: '27.5px' }}
            stroke="#2a1208" strokeWidth="3.5" strokeLinecap="round"
            transition={{ type: 'spring', stiffness: 200, damping: 15 }}
          />
        </motion.g>

        {/* ── Eyes ───────────────────────────────────────────────────────── */}
        {/* Left eye socket */}
        <ellipse cx="37" cy="36" rx="6.5" ry="7" fill="#2a9090" stroke="#2a1208" strokeWidth="1.5"/>
        {/* Left pupil with tracking */}
        <motion.circle
          cx={37} cy={36} r={3.2} fill="#1a1a1a"
          animate={{ x: pupils.lx, y: pupils.ly }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        />
        {/* Left eye shine */}
        <circle cx="38.5" cy="33.5" r="1.3" fill="white" opacity="0.9"/>

        {/* Right eye socket */}
        <ellipse cx="63" cy="36" rx="6.5" ry="7" fill="#2a9090" stroke="#2a1208" strokeWidth="1.5"/>
        {/* Right pupil with tracking */}
        <motion.circle
          cx={63} cy={36} r={3.2} fill="#1a1a1a"
          animate={{ x: pupils.rx, y: pupils.ry }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        />
        {/* Right eye shine */}
        <circle cx="64.5" cy="33.5" r="1.3" fill="white" opacity="0.9"/>

        {/* ── Eyelid overlay (blink + state) ──────────────────────────────── */}
        <motion.ellipse
          key={`blink-l-${blinkKey}`}
          cx="37" cy="31" rx="7" ry="5.5"
          fill="#e8742a"
          animate={
            adlyState === 'sleep'
              ? { scaleY: 3.2, y: 5 }
              : blinkKey > 0
                ? { scaleY: [1, cfg.eyeOpenY < 0.5 ? cfg.eyeOpenY : 0.05, cfg.eyeOpenY] }
                : { scaleY: cfg.eyeOpenY }
          }
          style={{ originX: '37px', originY: '31px' }}
          transition={{ duration: blinkKey > 0 ? 0.15 : 0.4, ease: 'easeInOut' }}
        />
        <motion.ellipse
          key={`blink-r-${blinkKey}`}
          cx="63" cy="31" rx="7" ry="5.5"
          fill="#e8742a"
          animate={
            adlyState === 'sleep'
              ? { scaleY: 3.2, y: 5 }
              : blinkKey > 0
                ? { scaleY: [1, cfg.eyeOpenY < 0.5 ? cfg.eyeOpenY : 0.05, cfg.eyeOpenY] }
                : { scaleY: cfg.eyeOpenY }
          }
          style={{ originX: '63px', originY: '31px' }}
          transition={{ duration: blinkKey > 0 ? 0.15 : 0.4, ease: 'easeInOut' }}
        />

        {/* ── Nose ───────────────────────────────────────────────────────── */}
        <ellipse cx="50" cy="44" rx="3" ry="2" fill="#c85c14"/>

        {/* ── Mouth ──────────────────────────────────────────────────────── */}
        <motion.path
          d={MOUTH_PATHS[cfg.mouthType]}
          animate={{ d: MOUTH_PATHS[cfg.mouthType] }}
          transition={{ type: 'spring', stiffness: 180, damping: 18 }}
          fill="none" stroke="#2a1208" strokeWidth="2.2" strokeLinecap="round"
        />

        {/* ── Whiskers ───────────────────────────────────────────────────── */}
        <line x1="14" y1="41" x2="33" y2="43" stroke="#2a1208" strokeWidth="1" opacity="0.5"/>
        <line x1="14" y1="45" x2="33" y2="45" stroke="#2a1208" strokeWidth="1" opacity="0.5"/>
        <line x1="67" y1="43" x2="86" y2="41" stroke="#2a1208" strokeWidth="1" opacity="0.5"/>
        <line x1="67" y1="45" x2="86" y2="45" stroke="#2a1208" strokeWidth="1" opacity="0.5"/>

        {/* ── Sparks (typing state) ───────────────────────────────────────── */}
        {cfg.sparks && (
          <>
            <Spark x={72} y={16} delay={0}   />
            <Spark x={80} y={10} delay={0.25}/>
            <Spark x={66} y={10} delay={0.5} />
            <Spark x={76} y={22} delay={0.15}/>
          </>
        )}

        {/* ── ZZZ (sleep state) ──────────────────────────────────────────── */}
        {cfg.zzz && <ZzzLetters />}
      </motion.g>
    </svg>
  )
}
