import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Message from './Message'
import InputZone from './InputZone'
import Spinner from '@/components/ui/Spinner'
import { useAnalysis } from '@/hooks/useAnalysis'

const PAW_CSS = `
  @keyframes paw-step {
    0%, 100% { opacity: 0; transform: scale(0.55); }
    12%       { opacity: 1; transform: scale(1.08); }
    28%       { opacity: 1; transform: scale(1);    }
    42%       { opacity: 0; transform: scale(0.75); }
  }
`

// Single cat paw print — inline SVG, no external assets
function PawPrint({ rotate = 0, nudgeY = 0 }) {
  return (
    <svg
      width="18"
      height="20"
      viewBox="0 0 18 20"
      fill="#e8742a"
      style={{ transform: `rotate(${rotate}deg) translateY(${nudgeY}px)`, flexShrink: 0 }}
      aria-hidden="true"
    >
      {/* Main pad */}
      <ellipse cx="9" cy="15" rx="5.5" ry="4.5" />
      {/* Toe pads */}
      <ellipse cx="2"  cy="9"  rx="2.4" ry="1.9" transform="rotate(-18 2 9)"  />
      <ellipse cx="6"  cy="5.5" rx="2.4" ry="1.9" transform="rotate(-5 6 5.5)" />
      <ellipse cx="12" cy="5.5" rx="2.4" ry="1.9" transform="rotate(5 12 5.5)" />
      <ellipse cx="16" cy="9"  rx="2.4" ry="1.9" transform="rotate(18 16 9)" />
    </svg>
  )
}

// 4 paws in walking gait: LF → RR → RF → LR
// Alternate left (neg rotate, nudge down) / right (pos rotate)
const PAWS = [
  { rotate: -15, nudgeY: 0 },  // Left Front
  { rotate:  15, nudgeY: 4 },  // Right Rear
  { rotate:  15, nudgeY: 0 },  // Right Front
  { rotate: -15, nudgeY: 4 },  // Left Rear
]
const CYCLE = 1.6   // seconds total
const STEP  = CYCLE / PAWS.length  // 0.4s stagger

function TypingPaws() {
  return (
    <div
      style={{
        display:    'flex',
        alignItems: 'center',
        gap:        10,
        padding:    '10px 16px 4px',
      }}
    >
      {PAWS.map((p, i) => (
        <div
          key={i}
          style={{
            animation:  `paw-step ${CYCLE}s ${i * STEP}s infinite ease-in-out`,
            opacity:    0,
            display:    'flex',
            alignItems: 'center',
          }}
        >
          <PawPrint rotate={p.rotate} nudgeY={p.nudgeY} />
        </div>
      ))}
    </div>
  )
}

/**
 * Full chat interface: message list + input.
 * Accepts analysisId to load messages for that analysis.
 */
export default function ChatWindow({ analysisId, onBack }) {
  const {
    messages,
    dataset,
    loading,
    sending,
    error,
    sendMessage,
    onUserTyping,
    onUserStopTyping,
  } = useAnalysis(analysisId)

  const messagesEndRef = useRef(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  const handleSend = async (text) => {
    await sendMessage(text)
  }

  if (!analysisId) {
    return <EmptyState onBack={onBack} message="Selecciona un análisis para comenzar" />
  }

  if (loading) {
    return (
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#1a1a1a',
      }}>
        <Spinner size={32} color="#e8742a" />
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      background: '#000',
    }}>
      <style>{PAW_CSS}</style>
      {/* Header */}
      <ChatHeader dataset={dataset} onBack={onBack} />

      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '16px 0',
      }}>
        {messages.length === 0 ? (
          <EmptyState message="¡Hola! Saya es Adly, tu analista de datos. ¿En qué puedo ayudarte?" />
        ) : (
          <div style={{ padding: '0 16px' }}>
            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <Message key={msg.id} {...msg} />
              ))}
            </AnimatePresence>
            {sending && <TypingPaws />}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          style={{
            padding: '8px 16px',
            background: 'rgba(220, 53, 69, 0.15)',
            borderTop: '1px solid rgba(220, 53, 69, 0.3)',
            color: '#ff6b6b',
            fontSize: 13,
            fontFamily: 'Inter, sans-serif',
          }}
        >
          {error}
        </motion.div>
      )}

      {/* Input */}
      <InputZone
        onSend={handleSend}
        onTyping={onUserTyping}
        onStopTyping={onUserStopTyping}
        disabled={sending}
        placeholder="Escribe tu pregunta sobre los datos..."
      />
    </div>
  )
}

/**
 * Simple header showing dataset info.
 */
function ChatHeader({ dataset, onBack }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '12px 16px',
      borderBottom: '1px solid rgba(232,116,42,0.08)',
      background: '#050505',
    }}>
      {/* Back button */}
      {onBack && (
        <button
          onClick={onBack}
          style={{
            background: 'none',
            border: 'none',
            color: '#666666',
            cursor: 'pointer',
            padding: 4,
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
        </button>
      )}

      {/* Dataset info */}
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: '#eeeeee', fontFamily: 'Inter, sans-serif' }}>
          Análisis de datos
        </div>
        {dataset && (
          <div style={{ fontSize: 11, color: '#666666', fontFamily: 'JetBrains Mono, monospace', marginTop: 2 }}>
            {dataset.records} registros · integridad {dataset.integrity}%
          </div>
        )}
      </div>

      {/* Status indicator */}
      {dataset && (
        <div style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: dataset.integrity >= 70 ? '#22c55e' : dataset.integrity >= 40 ? '#e8742a' : '#dc2626',
        }} />
      )}
    </div>
  )
}

/**
 * Empty state placeholder.
 */
function EmptyState({ message, onBack }) {
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#1a1a1a',
      padding: 32,
    }}>
      <div style={{
        width: 64,
        height: 64,
        marginBottom: 16,
        opacity: 0.6,
      }}>
        <svg viewBox="0 0 24 24" fill="none" stroke="#e8742a" strokeWidth={1.5}>
          <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
      </div>
      <p style={{
        color: '#666666',
        fontSize: 14,
        fontFamily: 'Inter, sans-serif',
        textAlign: 'center',
        maxWidth: 280,
      }}>
        {message}
      </p>
    </div>
  )
}