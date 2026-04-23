import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate, useLocation } from 'react-router-dom'
import { getAnalyses } from '@/api/client'
import Spinner from '@/components/ui/Spinner'

/**
 * Sidebar with analysis list and navigation.
 * Collapsible on mobile.
 */
export default function Sidebar({ isOpen, onClose }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [analyses, setAnalyses] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAnalyses()
      .then(setAnalyses)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const handleSelect = (id) => {
    navigate(`/chat/${id}`)
    onClose?.()
  }

  const handleNew = () => {
    navigate('/new')
    onClose?.()
  }

  return (
    <>
      {/* Backdrop on mobile */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.5)',
              zIndex: 40,
              display: 'md:none',
            }}
          />
        )}
      </AnimatePresence>

      {/* Sidebar panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.aside
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            exit={{ x: -280 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            style={{
              position: 'fixed',
              left: 0,
              top: 0,
              bottom: 0,
              width: 280,
              background: '#151515',
              borderRight: '1px solid #2a2a2a',
              zIndex: 50,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* Header */}
            <div style={{
              padding: '16px',
              borderBottom: '1px solid #2a2a2a',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <h2 style={{
                margin: 0,
                fontSize: 14,
                fontWeight: 600,
                color: '#eeeeee',
                fontFamily: 'Inter, sans-serif',
              }}>
                Análisis
              </h2>
              <button
                onClick={onClose}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#666666',
                  cursor: 'pointer',
                  padding: 4,
                  display: 'flex',
                }}
              >
                <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* New Analysis Button */}
            <div style={{ padding: '12px 16px' }}>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleNew}
                style={{
                  width: '100%',
                  padding: '10px 16px',
                  background: '#e8742a',
                  border: 'none',
                  borderRadius: 6,
                  color: '#ffffff',
                  fontSize: 13,
                  fontWeight: 500,
                  fontFamily: 'Inter, sans-serif',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                }}
              >
                <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M12 5v14M5 12h14" />
                </svg>
                Nuevo Análisis
              </motion.button>
            </div>

            {/* Analysis list */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px 16px' }}>
              {loading ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
                  <Spinner size={24} color="#e8742a" />
                </div>
              ) : analyses.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: 24,
                  color: '#444444',
                  fontSize: 12,
                  fontFamily: 'Inter, sans-serif',
                }}>
                  No hay análisis todavía
                </div>
              ) : (
                analyses.map((analysis) => (
                  <AnalysisItem
                    key={analysis.id}
                    analysis={analysis}
                    isActive={location.pathname === `/chat/${analysis.id}`}
                    onClick={() => handleSelect(analysis.id)}
                  />
                ))
              )}
            </div>

            {/* Footer */}
            <div style={{
              padding: '12px 16px',
              borderTop: '1px solid #2a2a2a',
            }}>
              <button
                onClick={() => navigate('/home')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  background: 'none',
                  border: 'none',
                  color: '#666666',
                  fontSize: 12,
                  fontFamily: 'Inter, sans-serif',
                  cursor: 'pointer',
                  padding: '6px 8px',
                  borderRadius: 4,
                  width: '100%',
                  textAlign: 'left',
                }}
              >
                <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                </svg>
                Dashboard
              </button>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  )
}

/**
 * Single analysis item in the list.
 */
function AnalysisItem({ analysis, isActive, onClick }) {
  const formatDate = (iso) => {
    try {
      return new Date(iso).toLocaleDateString('es', { month: 'short', day: 'numeric' })
    } catch { return '' }
  }

  return (
    <motion.button
      whileHover={{ backgroundColor: 'rgba(232,116,42,0.08)' }}
      onClick={onClick}
      style={{
        width: '100%',
        padding: '10px 12px',
        background: isActive ? 'rgba(232,116,42,0.12)' : 'transparent',
        border: 'none',
        borderRadius: 6,
        cursor: 'pointer',
        textAlign: 'left',
        marginBottom: 4,
        borderLeft: `2px solid ${isActive ? '#e8742a' : 'transparent'}`,
        transition: 'background 0.15s ease',
      }}
    >
      <div style={{
        fontSize: 13,
        fontWeight: 500,
        color: isActive ? '#eeeeee' : '#cccccc',
        fontFamily: 'Inter, sans-serif',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}>
        {analysis.name}
      </div>
      <div style={{
        fontSize: 11,
        color: '#666666',
        fontFamily: 'JetBrains Mono, monospace',
        marginTop: 4,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}>
        <span>{formatDate(analysis.created_at)}</span>
        {analysis.confidence != null && (
          <span style={{
            color: analysis.confidence >= 0.7 ? '#22c55e' : analysis.confidence >= 0.4 ? '#e8742a' : '#dc2626',
          }}>
            {Math.round(analysis.confidence * 100)}%
          </span>
        )}
      </div>
    </motion.button>
  )
}