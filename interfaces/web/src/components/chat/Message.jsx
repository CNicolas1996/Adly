import { useState } from 'react'
import { motion } from 'framer-motion'
import DataTable from './DataTable'
import ConfidenceBar from './ConfidenceBar'

// ── Detectores de tipo de contenido ──────────────────────────────────────────

const isRichTable   = t => /[┌┐└┘│─┼╔╗╚╝║═]/.test(t)
const isMarkdown    = t => /^#{1,3} |^\- |\*\*|`[^`]|^\|.+\|/m.test(t)
const hasNewlines   = t => t.includes('\n')

// ── Tiempo ────────────────────────────────────────────────────────────────────

function formatTime(ts) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

// ── Renderer Rich ASCII (tablas de terminal) ──────────────────────────────────
// Renderiza el output de Rich como bloque monospace con scroll horizontal

function RichOutput({ text }) {
  return (
    <pre style={{
      fontFamily:  'JetBrains Mono, Fira Code, Consolas, monospace',
      fontSize:    12,
      lineHeight:  1.55,
      color:       '#d4d4d4',
      background:  '#0d0d0d',
      border:      '1px solid #1e1e1e',
      borderRadius: 6,
      padding:     '10px 14px',
      overflowX:   'auto',
      whiteSpace:  'pre',
      margin:      '4px 0 0',
      maxWidth:    '100%',
    }}>
      {text}
    </pre>
  )
}

// ── Renderer Markdown ─────────────────────────────────────────────────────────

function renderInline(text) {
  if (!text) return null
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**'))
      return <strong key={i} style={{ color: '#eeeeee', fontWeight: 600 }}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`') && part.endsWith('`'))
      return (
        <code key={i} style={{
          fontFamily:   'JetBrains Mono, monospace',
          fontSize:     11,
          background:   '#111',
          border:       '1px solid #2a2a2a',
          borderRadius: 3,
          padding:      '1px 5px',
          color:        '#e8742a',
        }}>{part.slice(1, -1)}</code>
      )
    return <span key={i}>{part}</span>
  })
}

function MarkdownTable({ rows }) {
  if (rows.length < 2) return null
  const headers = rows[0].split('|').map(h => h.trim()).filter(Boolean)
  const body    = rows.slice(2).map(r => r.split('|').map(c => c.trim()).filter(Boolean))

  return (
    <div style={{ overflowX: 'auto', marginTop: 8 }}>
      <table style={{
        width:          '100%',
        borderCollapse: 'collapse',
        fontSize:       12,
        fontFamily:     'JetBrains Mono, monospace',
      }}>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i} style={{
                padding:     '6px 10px',
                textAlign:   'left',
                color:       '#e8742a',
                borderBottom:'1px solid #2a2a2a',
                fontWeight:  600,
                whiteSpace:  'nowrap',
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr key={ri} style={{ borderBottom: '1px solid #1a1a1a' }}>
              {row.map((cell, ci) => (
                <td key={ci} style={{
                  padding:   '5px 10px',
                  color:     '#cccccc',
                  whiteSpace:'nowrap',
                }}>{renderInline(cell)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MarkdownRenderer({ text }) {
  const lines  = text.split('\n')
  const output = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Tabla markdown
    if (line.startsWith('|') && i + 1 < lines.length && lines[i + 1].includes('---')) {
      const tableRows = []
      while (i < lines.length && lines[i].startsWith('|')) {
        tableRows.push(lines[i])
        i++
      }
      output.push(<MarkdownTable key={`tbl-${i}`} rows={tableRows} />)
      continue
    }

    // Encabezado
    if (/^#{1,3} /.test(line)) {
      const level = line.match(/^#+/)[0].length
      const text  = line.replace(/^#+\s/, '')
      const sizes = { 1: 16, 2: 14, 3: 13 }
      output.push(
        <div key={i} style={{
          fontSize:     sizes[level] || 14,
          fontWeight:   600,
          color:        '#e8742a',
          marginTop:    level === 1 ? 0 : 10,
          marginBottom: 4,
          fontFamily:   'Inter, sans-serif',
          letterSpacing: '-0.01em',
        }}>
          {text}
        </div>
      )
      i++
      continue
    }

    // Lista con guión
    if (/^[-•] /.test(line)) {
      const items = []
      while (i < lines.length && /^[-•] /.test(lines[i])) {
        items.push(lines[i].replace(/^[-•] /, ''))
        i++
      }
      output.push(
        <ul key={`ul-${i}`} style={{
          margin:     '4px 0',
          paddingLeft: 16,
          listStyle:  'none',
        }}>
          {items.map((item, j) => (
            <li key={j} style={{
              display:     'flex',
              alignItems:  'flex-start',
              gap:         8,
              color:       '#cccccc',
              fontSize:    14,
              lineHeight:  1.6,
              marginBottom: 2,
            }}>
              <span style={{ color: '#e8742a', flexShrink: 0, marginTop: 1 }}>◆</span>
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ul>
      )
      continue
    }

    // Línea vacía
    if (!line.trim()) {
      output.push(<div key={i} style={{ height: 6 }} />)
      i++
      continue
    }

    // Texto normal
    output.push(
      <p key={i} style={{
        margin:     '2px 0',
        color:      '#cccccc',
        fontSize:   14,
        lineHeight: 1.65,
      }}>
        {renderInline(line)}
      </p>
    )
    i++
  }

  return <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>{output}</div>
}

// ── Renderer unificado ────────────────────────────────────────────────────────

function ContentRenderer({ text }) {
  if (!text) return null

  // Tablas ASCII de Rich — monospace con scroll
  if (isRichTable(text)) return <RichOutput text={text} />

  // Markdown — renderer estructurado
  if (isMarkdown(text) || hasNewlines(text)) return <MarkdownRenderer text={text} />

  // Texto plano con inline markdown
  return (
    <p style={{ margin: 0, color: '#cccccc', fontSize: 14, lineHeight: 1.65 }}>
      {renderInline(text)}
    </p>
  )
}

// ── Avatar ────────────────────────────────────────────────────────────────────

function CatPaw({ size = 18, color = '#e8742a' }) {
  return (
    <svg viewBox="0 0 274.2 244.33" width={size} height={size} style={{ display: 'block' }}>
      <g transform="translate(-198.45 -215.42)" fill={color}>
        <path d="m230.31 398.87c11.173-12.772 35.257-11.499 43.603-26.274 4.5828-8.1119-3.0615-19.151 0-27.951 1.8743-5.3872 5.5283-10.848 10.621-13.416 15.149-7.6391 31.161 0.75806 48.075-0.55902 12.167-0.94735 27.757-10.013 39.131-5.5902 9.3621 3.6405 17.244 13.147 19.566 22.92 2.1726 9.1459-5.0312 25.715-5.0312 27.951 0 2.2361 8.8885 17.525 19.566 23.479 6.3805 3.5577 19.401 0.86486 22.92 7.2672 5.4179 9.8594-3.1367 18-8.3852 27.951-2.6851 5.0907-9.959 14.729-15.093 17.33-11.897 6.0254-26.457-6.6822-39.69-5.0312-11.125 1.388-20.094 12.38-31.305 12.298-12.284-0.0898-21.821-14.335-34.1-13.975-10.33 0.30257-17.711 14.814-27.951 13.416-21.589-2.9467-44.406-21.788-49.193-43.044-1.3386-5.9436 3.2559-12.185 7.2672-16.77z"/>
        <path d="m249.32 323.68c3.3541 29.4-12.447 36.616-27.112 36.616s-23.758-13.364-23.758-36.057c0-22.692 14.124-41.647 28.789-41.647s22.081 18.396 22.081 41.088z"/>
        <path d="m402.77 255.2c2.2361 30.518-11.888 41.088-26.553 41.088s-29.907-13.364-26.553-41.088c2.7255-22.528 11.888-35.498 26.553-35.498s26.553 12.805 26.553 35.498z"/>
        <path d="m472.65 326.41c0 20.739-10.219 31.487-24.876 31.932-33.672 1.0218-23.758-24.476-23.758-45.215s7.9752-31.932 22.64-31.932 25.994 24.476 25.994 45.215z"/>
        <path d="m322.95 253.12c2.2361 32.07-11.888 43.177-26.553 43.177s-29.907-14.044-26.553-43.177c2.7255-23.673 10.77-33.778 26.553-37.302 14.345-3.2034 26.553 13.457 26.553 37.302z"/>
      </g>
    </svg>
  )
}

function BotAvatar() {
  const [imgError, setImgError] = useState(false)
  if (imgError) {
    return (
      <div style={{
        width: 32, height: 32, borderRadius: '50%',
        background: 'rgba(232,116,42,0.1)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <CatPaw size={18} color="#e8742a" />
      </div>
    )
  }
  return (
    <div style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <img src="/seals/idle.svg" width={26} height={26} alt="Adly"
        style={{ display: 'block' }} onError={() => setImgError(true)} />
    </div>
  )
}

// ── Message ───────────────────────────────────────────────────────────────────

export default function Message({ role, content, confidence, table, timestamp, confidence_note, data_freshness }) {
  const isBot = role === 'bot'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      style={{
        display:       'flex',
        flexDirection: isBot ? 'row' : 'row-reverse',
        alignItems:    'flex-start',
        gap:           10,
        maxWidth:      '100%',
        marginBottom:  2,
      }}
    >
      {/* Avatar */}
      {isBot && (
        <div style={{ flexShrink: 0, marginTop: 2 }}>
          <BotAvatar />
        </div>
      )}

      {/* Bubble */}
      <div style={{ maxWidth: isBot ? (table ? 'min(900px, 95%)' : 'min(680px, 90%)') : 'min(480px, 82%)', minWidth: 60 }}>
        <div style={{
          background:   isBot ? '#0f0f0f' : 'rgba(232,116,42,0.08)',
          border:       `1px solid ${isBot ? '#1e1e1e' : 'rgba(232,116,42,0.2)'}`,
          borderRadius: isBot ? '2px 10px 10px 10px' : '10px 2px 10px 10px',
          padding:      isBot ? '10px 14px' : '10px 14px',
        }}>
          {/* Contenido */}
          {isBot
            ? <ContentRenderer text={content} />
            : <p style={{ margin: 0, fontSize: 14, lineHeight: 1.65, color: '#dddddd', fontFamily: 'Inter, sans-serif' }}>
                {content}
              </p>
          }

          {/* Tabla estructurada (del backend via prop table) */}
          {isBot && table && <DataTable table={table} />}

          {/* Barra de confianza */}
          {isBot && confidence != null && confidence > 0 && (
            <ConfidenceBar confidence={confidence} note={confidence_note} />
          )}
        </div>

        {/* Meta row */}
        <div style={{
          display:        'flex',
          alignItems:     'center',
          gap:            8,
          marginTop:      4,
          paddingLeft:    isBot ? 2 : 0,
          paddingRight:   isBot ? 0 : 2,
          justifyContent: isBot ? 'flex-start' : 'flex-end',
        }}>
          <span style={{ fontSize: 10, color: '#444444', fontFamily: 'Inter, sans-serif' }}>
            {formatTime(timestamp)}
          </span>
          {isBot && data_freshness && (
            <span style={{ fontSize: 10, color: '#444444', fontFamily: 'JetBrains Mono, monospace' }}>
              · datos: {data_freshness}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  )
}
