import { useState, useEffect } from 'react'
import { Routes, Route, useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { AdlyProvider } from '@/context/AdlyContext'

import Splash from '@/pages/Splash'
import Onboarding from '@/pages/Onboarding'
import Home from '@/pages/Home'
import NewAnalysis from '@/pages/NewAnalysis'
import Chat from '@/pages/Chat'
import AdlyFloat from '@/components/adly/AdlyFloat'
import { getAnalyses } from '@/api/client'
import Spinner from '@/components/ui/Spinner'

/* ─── Cat paw inline ─────────────────────────────────── */
function CatPaw({ size = 16, color = '#e8742a', rotate = 0 }) {
  return (
    <svg viewBox="0 0 274.2 244.33" width={size} height={size} style={{ display: 'block', transform: `rotate(${rotate}deg)` }}>
      <g transform="translate(-198.45 -215.42)">
        <path fill={color} d="m230.31 398.87c11.173-12.772 35.257-11.499 43.603-26.274 4.5828-8.1119-3.0615-19.151 0-27.951 1.8743-5.3872 5.5283-10.848 10.621-13.416 15.149-7.6391 31.161 0.75806 48.075-0.55902 12.167-0.94735 27.757-10.013 39.131-5.5902 9.3621 3.6405 17.244 13.147 19.566 22.92 2.1726 9.1459-5.0312 25.715-5.0312 27.951 0 2.2361 8.8885 17.525 19.566 23.479 6.3805 3.5577 19.401 0.86486 22.92 7.2672 5.4179 9.8594-3.1367 18-8.3852 27.951-2.6851 5.0907-9.959 14.729-15.093 17.33-11.897 6.0254-26.457-6.6822-39.69-5.0312-11.125 1.388-20.094 12.38-31.305 12.298-12.284-0.0898-21.821-14.335-34.1-13.975-10.33 0.30257-17.711 14.814-27.951 13.416-21.589-2.9467-44.406-21.788-49.193-43.044-1.3386-5.9436 3.2559-12.185 7.2672-16.77z" />
        <path fill={color} d="m249.32 323.68c3.3541 29.4-12.447 36.616-27.112 36.616s-23.758-13.364-23.758-36.057c0-22.692 14.124-41.647 28.789-41.647s22.081 18.396 22.081 41.088z" />
        <path fill={color} d="m402.77 255.2c2.2361 30.518-11.888 41.088-26.553 41.088s-29.907-13.364-26.553-41.088c2.7255-22.528 11.888-35.498 26.553-35.498s26.553 12.805 26.553 35.498z" />
        <path fill={color} d="m472.65 326.41c0 20.739-10.219 31.487-24.876 31.932-33.672 1.0218-23.758-24.476-23.758-45.215s7.9752-31.932 22.64-31.932 25.994 24.476 25.994 45.215z" />
        <path fill={color} d="m322.95 253.12c2.2361 32.07-11.888 43.177-26.553 43.177s-29.907-14.044-26.553-43.177c2.7255-23.673 10.77-33.778 26.553-37.302 14.345-3.2034 26.553 13.457 26.553 37.302z" />
      </g>
    </svg>
  )
}

const SIDEBAR_W = 260

export default function App() {
  const location = useLocation()
  const [desktopOpen, setDesktopOpen] = useState(true)
  const [mobileOpen, setMobileOpen] = useState(false)

  const showSidebar = ['/home', '/new', '/chat'].some(p => location.pathname.startsWith(p))

  return (
    <AdlyProvider>
      <div className="adly-bg" style={{ display: 'flex', minHeight: '100vh' }}>

        {/* Desktop sidebar */}
        <AnimatePresence initial={false}>
          {showSidebar && desktopOpen && (
            <motion.div
              key="dsk-sb"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: SIDEBAR_W, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ type: 'spring', damping: 28, stiffness: 280 }}
              className="hidden md:block"
              style={{ flexShrink: 0, overflow: 'hidden', position: 'relative', zIndex: 10 }}
            >
              <div style={{ position: 'fixed', left: 0, top: 0, bottom: 0, width: SIDEBAR_W }}>
                <DesktopSidebar onClose={() => setDesktopOpen(false)} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Main content */}
        <main style={{ flex: 1, minWidth: 0 }}>

          {/* Botón para reabrir sidebar en desktop */}
          <AnimatePresence>
            {showSidebar && !desktopOpen && (
              <motion.button
                key="reopen-btn"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                onClick={() => setDesktopOpen(true)}
                className="hidden md:flex"
                style={{
                  position: 'fixed', top: 14, left: 14, zIndex: 30,
                  background: '#0e0e0e',
                  border: '1px solid rgba(232,116,42,0.2)',
                  borderRadius: 8, padding: '7px 10px',
                  cursor: 'pointer', alignItems: 'center', gap: 6,
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = 'rgba(232,116,42,0.5)'}
                onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(232,116,42,0.2)'}
              >
                <CatPaw size={13} color="#e8742a" />
                <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="#555" strokeWidth={2}>
                  <path d="M3 12h18M3 6h18M3 18h18" />
                </svg>
              </motion.button>
            )}
          </AnimatePresence>

          {/* Botón mobile */}
          {showSidebar && (
            <button
              onClick={() => setMobileOpen(true)}
              className="flex md:hidden"
              style={{
                position: 'fixed', top: 12, left: 12, zIndex: 30,
                background: '#0e0e0e',
                border: '1px solid rgba(232,116,42,0.2)',
                borderRadius: 8, padding: 8, cursor: 'pointer',
              }}
            >
              <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="#666" strokeWidth={2}>
                <path d="M3 12h18M3 6h18M3 18h18" />
              </svg>
            </button>
          )}

          <AnimatePresence mode="wait" initial={false}>
            <Routes location={location} key={location.pathname}>
              <Route path="/" element={<Splash />} />
              <Route path="/onboarding" element={<Onboarding />} />
              <Route path="/home" element={<Home />} />
              <Route path="/new" element={<NewAnalysis />} />
              <Route path="/chat/:id" element={<Chat />} />
            </Routes>
          </AnimatePresence>
        </main>

        {/* Mobile drawer */}
        {showSidebar && <MobileSidebar isOpen={mobileOpen} onClose={() => setMobileOpen(false)} />}

        {/* AdlyFloat */}
        <div className="hidden md:block" style={{ position: 'fixed', bottom: 20, right: 20, zIndex: 100 }}>
          <AdlyFloat />
        </div>
      </div>
    </AdlyProvider>
  )
}

/* ─── Desktop sidebar ────────────────────────────────── */
function DesktopSidebar({ onClose }) {
  return (
    <div style={{
      width: SIDEBAR_W, height: '100%',
      background: 'rgba(4,4,4,0.45)', backdropFilter: 'blur(24px) saturate(1.6)', WebkitBackdropFilter: 'blur(24px) saturate(1.6)',
      borderRight: '1px solid rgba(232,116,42,0.1)',
      display: 'flex', flexDirection: 'column',
    }}>
      <div style={{ padding: '14px 16px', borderBottom: '1px solid rgba(232,116,42,0.07)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <CatPaw size={13} color="#e8742a" rotate={-15} />
          <span style={{ fontSize: 13, fontWeight: 600, color: '#ddd', fontFamily: 'Inter, sans-serif' }}>Análisis</span>
        </div>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer', padding: 4, borderRadius: 4, display: 'flex', transition: 'color 0.15s' }}
          onMouseEnter={e => e.currentTarget.style.color = '#e8742a'}
          onMouseLeave={e => e.currentTarget.style.color = '#555'}
          title="Cerrar"
        >
          <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div style={{ padding: '12px 14px' }}>
        <SidebarButton onClick={() => window.location.href = '/new'}>
          <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}><path d="M12 5v14M5 12h14" /></svg>
          Nuevo Análisis
        </SidebarButton>
      </div>
      <SidebarList />
    </div>
  )
}

/* ─── Mobile drawer ──────────────────────────────────── */
function MobileSidebar({ isOpen, onClose }) {
  return (
    <>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
            className="md:hidden"
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 40 }}
          />
        )}
      </AnimatePresence>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ x: -SIDEBAR_W }} animate={{ x: 0 }} exit={{ x: -SIDEBAR_W }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="md:hidden"
            style={{ position: 'fixed', left: 0, top: 0, bottom: 0, width: SIDEBAR_W, background: 'rgba(4,4,4,0.45)', backdropFilter: 'blur(24px) saturate(1.6)', WebkitBackdropFilter: 'blur(24px) saturate(1.6)', borderRight: '1px solid rgba(232,116,42,0.12)', zIndex: 50, display: 'flex', flexDirection: 'column' }}
          >
            <div style={{ padding: '14px 16px', borderBottom: '1px solid rgba(232,116,42,0.07)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <CatPaw size={13} color="#e8742a" rotate={-15} />
                <span style={{ fontSize: 13, fontWeight: 600, color: '#ddd', fontFamily: 'Inter, sans-serif' }}>Análisis</span>
              </div>
              <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#444', cursor: 'pointer', padding: 4 }}>
                <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M18 6L6 18M6 6l12 12" /></svg>
              </button>
            </div>
            <div style={{ padding: '12px 14px' }}>
              <SidebarButton onClick={() => { window.location.href = '/new'; onClose() }}>
                <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}><path d="M12 5v14M5 12h14" /></svg>
                Nuevo Análisis
              </SidebarButton>
            </div>
            <SidebarList onItemClick={onClose} />
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

/* ─── Shared sidebar button ──────────────────────────── */
function SidebarButton({ children, onClick }) {
  return (
    <motion.button
      whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
      onClick={onClick}
      style={{ width: '100%', padding: '9px 14px', background: '#e8742a', border: 'none', borderRadius: 6, color: '#fff', fontSize: 13, fontWeight: 500, fontFamily: 'Inter, sans-serif', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7 }}
    >
      {children}
    </motion.button>
  )
}

/* ─── Sidebar list ───────────────────────────────────── */
function SidebarList({ onItemClick }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [analyses, setAnalyses] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAnalyses().then(setAnalyses).catch(console.error).finally(() => setLoading(false))
  }, [])

  const handleSelect = (id) => { navigate(`/chat/${id}`); onItemClick?.() }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px 16px' }}>
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}><Spinner size={22} color="#e8742a" /></div>
      ) : analyses.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 24, color: '#555555', fontSize: 12, fontFamily: 'Inter, sans-serif' }}>No hay análisis todavía</div>
      ) : (
        analyses.map((analysis) => {
          const active = location.pathname === `/chat/${analysis.id}`
          const conf = analysis.confidence
          return (
            <motion.button
              key={analysis.id}
              whileHover={{ backgroundColor: 'rgba(232,116,42,0.06)' }}
              onClick={() => handleSelect(analysis.id)}
              style={{
                width: '100%', padding: '10px 12px',
                background: active ? 'rgba(232,116,42,0.1)' : 'transparent',
                border: 'none',
                borderLeft: `2px solid ${active ? '#e8742a' : 'transparent'}`,
                borderRadius: '0 6px 6px 0',
                cursor: 'pointer', textAlign: 'left', marginBottom: 2,
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 500, color: active ? '#eee' : '#bbb', fontFamily: 'Inter, sans-serif', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {analysis.name}
              </div>
              <div style={{ fontSize: 11, color: '#6a5a48', fontFamily: 'JetBrains Mono, monospace', marginTop: 3, display: 'flex', gap: 8 }}>
                <span>{formatDate(analysis.created_at)}</span>
                {conf != null && (
                  <span style={{ color: conf >= 0.7 ? '#4ade80' : conf >= 0.4 ? '#e8742a' : '#f87171' }}>
                    {Math.round(conf * 100)}%
                  </span>
                )}
              </div>
            </motion.button>
          )
        })
      )}
    </div>
  )
}

function formatDate(iso) {
  try { return new Date(iso).toLocaleDateString('es', { month: 'short', day: 'numeric' }) }
  catch { return '' }
}
