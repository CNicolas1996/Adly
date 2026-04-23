/**
 * Renders an array of objects as a styled dark table.
 * table: Array<Record<string, string|number>>
 */
export default function DataTable({ table }) {
  if (!table || table.length === 0) return null

  const headers = Object.keys(table[0])

  return (
    <div style={{
      marginTop:    10,
      borderRadius: 6,
      border:       '1px solid #2a2a2a',
      overflow:     'hidden',
      maxHeight:    280,
      overflowY:    'auto',
    }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: 'JetBrains Mono, monospace' }}>
        <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
          <tr>
            {headers.map(h => (
              <th key={h} style={{
                padding:         '7px 12px',
                textAlign:       'left',
                background:      '#161616',
                color:           '#e8742a',
                fontWeight:      500,
                fontSize:        10,
                textTransform:   'uppercase',
                letterSpacing:   '0.08em',
                borderBottom:    '1px solid #2a2a2a',
                whiteSpace:      'nowrap',
              }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.map((row, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? '#1a1a1a' : '#1c1c1c' }}>
              {headers.map(h => (
                <td key={h} style={{
                  padding:      '7px 12px',
                  color:        h === headers[0] ? '#eeeeee' : '#999999',
                  borderBottom: i < table.length - 1 ? '1px solid #222' : 'none',
                  whiteSpace:   'nowrap',
                }}>
                  {row[h] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
