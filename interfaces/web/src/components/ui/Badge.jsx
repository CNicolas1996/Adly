/**
 * Reusable colored badge pill.
 * variant: 'orange' | 'green' | 'red' | 'gray' | 'blue'
 */
export default function Badge({ children, variant = 'gray', className = '' }) {
  const styles = {
    orange: { background: 'rgba(232,116,42,0.15)', color: '#e8742a',  border: '1px solid rgba(232,116,42,0.3)' },
    green:  { background: 'rgba(74,222,128,0.12)', color: '#4ade80',  border: '1px solid rgba(74,222,128,0.25)' },
    red:    { background: 'rgba(248,113,113,0.12)', color: '#f87171', border: '1px solid rgba(248,113,113,0.25)' },
    gray:   { background: 'rgba(255,255,255,0.06)', color: '#999999', border: '1px solid #2a2a2a' },
    blue:   { background: 'rgba(96,165,250,0.12)', color: '#60a5fa',  border: '1px solid rgba(96,165,250,0.25)' },
  }

  return (
    <span
      style={{
        ...styles[variant],
        display:       'inline-flex',
        alignItems:    'center',
        gap:           4,
        padding:       '2px 8px',
        borderRadius:  100,
        fontSize:      11,
        fontWeight:    500,
        fontFamily:    'Inter, sans-serif',
        whiteSpace:    'nowrap',
        lineHeight:    1.6,
      }}
      className={className}
    >
      {children}
    </span>
  )
}
