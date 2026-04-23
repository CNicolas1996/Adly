import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { getConfig } from '@/api/client'

/* ─── Halo background (mismo que Home) ─────────────────── */
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
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,0.75) 100%)',
        pointerEvents: 'none', zIndex: 1,
      }} />
    </>
  )
}

/* ─── Animated Loading Paw ───────────────────────────── */
function LoadingPaw({ size = 80, color = '#e8742a', progress = 0 }) {
  const p = Math.min(Math.max(progress, 0), 100);
  const pathData = [
    "m230.31 398.87c11.173-12.772 35.257-11.499 43.603-26.274 4.5828-8.1119-3.0615-19.151 0-27.951 1.8743-5.3872 5.5283-10.848 10.621-13.416 15.149-7.6391 31.161 0.75806 48.075-0.55902 12.167-0.94735 27.757-10.013 39.131-5.5902 9.3621 3.6405 17.244 13.147 19.566 22.92 2.1726 9.1459-5.0312 25.715-5.0312 27.951 0 2.2361 8.8885 17.525 19.566 23.479 6.3805 3.5577 19.401 0.86486 22.92 7.2672 5.4179 9.8594-3.1367 18-8.3852 27.951-2.6851 5.0907-9.959 14.729-15.093 17.33-11.897 6.0254-26.457-6.6822-39.69-5.0312-11.125 1.388-20.094 12.38-31.305 12.298-12.284-0.0898-21.821-14.335-34.1-13.975-10.33 0.30257-17.711 14.814-27.951 13.416-21.589-2.9467-44.406-21.788-49.193-43.044-1.3386-5.9436 3.2559-12.185 7.2672-16.77z",
    "m249.32 323.68c3.3541 29.4-12.447 36.616-27.112 36.616s-23.758-13.364-23.758-36.057c0-22.692 14.124-41.647 28.789-41.647s22.081 18.396 22.081 41.088z",
    "m402.77 255.2c2.2361 30.518-11.888 41.088-26.553 41.088s-29.907-13.364-26.553-41.088c2.7255-22.528 11.888-35.498 26.553-35.498s26.553 12.805 26.553 35.498z",
    "m472.65 326.41c0 20.739-10.219 31.487-24.876 31.932-33.672 1.0218-23.758-24.476-23.758-45.215s7.9752-31.932 22.64-31.932 25.994 24.476 25.994 45.215z",
    "m322.95 253.12c2.2361 32.07-11.888 43.177-26.553 43.177s-29.907-14.044-26.553-43.177c2.7255-23.673 10.77-33.778 26.553-37.302 14.345-3.2034 26.553 13.457 26.553 37.302z"
  ];

  return (
    <svg viewBox="0 0 274.2 244.33" width={size} height={size} style={{ display: 'block', margin: '0 auto' }}>
      <defs>
        <clipPath id="paw-fill-clip">
          <rect x="0" y={`${100 - p}%`} width="100%" height={`${p}%`} style={{ transition: 'all 0.2s ease-out' }} />
        </clipPath>
      </defs>
      {/* Fondo oscuro de la huella */}
      <g transform="translate(-198.45 -215.42)">
        {pathData.map((d, i) => <path key={`bg-${i}`} fill="#1c1c1c" d={d} />)}
      </g>
      {/* Huella rellenada con clip path */}
      <g clipPath="url(#paw-fill-clip)">
        <g transform="translate(-198.45 -215.42)">
          {pathData.map((d, i) => <path key={`fg-${i}`} fill={color} d={d} />)}
        </g>
      </g>
    </svg>
  )
}

export default function Splash() {
  const navigate = useNavigate()
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    // Simulated loading progress
    const interval = setInterval(() => {
      setProgress(p => {
        if (p >= 100) {
          clearInterval(interval)
          return 100
        }
        return p + Math.random() * 30
      })
    }, 200)

    // Check if user is already configured
    getConfig()
      .then(config => {
        setTimeout(() => {
          // Navigate based on config status
          if (config.data_source === 'mock') {
            navigate('/onboarding')
          } else {
            navigate('/home')
          }
        }, 800)
      })
      .catch(() => {
        setTimeout(() => navigate('/onboarding'), 1200)
      })

    return () => clearInterval(interval)
  }, [navigate])

  return (
    <motion.div
      className="flex items-center justify-center min-h-screen"
      style={{ background: '#000', position: 'relative', overflow: 'hidden' }}
      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
    >
      <HaloBg />
      <div style={{ position: 'relative', zIndex: 2, textAlign: 'center', color: '#eeeeee' }}>
        <LoadingPaw size={80} color="#e8742a" progress={progress} />
        
        <h1 style={{
          fontSize: 'clamp(80px, 15vw, 148px)',
          fontWeight: 700,
          color: '#ffffff',
          fontFamily: 'Inter, sans-serif',
          letterSpacing: '-0.045em',
          lineHeight: 0.95,
          margin: '16px 0 0 0',
        }}>
          Adly
        </h1>

        <div style={{ color: '#555555', fontSize: 11, marginTop: 12, fontFamily: 'JetBrains Mono, monospace' }}>
          cargando... {Math.min(Math.round(progress), 100)}%
        </div>
      </div>
    </motion.div>
  )
}
