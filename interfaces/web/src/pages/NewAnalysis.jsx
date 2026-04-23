import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { createAnalysis } from '@/api/client'
import Spinner from '@/components/ui/Spinner'

export default function NewAnalysis() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [sourceType, setSourceType] = useState('csv') // 'csv' or 'sheets'
  const [file, setFile] = useState(null)
  const [sheetId, setSheetId] = useState('')
  const [dateFrom, setDateFrom] = useState('2026-03-01')
  const [dateTo, setDateTo] = useState('2026-04-19')
  const [campaign, setCampaign] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)

  const handleCreate = async () => {
    if (!name.trim()) {
      setError('Ingresa un nombre para el análisis')
      return
    }

    if (sourceType === 'csv' && !file) {
      setError('Sube un archivo CSV')
      return
    }

    if (sourceType === 'sheets' && !sheetId.trim()) {
      setError('Ingresa el ID de Google Sheets')
      return
    }

    setCreating(true)
    setError(null)

    try {
      const newAnalysis = await createAnalysis({
        name,
        sourceType,
        file: sourceType === 'csv' ? file : null,
        sheetId: sourceType === 'sheets' ? sheetId.trim() : null,
        date_from: dateFrom,
        date_to: dateTo,
        campaign: campaign || null,
      })
      navigate(`/chat/${newAnalysis.id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setCreating(false)
    }
  }

  return (
    <motion.div
      style={{
        minHeight: '100vh',
        background: '#1a1a1a',
        padding: 24,
      }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <div style={{ maxWidth: 560, margin: '0 auto' }}>
        {/* Header */}
        <header style={{ marginBottom: 32 }}>
          <button
            onClick={() => navigate(-1)}
            style={{
              background: 'none',
              border: 'none',
              color: '#666666',
              cursor: 'pointer',
              padding: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 16,
            }}
          >
            <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            Volver
          </button>
          <h1 style={{
            fontSize: 24,
            fontWeight: 600,
            color: '#eeeeee',
            fontFamily: 'Inter, sans-serif',
            margin: 0,
          }}>
            Nuevo análisis
          </h1>
          <p style={{
            fontSize: 13,
            color: '#666666',
            fontFamily: 'Inter, sans-serif',
            marginTop: 4,
          }}>
            Configura los parámetros de tu análisis
          </p>
        </header>

        {/* Form */}
        <div style={{ display: 'grid', gap: 20 }}>
          {/* Name */}
          <div>
            <label style={{
              display: 'block',
              fontSize: 12,
              color: '#666666',
              fontFamily: 'JetBrains Mono, monospace',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: 8,
            }}>
              Nombre del análisis
            </label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Ej: Campaña Leads Abril"
              style={{
                width: '100%',
                padding: '12px 16px',
                background: '#151515',
                border: '1px solid #2a2a2a',
                borderRadius: 8,
                color: '#eeeeee',
                fontSize: 14,
                fontFamily: 'Inter, sans-serif',
                outline: 'none',
              }}
            />
          </div>

          {/* Dataset Source */}
          <div>
            <label style={{
              display: 'block',
              fontSize: 12,
              color: '#666666',
              fontFamily: 'JetBrains Mono, monospace',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: 8,
            }}>
              Fuente de datos
            </label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              <button
                onClick={() => setSourceType('csv')}
                style={{
                  flex: 1,
                  padding: '10px',
                  background: sourceType === 'csv' ? 'rgba(232,116,42,0.12)' : '#151515',
                  border: `1px solid ${sourceType === 'csv' ? '#e8742a' : '#2a2a2a'}`,
                  borderRadius: 8,
                  color: sourceType === 'csv' ? '#e8742a' : '#aaaaaa',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                Subir CSV
              </button>
              <button
                onClick={() => setSourceType('sheets')}
                style={{
                  flex: 1,
                  padding: '10px',
                  background: sourceType === 'sheets' ? 'rgba(232,116,42,0.12)' : '#151515',
                  border: `1px solid ${sourceType === 'sheets' ? '#e8742a' : '#2a2a2a'}`,
                  borderRadius: 8,
                  color: sourceType === 'sheets' ? '#e8742a' : '#aaaaaa',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                Google Sheets
              </button>
            </div>

            {sourceType === 'csv' ? (
              <div>
                <input
                  type="file"
                  accept=".csv"
                  onChange={e => setFile(e.target.files[0])}
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    background: '#151515',
                    border: '1px solid #2a2a2a',
                    borderRadius: 8,
                    color: '#eeeeee',
                    fontSize: 14,
                    fontFamily: 'Inter, sans-serif',
                    outline: 'none',
                  }}
                />
              </div>
            ) : (
              <div>
                <input
                  type="text"
                  value={sheetId}
                  onChange={e => setSheetId(e.target.value)}
                  placeholder="ID del Google Sheet"
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    background: '#151515',
                    border: '1px solid #2a2a2a',
                    borderRadius: 8,
                    color: '#eeeeee',
                    fontSize: 14,
                    fontFamily: 'Inter, sans-serif',
                    outline: 'none',
                  }}
                />
                <p style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                  Asegúrate de haber compartido el sheet con el correo de servicio.
                </p>
              </div>
            )}
          </div>

          {/* Date range */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{
                display: 'block',
                fontSize: 12,
                color: '#666666',
                fontFamily: 'JetBrains Mono, monospace',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: 8,
              }}>
                Desde
              </label>
              <input
                type="date"
                value={dateFrom}
                onChange={e => setDateFrom(e.target.value)}
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  background: '#151515',
                  border: '1px solid #2a2a2a',
                  borderRadius: 8,
                  color: '#eeeeee',
                  fontSize: 14,
                  fontFamily: 'Inter, sans-serif',
                  outline: 'none',
                }}
              />
            </div>
            <div>
              <label style={{
                display: 'block',
                fontSize: 12,
                color: '#666666',
                fontFamily: 'JetBrains Mono, monospace',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: 8,
              }}>
                Hasta
              </label>
              <input
                type="date"
                value={dateTo}
                onChange={e => setDateTo(e.target.value)}
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  background: '#151515',
                  border: '1px solid #2a2a2a',
                  borderRadius: 8,
                  color: '#eeeeee',
                  fontSize: 14,
                  fontFamily: 'Inter, sans-serif',
                  outline: 'none',
                }}
              />
            </div>
          </div>

          {/* Campaign (optional) */}
          <div>
            <label style={{
              display: 'block',
              fontSize: 12,
              color: '#666666',
              fontFamily: 'JetBrains Mono, monospace',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: 8,
            }}>
              Campaña (opcional)
            </label>
            <input
              type="text"
              value={campaign}
              onChange={e => setCampaign(e.target.value)}
              placeholder="Ej: Campaña_Leads_Abril"
              style={{
                width: '100%',
                padding: '12px 16px',
                background: '#151515',
                border: '1px solid #2a2a2a',
                borderRadius: 8,
                color: '#eeeeee',
                fontSize: 14,
                fontFamily: 'JetBrains Mono, monospace',
                outline: 'none',
              }}
            />
          </div>

          {/* Error */}
          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              style={{
                padding: '12px 16px',
                background: 'rgba(220, 53, 69, 0.15)',
                borderRadius: 8,
                border: '1px solid rgba(220, 53, 69, 0.3)',
                color: '#ff6b6b',
                fontSize: 13,
                fontFamily: 'Inter, sans-serif',
              }}
            >
              {error}
            </motion.div>
          )}

          {/* Create button */}
          <motion.button
            whileHover={{ scale: name.trim() ? 1.02 : 1 }}
            whileTap={{ scale: name.trim() ? 0.98 : 1 }}
            onClick={handleCreate}
            disabled={!name.trim() || creating}
            style={{
              padding: '14px 24px',
              background: name.trim() && !creating ? '#e8742a' : '#2a2a2a',
              border: 'none',
              borderRadius: 8,
              color: name.trim() && !creating ? '#ffffff' : '#444444',
              fontSize: 14,
              fontWeight: 500,
              fontFamily: 'Inter, sans-serif',
              cursor: name.trim() && !creating ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              marginTop: 8,
            }}
          >
            {creating ? (
              <>
                <Spinner size={16} color="#ffffff" />
                Creando...
              </>
            ) : (
              <>
                <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M12 5v14M5 12h14" />
                </svg>
                Crear análisis
              </>
            )}
          </motion.button>
        </div>
      </div>
    </motion.div>
  )
}