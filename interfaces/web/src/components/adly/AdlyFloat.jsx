import { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react'
import { motion, useDragControls } from 'framer-motion'
import { useAdly } from '@/context/AdlyContext'
import { ADLY_STATE_CONFIG } from './adlyStates'

const STORAGE_KEY    = 'adly_float_pos'
const SIZE_KEY       = 'adly_float_size'
const DEFAULT_SIZE   = 80
const SLEEP_AFTER_MS = 30_000

const STATE_IMAGE = {
  idle:     '/seals/idle.png',
  error:    '/seals/error.svg',
  thinking: '/seals/thinking.svg',
  sleep:    '/seals/sleep.svg',
  warning:  '/seals/warning.svg',
  alert:    '/seals/alert.svg',
  happy:    '/seals/happy.svg',
  typing:   '/seals/thinking.svg',
}

function getInitialPos() {
  try {
    const s = JSON.parse(localStorage.getItem(STORAGE_KEY))
    if (s?.x != null) return s
  } catch {}
  return { x: window.innerWidth - 120, y: window.innerHeight - 140 }
}

function getInitialSize() {
  try {
    const s = parseInt(localStorage.getItem(SIZE_KEY), 10)
    if (s >= 48 && s <= 160) return s
  } catch {}
  return DEFAULT_SIZE
}

const CSS = `
  @keyframes adly-tail {
    0%   { transform: rotate(-13deg); }
    20%  { transform: rotate(18deg);  }
    45%  { transform: rotate(-9deg);  }
    70%  { transform: rotate(15deg);  }
    100% { transform: rotate(-13deg); }
  }
  @keyframes adly-bounce {
    0%, 100% { transform: translateY(0px); }
    50%      { transform: translateY(-6px); }
  }
  @keyframes adly-zzz {
    0%   { opacity: 0; transform: translate(0px, 0px) scale(0.7); }
    20%  { opacity: 0.85; }
    80%  { opacity: 0.4;  }
    100% { opacity: 0; transform: translate(-3px, -22px) scale(1.08); }
  }
  @media (prefers-reduced-motion: reduce) {
    .adly-root * {
      animation-duration: 0.01ms !important;
      transition-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
    }
  }
`

// ─── ZZZ bubbles ─────────────────────────────────────────────────────────────
function ZzzBubbles({ size }) {
  const base = size * 0.16
  return (
    <div style={{ position: 'absolute', top: -(size * 0.38), right: -(size * 0.05), pointerEvents: 'none', zIndex: 2 }}>
      {[
        { ch: 'z', delay: 0,   fs: base * 0.72 },
        { ch: 'z', delay: 0.7, fs: base * 0.88 },
        { ch: 'Z', delay: 1.4, fs: base },
      ].map((z, i) => (
        <span
          key={i}
          style={{
            position:   'absolute',
            right:      i * (size * 0.14),
            top:        0,
            fontSize:   z.fs,
            fontWeight: 700,
            color:      '#aaaaaa',
            fontFamily: 'system-ui, sans-serif',
            animation:  `adly-zzz 2.5s ${z.delay}s infinite ease-out`,
            opacity:    0,
            lineHeight: 1,
          }}
        >
          {z.ch}
        </span>
      ))}
    </div>
  )
}

// ─── Tail SVG — wiggles independently via CSS ─────────────────────────────────
function Tail({ size, durationS }) {
  const ts = size * 0.46
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 48 48"
      width={ts}
      height={ts}
      style={{
        position:        'absolute',
        bottom:          size * 0.07,
        right:           -(ts * 0.36),
        overflow:        'visible',
        transformOrigin: '17% 87%',
        animation:       `adly-tail ${durationS}s ease-in-out infinite`,
        pointerEvents:   'none',
        mixBlendMode:    'multiply',
      }}
    >
      <path d="M 6 42 Q 20 24 36 8" fill="none" stroke="#e8742a" strokeWidth="10" strokeLinecap="round" />
      <path d="M 6 42 Q 20 24 36 8" fill="none" stroke="#2a1208" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  )
}

// ─── Crossfade hook ───────────────────────────────────────────────────────────
// Keeps the outgoing image alive and fades it out via imperative style,
// avoiding the "transition on mount" problem.
function useImageFade(src) {
  const [cur, setCur]   = useState(src)
  const [prev, setPrev] = useState(null)
  const prevRef         = useRef(null)
  const timerRef        = useRef(null)

  useEffect(() => {
    if (src === cur) return
    clearTimeout(timerRef.current)
    setPrev(cur)
    setCur(src)
  }, [src, cur])

  useLayoutEffect(() => {
    if (!prev || !prevRef.current) return
    const el = prevRef.current
    // Start at full opacity (no transition yet)
    el.style.opacity    = '1'
    el.style.transition = 'none'

    // Next frame: trigger fade-out
    const raf = requestAnimationFrame(() => {
      if (!el) return
      el.style.opacity    = '0'
      el.style.transition = 'opacity 300ms ease'
    })
    timerRef.current = setTimeout(() => setPrev(null), 330)

    return () => {
      cancelAnimationFrame(raf)
      clearTimeout(timerRef.current)
    }
  }, [prev])

  return { cur, prev, prevRef }
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function AdlyFloat() { return null }

// eslint-disable-next-line no-unused-vars
function AdlyFloatImpl() {
  const { adlyState, wakeAdly } = useAdly()

  const [pos, setPos]                 = useState(getInitialPos)
  const [size, setSize]               = useState(getInitialSize)
  const [isHovered, setIsHovered]     = useState(false)
  const [showTooltip, setShowTooltip] = useState(false)
  const [localSleep, setLocalSleep]   = useState(false)
  const [blinkActive, setBlinkActive] = useState(false)

  const dragControls   = useDragControls()
  const constraintsRef = useRef(null)
  const sleepRef       = useRef(null)
  const blinkRef       = useRef(null)

  // Priority: hover > localSleep/backend-sleep > adlyState
  const effectiveState = isHovered
    ? 'happy'
    : (localSleep || adlyState === 'sleep') ? 'sleep'
    : adlyState

  const cfg       = ADLY_STATE_CONFIG[effectiveState] ?? ADLY_STATE_CONFIG.idle
  const targetSrc = STATE_IMAGE[effectiveState] ?? STATE_IMAGE.idle
  const tailDur   = cfg.tailDuration  ?? 2.8
  const bounceDur = cfg.bodyDuration  ?? 4

  const { cur, prev, prevRef } = useImageFade(targetSrc)

  // ── Sleep timer ─────────────────────────────────────────────────────────────
  const resetSleep = useCallback(() => {
    setLocalSleep(false)
    clearTimeout(sleepRef.current)
    sleepRef.current = setTimeout(() => setLocalSleep(true), SLEEP_AFTER_MS)
  }, [])

  useEffect(() => {
    if (adlyState === 'sleep') {
      clearTimeout(sleepRef.current)
      setLocalSleep(false)
      return
    }
    resetSleep()
    window.addEventListener('mousemove', resetSleep)
    window.addEventListener('keydown',   resetSleep)
    return () => {
      clearTimeout(sleepRef.current)
      window.removeEventListener('mousemove', resetSleep)
      window.removeEventListener('keydown',   resetSleep)
    }
  }, [adlyState, resetSleep])

  // ── Organic blink via random setInterval ────────────────────────────────────
  useEffect(() => {
    if (effectiveState === 'sleep') return
    function sched() {
      const wait = 2500 + Math.random() * 4500
      blinkRef.current = setTimeout(() => {
        setBlinkActive(true)
        setTimeout(() => setBlinkActive(false), 130)
        sched()
      }, wait)
    }
    sched()
    return () => clearTimeout(blinkRef.current)
  }, [effectiveState])

  // ── Drag handlers ──────────────────────────────────────────────────────────
  const handleDragEnd = (_, info) => {
    const newPos = {
      x: Math.max(0, Math.min(window.innerWidth  - size - 10, pos.x + info.offset.x)),
      y: Math.max(0, Math.min(window.innerHeight - size - 10, pos.y + info.offset.y)),
    }
    setPos(newPos)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newPos))
    resetSleep()
  }

  const handleWheel = (e) => {
    e.preventDefault()
    setSize(prev => {
      const next = Math.max(48, Math.min(160, prev - Math.sign(e.deltaY) * 8))
      localStorage.setItem(SIZE_KEY, String(next))
      return next
    })
  }

  const handleClick = () => {
    if (localSleep) setLocalSleep(false)
    wakeAdly()
    resetSleep()
  }

  const baseImg = {
    width:         '100%',
    height:        '100%',
    objectFit:     'contain',
    mixBlendMode:  'multiply',
    userSelect:    'none',
    pointerEvents: 'none',
    display:       'block',
  }

  return (
    <>
      <style>{CSS}</style>

      {/* Full-window drag constraint layer */}
      <div
        ref={constraintsRef}
        style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 9998 }}
      />

      <motion.div
        drag
        dragControls={dragControls}
        dragMomentum={false}
        dragElastic={0.1}
        dragConstraints={constraintsRef}
        onDragEnd={handleDragEnd}
        onClick={handleClick}
        onWheel={handleWheel}
        onHoverStart={() => { setIsHovered(true);  setShowTooltip(true)  }}
        onHoverEnd={()   => { setIsHovered(false); setShowTooltip(false) }}
        initial={{ x: pos.x, y: pos.y, opacity: 0, scale: 0.6 }}
        animate={{ x: pos.x, y: pos.y, opacity: 1, scale: 1 }}
        transition={{
          opacity: { duration: 0.4 },
          scale:   { type: 'spring', stiffness: 280, damping: 22 },
        }}
        whileDrag={{ scale: 1.08, cursor: 'grabbing' }}
        className="adly-root"
        style={{
          position:    'fixed',
          top:         0,
          left:        0,
          zIndex:      9999,
          cursor:      'grab',
          userSelect:  'none',
          touchAction: 'none',
        }}
      >
        {/* State tooltip */}
        {showTooltip && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              position:      'absolute',
              bottom:        '100%',
              left:          '50%',
              transform:     'translateX(-50%)',
              marginBottom:  8,
              whiteSpace:    'nowrap',
              background:    '#1e1e1e',
              border:        '1px solid #2a2a2a',
              borderRadius:  6,
              padding:       '3px 10px',
              fontSize:      11,
              color:         '#999999',
              fontFamily:    'Inter, sans-serif',
              pointerEvents: 'none',
            }}
          >
            {cfg.label}
            {effectiveState === 'sleep' && (
              <span style={{ color: '#e8742a', marginLeft: 6 }}>— click para despertar</span>
            )}
          </motion.div>
        )}

        {/* Body — idle bounce with spring easing as requested */}
        <div
          style={{
            position:  'relative',
            width:     size,
            height:    size,
            animation: `adly-bounce ${bounceDur}s cubic-bezier(0.34, 1.56, 0.64, 1) infinite`,
          }}
        >
          {/* Hover glow */}
          {isHovered && (
            <div style={{
              position:      'absolute',
              inset:         -6,
              borderRadius:  '50%',
              background:    'radial-gradient(circle, rgba(232,116,42,0.18) 0%, transparent 70%)',
              pointerEvents: 'none',
              zIndex:        0,
            }} />
          )}

          {/* ZZZ bubbles when sleeping */}
          {effectiveState === 'sleep' && <ZzzBubbles size={size} />}

          {/* Image crossfade stack */}
          <div style={{ position: 'relative', width: '100%', height: '100%' }}>
            {/* Outgoing image: sits on top, fades out via imperative style in hook */}
            {prev && (
              <img
                ref={prevRef}
                src={prev}
                alt=""
                style={{ ...baseImg, position: 'absolute', inset: 0, zIndex: 1 }}
              />
            )}

            {/* Active image: blink simulated via brief scaleY compression */}
            <img
              src={cur}
              alt="Adly"
              style={{
                ...baseImg,
                position:        'relative',
                transform:       blinkActive ? 'scaleY(0.92)' : 'scaleY(1)',
                transformOrigin: 'center 38%',
                transition:      blinkActive ? 'transform 55ms ease' : 'transform 90ms ease',
              }}
            />
          </div>

          {/* Tail — independent CSS wiggle, pivot at base */}
          <Tail size={size} durationS={tailDur} />
        </div>
      </motion.div>
    </>
  )
}
