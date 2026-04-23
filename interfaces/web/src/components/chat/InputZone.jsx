import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

/**
 * Chat input with send button.
 * - Enter sends, Shift+Enter adds newline
 * - Shows character count on hover/focus
 * - Disabled state when sending
 */
export default function InputZone({ onSend, onTyping, onStopTyping, disabled, placeholder = 'Escribe tu pregunta...' }) {
  const [text, setText] = useState('')
  const textareaRef = useRef(null)

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px'
    }
  }, [text])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSend = () => {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
    onStopTyping?.()
  }

  const handleChange = (e) => {
    setText(e.target.value)
    if (e.target.value.trim()) {
      onTyping?.()
    } else {
      onStopTyping?.()
    }
  }

  const charCount = text.length

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: 10,
        padding: '12px 16px',
        background: '#151515',
        borderTop: '1px solid #2a2a2a',
      }}
    >
      {/* Textarea */}
      <div style={{ flex: 1, position: 'relative' }}>
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          rows={1}
          style={{
            width: '100%',
            background: '#1a1a1a',
            border: '1px solid #2a2a2a',
            borderRadius: 8,
            padding: '10px 14px',
            color: '#eeeeee',
            fontFamily: 'Inter, sans-serif',
            fontSize: 14,
            lineHeight: 1.5,
            resize: 'none',
            outline: 'none',
            transition: 'border-color 0.15s ease',
          }}
          onFocus={(e) => e.target.style.borderColor = '#e8742a'}
          onBlur={(e) => e.target.style.borderColor = '#2a2a2a'}
        />
        {/* Character count hint */}
        <AnimatePresence>
          {charCount > 0 && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              style={{
                position: 'absolute',
                bottom: 6,
                right: 10,
                fontSize: 10,
                color: '#444444',
                fontFamily: 'JetBrains Mono, monospace',
                pointerEvents: 'none',
              }}
            >
              {charCount}
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      {/* Send button */}
      <motion.button
        whileHover={!disabled ? { scale: 1.05 } : {}}
        whileTap={!disabled ? { scale: 0.95 } : {}}
        onClick={handleSend}
        disabled={disabled || !text.trim()}
        style={{
          width: 42,
          height: 42,
          borderRadius: 8,
          border: 'none',
          background: text.trim() && !disabled ? '#e8742a' : '#2a2a2a',
          color: text.trim() && !disabled ? '#ffffff' : '#666666',
          cursor: text.trim() && !disabled ? 'pointer' : 'not-allowed',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          transition: 'background 0.15s ease, color 0.15s ease',
        }}
      >
        {disabled ? (
          <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx={12} cy={12} r={10} />
            <path d="M12 6v6l4 2" />
          </svg>
        ) : (
          <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
          </svg>
        )}
      </motion.button>
    </motion.div>
  )
}