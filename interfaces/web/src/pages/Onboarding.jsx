import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { testConnection, saveConfig } from '@/api/client'
import Spinner from '@/components/ui/Spinner'

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

const STEPS = [
  {
    title: 'Bienvenido a Adly',
    description: 'Tu analista de datos con IA. Conectemos tus fuentes de datos para comenzar.',
  },
  {
    title: 'Elige tu modelo',
    description: 'Selecciona el modelo de IA que quieres usar para analizar tus datos.',
  },
  {
    title: 'Configura el origen',
    description: '¿De dónde vienen tus datos? Google Sheets o un archivo CSV.',
  },
  {
    title: 'Listo para analizar',
    description: 'Todo configurado. Ahora puedes explorar tus datos con Adly.',
  },
]

const MODELS = [
  { id: 'groq', name: 'Groq (Mixtral)', description: 'Rápido y económico', latency: '~500ms' },
  { id: 'openai', name: 'OpenAI', description: 'Alta calidad', latency: '~2s' },
  { id: 'anthropic', name: 'Claude', description: 'El mejor reasoning', latency: '~1.5s' },
  { id: 'mock', name: 'Modo demo', description: 'Sin configurar', latency: '0ms' },
]

const SOURCES = [
  { id: 'google_sheet', name: 'Google Sheets', icon: 'sheet' },
  { id: 'csv', name: 'Archivo CSV', icon: 'csv' },
]

export default function Onboarding() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [selectedModel, setSelectedModel] = useState(null)
  const [selectedSource, setSelectedSource] = useState(null)
  const [sheetUrl, setSheetUrl] = useState('')
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState(null)

  const handleNext = () => {
    if (step < STEPS.length - 1) {
      setStep(s => s + 1)
      setError(null)
    }
  }

  const handleBack = () => {
    if (step > 0) {
      setStep(s => s - 1)
      setError(null)
    }
  }

  const handleTestConnection = async () => {
    setTesting(true)
    setError(null)

    try {
      const result = await testConnection({ model: selectedModel })

      if (result.ok) {
        await saveConfig({
          model: selectedModel,
          data_source: selectedSource,
          sheet_id: sheetUrl || null,
        })
        handleNext()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setTesting(false)
    }
  }

  const handleSkip = () => {
    // Use mock mode
    saveConfig({ model: 'mock', data_source: 'mock' })
    navigate('/home')
  }

  const canProceed = () => {
    switch (step) {
      case 0: return true
      case 1: return selectedModel != null
      case 2: return selectedSource != null
      case 3: return true
      default: return false
    }
  }

  return (
    <motion.div
      className="flex items-center justify-center min-h-screen"
      style={{ background: 'transparent', position: 'relative', overflow: 'hidden' }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <HaloBg />
      <div style={{ position: 'relative', zIndex: 2, width: '100%', maxWidth: 480, padding: 24 }}>
        {/* Progress dots */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginBottom: 32 }}>
          {STEPS.map((_, i) => (
            <div
              key={i}
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: i === step ? '#e8742a' : i < step ? 'rgba(232,116,42,0.6)' : 'rgba(255,255,255,0.1)',
                transition: 'background 0.3s ease',
              }}
            />
          ))}
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            {/* Step title */}
            <h1 style={{
              fontSize: 24,
              fontWeight: 600,
              color: '#eeeeee',
              fontFamily: 'Inter, sans-serif',
              marginBottom: 8,
              textAlign: 'center',
            }}>
              {STEPS[step].title}
            </h1>
            <p style={{
              fontSize: 14,
              color: '#666666',
              fontFamily: 'Inter, sans-serif',
              textAlign: 'center',
              marginBottom: 32,
            }}>
              {STEPS[step].description}
            </p>

            {/* Step content */}
            {step === 1 && (
              <div style={{ display: 'grid', gap: 12 }}>
                {MODELS.map(model => (
                  <motion.button
                    key={model.id}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    onClick={() => setSelectedModel(model.id)}
                    style={{
                      padding: '16px 20px',
                      background: selectedModel === model.id ? 'rgba(232,116,42,0.12)' : '#1a1a1a',
                      border: `1px solid ${selectedModel === model.id ? '#e8742a' : '#2a2a2a'}`,
                      borderRadius: 8,
                      cursor: 'pointer',
                      textAlign: 'left',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <div style={{
                        fontSize: 14,
                        fontWeight: 500,
                        color: '#eeeeee',
                        fontFamily: 'Inter, sans-serif',
                      }}>
                        {model.name}
                      </div>
                      <div style={{
                        fontSize: 12,
                        color: '#666666',
                        fontFamily: 'Inter, sans-serif',
                        marginTop: 2,
                      }}>
                        {model.description}
                      </div>
                    </div>
                    <div style={{
                      fontSize: 11,
                      color: selectedModel === model.id ? '#e8742a' : '#444444',
                      fontFamily: 'JetBrains Mono, monospace',
                    }}>
                      {model.latency}
                    </div>
                  </motion.button>
                ))}
              </div>
            )}

            {step === 2 && (
              <div style={{ display: 'grid', gap: 12 }}>
                {SOURCES.map(source => (
                  <motion.button
                    key={source.id}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    onClick={() => setSelectedSource(source.id)}
                    style={{
                      padding: '20px',
                      background: selectedSource === source.id ? 'rgba(232,116,42,0.12)' : '#1a1a1a',
                      border: `1px solid ${selectedSource === source.id ? '#e8742a' : '#2a2a2a'}`,
                      borderRadius: 8,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 16,
                    }}
                  >
                    <div style={{
                      width: 40,
                      height: 40,
                      background: '#2a2a2a',
                      borderRadius: 8,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="#e8742a" strokeWidth={2}>
                        {source.icon === 'sheet' ? (
                          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6M8 13h8M8 17h8" />
                        ) : (
                          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6" />
                        )}
                      </svg>
                    </div>
                    <div style={{ textAlign: 'left' }}>
                      <div style={{
                        fontSize: 14,
                        fontWeight: 500,
                        color: '#eeeeee',
                        fontFamily: 'Inter, sans-serif',
                      }}>
                        {source.name}
                      </div>
                      <div style={{
                        fontSize: 12,
                        color: '#666666',
                        fontFamily: 'Inter, sans-serif',
                        marginTop: 2,
                      }}>
                        {source.id === 'google_sheet' ? 'Conecta tu Google Sheet' : 'Sube un archivo CSV'}
                      </div>
                    </div>
                  </motion.button>
                ))}

                {/* Sheet URL input */}
                {selectedSource === 'google_sheet' && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    style={{ marginTop: 12 }}
                  >
                    <input
                      type="text"
                      value={sheetUrl}
                      onChange={e => setSheetUrl(e.target.value)}
                      placeholder="https://docs.google.com/spreadsheets/d/..."
                      style={{
                        width: '100%',
                        padding: '12px 16px',
                        background: '#1a1a1a',
                        border: '1px solid #2a2a2a',
                        borderRadius: 8,
                        color: '#eeeeee',
                        fontSize: 13,
                        fontFamily: 'JetBrains Mono, monospace',
                        outline: 'none',
                      }}
                    />
                  </motion.div>
                )}
              </div>
            )}

            {step === 3 && (
              <div style={{
                textAlign: 'center',
                padding: '32px 0',
              }}>
                <motion.div
                  animate={{ scale: [1, 1.1, 1] }}
                  transition={{ duration: 0.5 }}
                  style={{ background: 'transparent', border: '1px solid rgba(232,116,42,0.2)', borderRadius: 12, padding: 16, display: 'inline-block', marginBottom: 16 }}
                >
                  <img src="/seals/happy.svg" width="80" alt="Adly" style={{ mixBlendMode: 'multiply', background: 'transparent', display: 'block', margin: '0 auto' }} />
                </motion.div>
                <div style={{
                  fontSize: 16,
                  color: '#e8742a',
                  fontFamily: 'Inter, sans-serif',
                  fontWeight: 500,
                }}>
                  ¡Configuración completa!
                </div>
                <div style={{
                  fontSize: 13,
                  color: '#666666',
                  fontFamily: 'Inter, sans-serif',
                  marginTop: 8,
                }}>
                  Adly está listo para analizar tus datos
                </div>
              </div>
            )}

            {/* Error message */}
            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                style={{
                  marginTop: 16,
                  padding: '12px 16px',
                  background: 'rgba(220, 53, 69, 0.15)',
                  borderRadius: 8,
                  border: '1px solid rgba(220, 53, 69, 0.3)',
                  color: '#ff6b6b',
                  fontSize: 13,
                  fontFamily: 'Inter, sans-serif',
                  textAlign: 'center',
                }}
              >
                {error}
              </motion.div>
            )}
          </motion.div>
        </AnimatePresence>

        {/* Navigation buttons */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 32,
          gap: 12,
        }}>
          {step > 0 && step < 3 && (
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleBack}
              style={{
                padding: '12px 24px',
                background: 'transparent',
                border: '1px solid #2a2a2a',
                borderRadius: 8,
                color: '#666666',
                fontSize: 13,
                fontFamily: 'Inter, sans-serif',
                cursor: 'pointer',
              }}
            >
              Atrás
            </motion.button>
          )}

          {step === 0 && (
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleSkip}
              style={{
                padding: '12px 24px',
                background: 'transparent',
                border: '1px solid #2a2a2a',
                borderRadius: 8,
                color: '#666666',
                fontSize: 13,
                fontFamily: 'Inter, sans-serif',
                cursor: 'pointer',
                marginLeft: 'auto',
              }}
            >
              Usar modo demo
            </motion.button>
          )}

          {step < 2 && (
            <motion.button
              whileHover={{ scale: canProceed() ? 1.02 : 1 }}
              whileTap={{ scale: canProceed() ? 0.98 : 1 }}
              onClick={handleNext}
              disabled={!canProceed()}
              style={{
                padding: '12px 32px',
                background: canProceed() ? '#e8742a' : '#2a2a2a',
                border: 'none',
                borderRadius: 8,
                color: canProceed() ? '#ffffff' : '#444444',
                fontSize: 13,
                fontWeight: 500,
                fontFamily: 'Inter, sans-serif',
                cursor: canProceed() ? 'pointer' : 'not-allowed',
                marginLeft: 'auto',
              }}
            >
              Continuar
            </motion.button>
          )}

          {step === 2 && (
            <motion.button
              whileHover={{ scale: canProceed() ? 1.02 : 1 }}
              whileTap={{ scale: canProceed() ? 0.98 : 1 }}
              onClick={handleTestConnection}
              disabled={!canProceed() || testing}
              style={{
                padding: '12px 32px',
                background: canProceed() ? '#e8742a' : '#2a2a2a',
                border: 'none',
                borderRadius: 8,
                color: canProceed() ? '#ffffff' : '#444444',
                fontSize: 13,
                fontWeight: 500,
                fontFamily: 'Inter, sans-serif',
                cursor: canProceed() ? 'pointer' : 'not-allowed',
                marginLeft: 'auto',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              {testing ? (
                <>
                  <Spinner size={14} color="#ffffff" />
                  Probando...
                </>
              ) : (
                'Probar conexión'
              )}
            </motion.button>
          )}

          {step === 3 && (
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => navigate('/home')}
              style={{
                padding: '12px 32px',
                background: '#e8742a',
                border: 'none',
                borderRadius: 8,
                color: '#ffffff',
                fontSize: 13,
                fontWeight: 500,
                fontFamily: 'Inter, sans-serif',
                cursor: 'pointer',
                margin: '0 auto',
              }}
            >
              Ir al dashboard
            </motion.button>
          )}
        </div>
      </div>
    </motion.div>
  )
}