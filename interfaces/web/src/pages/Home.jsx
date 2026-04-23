import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, useInView } from 'framer-motion'
import { getAnalyses } from '@/api/client'
import Spinner from '@/components/ui/Spinner'

/* ─── Cat paw SVG (inline, CC0) ──────────────────────── */
function CatPaw({ size = 32, color = '#e8742a', opacity = 1, rotate = 0, style = {} }) {
  return (
    <svg
      viewBox="0 0 274.2 244.33"
      width={size}
      height={size}
      style={{ display: 'block', transform: `rotate(${rotate}deg)`, opacity, ...style }}
    >
      <g transform="translate(-198.45 -215.42)">
        <path fill={color} d="m230.31 398.87c11.173-12.772 35.257-11.499 43.603-26.274 4.5828-8.1119-3.0615-19.151 0-27.951 1.8743-5.3872 5.5283-10.848 10.621-13.416 15.149-7.6391 31.161 0.75806 48.075-0.55902 12.167-0.94735 27.757-10.013 39.131-5.5902 9.3621 3.6405 17.244 13.147 19.566 22.92 2.1726 9.1459-5.0312 25.715-5.0312 27.951 0 2.2361 8.8885 17.525 19.566 23.479 6.3805 3.5577 19.401 0.86486 22.92 7.2672 5.4179 9.8594-3.1367 18-8.3852 27.951-2.6851 5.0907-9.959 14.729-15.093 17.33-11.897 6.0254-26.457-6.6822-39.69-5.0312-11.125 1.388-20.094 12.38-31.305 12.298-12.284-0.0898-21.821-14.335-34.1-13.975-10.33 0.30257-17.711 14.814-27.951 13.416-21.589-2.9467-44.406-21.788-49.193-43.044-1.3386-5.9436 3.2559-12.185 7.2672-16.77z"/>
        <path fill={color} d="m249.32 323.68c3.3541 29.4-12.447 36.616-27.112 36.616s-23.758-13.364-23.758-36.057c0-22.692 14.124-41.647 28.789-41.647s22.081 18.396 22.081 41.088z"/>
        <path fill={color} d="m402.77 255.2c2.2361 30.518-11.888 41.088-26.553 41.088s-29.907-13.364-26.553-41.088c2.7255-22.528 11.888-35.498 26.553-35.498s26.553 12.805 26.553 35.498z"/>
        <path fill={color} d="m472.65 326.41c0 20.739-10.219 31.487-24.876 31.932-33.672 1.0218-23.758-24.476-23.758-45.215s7.9752-31.932 22.64-31.932 25.994 24.476 25.994 45.215z"/>
        <path fill={color} d="m322.95 253.12c2.2361 32.07-11.888 43.177-26.553 43.177s-29.907-14.044-26.553-43.177c2.7255-23.673 10.77-33.778 26.553-37.302 14.345-3.2034 26.553 13.457 26.553 37.302z"/>
      </g>
    </svg>
  )
}

/* ─── Huellas flotantes random en el fondo ───────────── */
function CatPawTrail() {
  const [paws, setPaws] = useState([])
  const idRef = useRef(0)

  useEffect(() => {
    const spawn = () => {
      const id = idRef.current++
      const x = 5 + Math.random() * 88
      const y = 10 + Math.random() * 78
      const size = 16 + Math.random() * 24
      const rotate = Math.random() * 360
      setPaws(prev => [...prev, { id, x, y, size, rotate }])
      setTimeout(() => setPaws(prev => prev.filter(p => p.id !== id)), 4500)
    }
    const t1 = setTimeout(spawn, 2000)
    const t2 = setTimeout(spawn, 4500)
    const interval = setInterval(spawn, 7000 + Math.random() * 6000)
    return () => { clearTimeout(t1); clearTimeout(t2); clearInterval(interval) }
  }, [])

  return (
    <div style={{ position: 'absolute', inset: 0, zIndex: 1, pointerEvents: 'none', overflow: 'hidden' }}>
      {paws.map(p => (
        <motion.div
          key={p.id}
          initial={{ opacity: 0, scale: 0.4 }}
          animate={{ opacity: [0, 0.15, 0.15, 0] }}
          transition={{ duration: 4, ease: 'easeInOut' }}
          style={{ position: 'absolute', left: `${p.x}%`, top: `${p.y}%` }}
        >
          <CatPaw size={p.size} color="#e8742a" rotate={p.rotate} />
        </motion.div>
      ))}
    </div>
  )
}

/* ─── Constantes ─────────────────────────────────────── */
const QUICK_COMMANDS = [
  { cmd: '/metricas',     desc: 'Métricas generales del dataset' },
  { cmd: '/embudo',       desc: 'Cuello de botella del funnel' },
  { cmd: '/rfm',          desc: 'Segmentación RFM de leads' },
  { cmd: '/rentabilidad', desc: 'CAC · LTV · ROI por campaña' },
  { cmd: '/outliers',     desc: 'Detectar valores anómalos' },
  { cmd: '/cohorts',      desc: 'Cohortes por mes de entrada' },
]

/* ─── Main ───────────────────────────────────────────── */
export default function Home() {
  const navigate  = useNavigate()
  const [analyses, setAnalyses] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [query,    setQuery]    = useState('')

  useEffect(() => {
    getAnalyses().then(setAnalyses).catch(console.error).finally(() => setLoading(false))
  }, [])

  const handleSubmit         = (e) => { e.preventDefault(); if (!query.trim()) return; navigate('/new', { state: { initialQuery: query.trim() } }) }
  const handleCommand        = (cmd) => navigate('/new', { state: { initialQuery: cmd } })
  const handleSelectAnalysis = (id)  => navigate(`/chat/${id}`)

  return (
    <div style={{ minHeight: '100vh', overflowX: 'hidden' }}>
      <Hero query={query} setQuery={setQuery} onSubmit={handleSubmit} />

      <div style={{ position: 'relative', zIndex: 2 }}>
        <RevealSection delay={0}>
          <Section label="Comandos rápidos">
            <div style={{ background: '#080808', border: '1px solid #1c1c1c', borderRadius: 12, overflow: 'hidden' }}>
              {QUICK_COMMANDS.map((c) => (
                <CommandRow key={c.cmd} cmd={c.cmd} desc={c.desc} onClick={() => handleCommand(c.cmd)} />
              ))}
            </div>
          </Section>
        </RevealSection>

        <RevealSection delay={0.15}>
          <Section label="Análisis recientes">
            {loading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
                <Spinner size={28} color="#e8742a" />
              </div>
            ) : analyses.length === 0 ? (
              <EmptyState onNew={() => navigate('/new')} />
            ) : (
              <div style={{ background: '#080808', border: '1px solid #1c1c1c', borderRadius: 12, overflow: 'hidden' }}>
                {analyses.map((a, i) => (
                  <AnalysisRow key={a.id} analysis={a} index={i} onClick={() => handleSelectAnalysis(a.id)} />
                ))}
              </div>
            )}
          </Section>
        </RevealSection>

        <RevealSection delay={0.3}>
          <Section label="Estado del dataset activo">
            <DatasetStatus analyses={analyses} loading={loading} />
          </Section>
        </RevealSection>

        <div style={{ borderTop: '1px solid #0f0f0f', padding: '24px 40px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 11, color: '#222', fontFamily: 'JetBrains Mono, monospace', letterSpacing: '0.08em' }}>ADLY · DATA INTEGRITY LAYER</span>
          <span style={{ fontSize: 11, color: '#222', fontFamily: 'JetBrains Mono, monospace' }}>Groq · Llama 3.3 70b</span>
        </div>
      </div>
    </div>
  )
}

/* ─── Hero ───────────────────────────────────────────── */
function Hero({ query, setQuery, onSubmit }) {
  const inputRef = useRef(null)
  useEffect(() => { const t = setTimeout(() => inputRef.current?.focus(), 900); return () => clearTimeout(t) }, [])

  return (
    <div style={{ position: 'relative', minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 24px', overflow: 'hidden' }}>
      <HaloBg />
      <CatPawTrail />

      <div style={{ position: 'relative', zIndex: 2, textAlign: 'center', maxWidth: 680, width: '100%' }}>

        {/* Wordmark con huella flotando encima */}
        <motion.div
          initial={{ opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          style={{ position: 'relative', display: 'inline-block', marginBottom: 22 }}
        >
          <motion.div
            animate={{ y: [0, -6, 0], rotate: [-8, -13, -8] }}
            transition={{ duration: 4.5, repeat: Infinity, ease: 'easeInOut' }}
            style={{ position: 'absolute', top: -32, left: '50%', transform: 'translateX(-50%)', opacity: 0.65 }}
          >
            <CatPaw size={38} color="#e8742a" rotate={-10} />
          </motion.div>

          <h1 style={{
            fontSize: 'clamp(80px, 15vw, 148px)',
            fontWeight: 700,
            color: '#ffffff',
            fontFamily: 'Inter, sans-serif',
            letterSpacing: '-0.045em',
            lineHeight: 0.95,
            margin: 0,
          }}>
            Adly
          </h1>
        </motion.div>

        {/* Subtítulo */}
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.18, ease: [0.16, 1, 0.3, 1] }}
          style={{ fontSize: 'clamp(13px, 2vw, 17px)', color: '#444', fontFamily: 'Inter, sans-serif', fontWeight: 400, marginBottom: 52, letterSpacing: '-0.01em' }}
        >
          Tu analista de datos de marketing
        </motion.p>

        {/* Input */}
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.9, delay: 0.32, ease: [0.16, 1, 0.3, 1] }}
        >
          <form className="input-scanner" onSubmit={onSubmit} style={{ position: 'relative', borderRadius: 14 }}>
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="¿Cuál campaña tuvo mejor ROAS esta semana?"
              style={{
                width: '100%',
                padding: '18px 64px 18px 24px',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(232,116,42,0.18)',
                borderRadius: 14,
                color: '#eeeeee',
                fontSize: 15,
                fontFamily: 'Inter, sans-serif',
                outline: 'none',
                transition: 'border-color 0.25s ease, background 0.25s ease, box-shadow 0.25s ease',
                caretColor: '#e8742a',
              }}
              onFocus={(e) => {
                e.target.style.borderColor = 'rgba(232,116,42,0.55)'
                e.target.style.background  = 'rgba(255,255,255,0.06)'
                e.target.style.boxShadow   = '0 0 0 3px rgba(232,116,42,0.08), 0 0 24px rgba(232,116,42,0.07)'
              }}
              onBlur={(e) => {
                e.target.style.borderColor = 'rgba(232,116,42,0.18)'
                e.target.style.background  = 'rgba(255,255,255,0.04)'
                e.target.style.boxShadow   = 'none'
              }}
            />
            <button
              type="submit"
              style={{
                position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                width: 38, height: 38,
                background: query.trim() ? '#e8742a' : 'rgba(255,255,255,0.05)',
                border: 'none', borderRadius: 9,
                cursor: query.trim() ? 'pointer' : 'default',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 0.2s ease',
              }}
            >
              <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke={query.trim() ? '#fff' : '#333'} strokeWidth={2.5}>
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>
          </form>

          <p style={{ marginTop: 16, fontSize: 11, color: '#2a2a2a', fontFamily: 'JetBrains Mono, monospace', letterSpacing: '0.05em' }}>
            escribe una pregunta · o usa /comandos abajo
          </p>
        </motion.div>
      </div>

      {/* Scroll arrow */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.4, duration: 1 }}
        style={{ position: 'absolute', bottom: 32, left: '50%', transform: 'translateX(-50%)', zIndex: 2 }}
      >
        <motion.div animate={{ y: [0, 7, 0] }} transition={{ duration: 2.6, repeat: Infinity, ease: 'easeInOut' }}>
          <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="#2a2a2a" strokeWidth={1.5}>
            <path d="M12 5v14M5 12l7 7 7-7" />
          </svg>
        </motion.div>
      </motion.div>
    </div>
  )
}

/* ─── Halo background ────────────────────────────────── */
function HaloBg() {
  return (
    <>
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(108deg, transparent 30%, rgba(232,116,42,0.03) 50%, transparent 70%)',
        backgroundSize: '200% 200%',
        animation: 'shimmer 12s ease-in-out infinite',
        pointerEvents: 'none', zIndex: 1,
      }} />
      <motion.div
        animate={{ scale: [1, 1.12, 1], opacity: [0.8, 1, 0.8] }}
        transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
          width: '85vw', height: '85vw', maxWidth: 960, maxHeight: 960,
          background: 'radial-gradient(ellipse at center, rgba(232,116,42,0.18) 0%, rgba(232,116,42,0.06) 38%, transparent 65%)',
          borderRadius: '50%', pointerEvents: 'none', zIndex: 0,
        }}
      />
      <motion.div
        animate={{ scale: [1.08, 1, 1.08], opacity: [0.45, 0.8, 0.45] }}
        transition={{ duration: 13, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          position: 'absolute', top: '44%', left: '50%', transform: 'translate(-50%, -50%)',
          width: '50vw', height: '50vw', maxWidth: 580, maxHeight: 580,
          background: 'radial-gradient(ellipse at center, rgba(232,116,42,0.1) 0%, transparent 65%)',
          borderRadius: '50%', pointerEvents: 'none', zIndex: 0,
        }}
      />
      {/* Vignette perimetral */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,0.75) 100%)',
        pointerEvents: 'none', zIndex: 1,
      }} />
    </>
  )
}

/* ─── Scroll reveal wrapper ──────────────────────────── */
function RevealSection({ children, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 32 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.6, delay, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  )
}

/* ─── Section ────────────────────────────────────────── */
function Section({ label, children }) {
  return (
    <div style={{ padding: '0 40px', marginBottom: 56 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
        <CatPaw size={12} color="#e8742a" opacity={0.5} rotate={-20} />
        <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono, monospace', color: '#e8742a', letterSpacing: '0.15em', textTransform: 'uppercase', fontWeight: 500 }}>
          {label}
        </span>
        <div style={{ flex: 1, height: '1px', background: 'linear-gradient(90deg, #1c1c1c, transparent)' }} />
      </div>
      {children}
    </div>
  )
}

/* ─── Command row ────────────────────────────────────── */
function CommandRow({ cmd, desc, onClick }) {
  const [hovered, setHovered] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 20,
        padding: '13px 20px',
        background: hovered ? 'rgba(232,116,42,0.05)' : 'transparent',
        border: 'none', borderBottom: '1px solid #0e0e0e',
        borderLeft: hovered ? '2px solid rgba(232,116,42,0.45)' : '2px solid transparent',
        cursor: 'pointer', textAlign: 'left',
        transition: 'all 0.15s ease', width: '100%',
      }}
    >
      <span style={{ fontSize: 12, fontFamily: 'JetBrains Mono, monospace', color: hovered ? '#e8742a' : '#383838', minWidth: 130, transition: 'color 0.15s ease', fontWeight: 500 }}>
        {cmd}
      </span>
      <span style={{ fontSize: 12, fontFamily: 'Inter, sans-serif', color: '#2c2c2c' }}>{desc}</span>
    </button>
  )
}

/* ─── Analysis row ───────────────────────────────────── */
function AnalysisRow({ analysis, onClick }) {
  const [hovered, setHovered] = useState(false)
  const conf = analysis.confidence
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16,
        padding: '15px 20px',
        background: hovered ? 'rgba(232,116,42,0.05)' : 'transparent',
        border: 'none', borderBottom: '1px solid #0e0e0e',
        borderLeft: hovered ? '2px solid rgba(232,116,42,0.45)' : '2px solid transparent',
        cursor: 'pointer', textAlign: 'left',
        transition: 'all 0.15s ease', width: '100%',
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: hovered ? '#ffffff' : '#aaaaaa', fontFamily: 'Inter, sans-serif', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', transition: 'color 0.15s ease', marginBottom: 4 }}>
          {analysis.name}
        </div>
        <div style={{ fontSize: 11, color: '#2a2a2a', fontFamily: 'JetBrains Mono, monospace', display: 'flex', gap: 10 }}>
          <span>{analysis.dataset}</span><span>·</span><span>{formatDate(analysis.created_at)}</span>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        {conf != null && <PawConfidence value={conf} />}
        <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke={hovered ? '#e8742a' : '#1f1f1f'} strokeWidth={2} style={{ transition: 'stroke 0.15s ease' }}>
          <path d="M9 18l6-6-6-6" />
        </svg>
      </div>
    </button>
  )
}

/* ─── Confidence = huellas de gato ───────────────────── */
function PawConfidence({ value }) {
  const total  = 5
  const filled = Math.round(value * total)
  const color  = value >= 0.7 ? '#4ade80' : value >= 0.4 ? '#e8742a' : '#f87171'
  return (
    <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
      {Array.from({ length: total }).map((_, i) => (
        <CatPaw key={i} size={10} color={i < filled ? color : '#1e1e1e'} rotate={i % 2 === 0 ? -15 : 15} />
      ))}
    </div>
  )
}

/* ─── Dataset status ─────────────────────────────────── */
function DatasetStatus({ analyses, loading }) {
  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}><Spinner size={24} color="#e8742a" /></div>
  const total     = analyses.length
  const fresh     = analyses.filter(a => a.confidence >= 0.7).length
  const stale     = analyses.filter(a => a.confidence  < 0.4).length
  const integrity = total > 0 ? Math.round((fresh / total) * 100) : 0
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', background: '#080808', border: '1px solid #1c1c1c', borderRadius: 12, overflow: 'hidden' }}>
      <StatusCell label="Análisis totales" value={total} />
      <StatusCell label="Datos frescos"    value={fresh}  accent="#4ade80" />
      <StatusCell label="Datos viejos"     value={stale}  accent="#f87171" />
      <StatusCell label="Integridad"       value={`${integrity}%`} accent={integrity >= 70 ? '#4ade80' : '#e8742a'} />
    </div>
  )
}

function StatusCell({ label, value, accent }) {
  return (
    <div style={{ padding: '22px 24px', borderRight: '1px solid #111' }}>
      <div style={{ fontSize: 10, fontFamily: 'JetBrains Mono, monospace', color: '#282828', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>{label}</div>
      <div style={{ fontSize: 30, fontWeight: 600, color: accent || '#eeeeee', fontFamily: 'Inter, sans-serif', letterSpacing: '-0.03em', lineHeight: 1 }}>{value}</div>
    </div>
  )
}

/* ─── Empty state ────────────────────────────────────── */
function EmptyState({ onNew }) {
  return (
    <div style={{ padding: '40px 24px', textAlign: 'center', border: '1px solid #111', borderRadius: 12 }}>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center', opacity: 0.15 }}>
        <CatPaw size={36} color="#e8742a" />
      </div>
      <p style={{ fontSize: 13, color: '#2a2a2a', fontFamily: 'Inter, sans-serif', marginBottom: 16 }}>
        No hay análisis — escribe una pregunta arriba para empezar
      </p>
      <button
        onClick={onNew}
        style={{ padding: '8px 20px', background: 'transparent', border: '1px solid rgba(232,116,42,0.2)', borderRadius: 8, color: '#444', fontSize: 12, fontFamily: 'Inter, sans-serif', cursor: 'pointer' }}
        onMouseEnter={e => { e.target.style.borderColor = 'rgba(232,116,42,0.5)'; e.target.style.color = '#e8742a' }}
        onMouseLeave={e => { e.target.style.borderColor = 'rgba(232,116,42,0.2)'; e.target.style.color = '#444' }}
      >
        Nuevo análisis
      </button>
    </div>
  )
}

function formatDate(iso) {
  try { return new Date(iso).toLocaleDateString('es', { month: 'short', day: 'numeric' }) }
  catch { return '—' }
}
