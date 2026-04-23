/**
 * Adly API Client
 * All fetch calls go through here. Set VITE_MOCK=false to hit the real FastAPI.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const IS_MOCK  = (import.meta.env.VITE_MOCK ?? 'true') !== 'false'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function randomDelay(min = 600, max = 1200) {
  return delay(Math.floor(Math.random() * (max - min) + min))
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Error de servidor')
  }
  return res.json()
}

// ─── Mock data ────────────────────────────────────────────────────────────────

const MOCK_CONFIG = {
  model:       'groq',
  api_key:     '***hidden***',
  data_source: 'mock',
  sheet_id:    null,
  created_at:  '2026-04-01T10:00:00Z',
}

const MOCK_ANALYSES = [
  {
    id:            '1',
    name:          'Campaña Leads Abril',
    dataset:       'mock_ghl.csv',
    date_from:     '2026-03-01',
    date_to:       '2026-04-19',
    campaign:      'Campaña_Leads_Abril',
    created_at:    '2026-04-10T14:23:00Z',
    last_message:  '¿Cuál campaña tiene mejor CPL este mes?',
    confidence:    0.87,
  },
  {
    id:            '2',
    name:          'Análisis Retargeting Q1',
    dataset:       'mock_sheet.csv',
    date_from:     '2026-01-01',
    date_to:       '2026-03-31',
    campaign:      'Campaña_Retargeting',
    created_at:    '2026-04-05T09:15:00Z',
    last_message:  '/embudo Campaña_Retargeting',
    confidence:    0.71,
  },
  {
    id:            '3',
    name:          'Dataset dañado — diagnóstico',
    dataset:       'mock_danado.csv',
    date_from:     '2026-02-01',
    date_to:       '2026-04-01',
    campaign:      null,
    created_at:    '2026-04-18T18:44:00Z',
    last_message:  '/nulos',
    confidence:    0.34,
  },
]

const MOCK_MESSAGES = {
  '1': [
    {
      id: 'm1', role: 'bot', confidence: 0.87,
      content: '👋 Hola. Datos cargados: **500 leads**, 3 campañas activas. Integridad general: **87%**. ¿En qué te ayudo?',
      timestamp: '2026-04-10T14:24:00Z',
      data_freshness: '2h', confidence_note: 'Datos de las últimas 2 horas. Confianza alta.',
    },
    {
      id: 'm2', role: 'user',
      content: '¿Cuál campaña tiene mejor CPL este mes?',
      timestamp: '2026-04-10T14:25:00Z',
    },
    {
      id: 'm3', role: 'bot', confidence: 0.91,
      content: '**Campaña_Leads_Abril** tiene el mejor CPL con **$312k** promedio. Campaña_Retargeting tiene el peor con $587k (+88%). Te recomiendo reasignar presupuesto.',
      timestamp: '2026-04-10T14:25:08Z',
      data_freshness: '2h', confidence_note: 'Cálculo sobre 500 leads. Datos frescos.',
      table: [
        { Campaña: 'Leads_Abril', CPL: '$312k', Leads: 210, Conversión: '8.2%' },
        { Campaña: 'Branding_Q2', CPL: '$445k', Leads: 180, Conversión: '5.1%' },
        { Campaña: 'Retargeting', CPL: '$587k', Leads: 110, Conversión: '3.8%' },
      ],
    },
  ],
  '2': [
    {
      id: 'm4', role: 'bot', confidence: 0.71,
      content: 'Datos cargados con **advertencias**. Se detectaron 4 duplicados y 2 leads con estado desactualizado. Integridad: **71%**.',
      timestamp: '2026-04-05T09:16:00Z',
      data_freshness: '14h', confidence_note: 'Datos con 14h de antigüedad. 6 inconsistencias detectadas.',
    },
    {
      id: 'm5', role: 'user',
      content: '/embudo Campaña_Retargeting',
      timestamp: '2026-04-05T09:17:00Z',
    },
    {
      id: 'm6', role: 'bot', confidence: 0.68,
      content: 'Embudo Campaña_Retargeting: **cuello de botella en MQL→SQL** (32% conversión vs 51% promedio). 4 duplicados afectan el conteo de leads.',
      timestamp: '2026-04-05T09:17:12Z',
      data_freshness: '14h', confidence_note: 'Confianza reducida por duplicados detectados.',
      table: [
        { Etapa: 'Lead',  Cantidad: 110, Tasa: '100%' },
        { Etapa: 'MQL',   Cantidad: 72,  Tasa: '65%' },
        { Etapa: 'SQL',   Cantidad: 23,  Tasa: '32%' },
        { Etapa: 'Venta', Cantidad: 8,   Tasa: '35%' },
      ],
    },
  ],
  '3': [
    {
      id: 'm7', role: 'bot', confidence: 0.34,
      content: '⚠️ Dataset con integridad **baja (34%)**. Detecté: 206 leads, 38 nulos críticos, estados inválidos y duplicados. Recomiendo revisar antes de cualquier análisis.',
      timestamp: '2026-04-18T18:45:00Z',
      data_freshness: '1h', confidence_note: 'Confianza muy baja por integridad del dataset.',
    },
  ],
}

const MOCK_DATASET_INFO = {
  '1': { source: 'mock_ghl.csv', records: 500, nulls: 12, schema_status: 'ok', discrepancies: 2, integrity: 87 },
  '2': { source: 'mock_sheet.csv', records: 300, nulls: 28, schema_status: 'ok', discrepancies: 6, integrity: 71 },
  '3': { source: 'mock_danado.csv', records: 206, nulls: 38, schema_status: 'drift', discrepancies: 19, integrity: 34 },
}

const BOT_RESPONSES = [
  {
    content: 'Analizando los datos disponibles… **CPL promedio**: $389k. Campaña con mejor rendimiento: **Leads_Abril** con 8.2% de conversión lead→venta.',
    confidence: 0.88,
    data_freshness: '2h',
    confidence_note: 'Datos frescos. Alta confianza en métricas calculadas.',
    table: null,
  },
  {
    content: 'Detecté **3 outliers** en la columna `valor_venta`: registros con valores 4.2σ por encima del promedio. Podrían ser errores de carga o ventas reales excepcionales.',
    confidence: 0.79,
    data_freshness: '2h',
    confidence_note: 'Análisis estadístico IQR. Revisar manualmente los outliers señalados.',
    table: [
      { ID: 'lead_042', Valor: '$8.2M', Desviación: '+4.2σ', Estado: 'Revisar' },
      { ID: 'lead_187', Valor: '$7.9M', Desviación: '+3.9σ', Estado: 'Revisar' },
    ],
  },
  {
    content: 'El embudo muestra un **cuello de botella entre MQL y SQL** (38% conversión). El promedio del dataset es 51%. Posible causa: falta de seguimiento en esa etapa.',
    confidence: 0.82,
    data_freshness: '3h',
    confidence_note: 'Métricas calculadas sobre 500 leads. Datos con 3h de antigüedad.',
    table: null,
  },
]

// ─── Public API ───────────────────────────────────────────────────────────────

/** GET /api/config */
export async function getConfig() {
  if (IS_MOCK) {
    await delay(300)
    return MOCK_CONFIG
  }
  return apiFetch('/api/config')
}

/** POST /api/config */
export async function saveConfig(config) {
  if (IS_MOCK) {
    await delay(500)
    return { ok: true }
  }
  return apiFetch('/api/config', { method: 'POST', body: JSON.stringify(config) })
}

/** GET /api/analyses */
export async function getAnalyses() {
  if (IS_MOCK) {
    await randomDelay(400, 800)
    return [...MOCK_ANALYSES]
  }
  return apiFetch('/api/analyses')
}

/** POST /api/analyses */
export async function createAnalysis(data) {
  if (IS_MOCK) {
    await randomDelay(600, 1000)
    const newAnalysis = {
      id:         String(Date.now()),
      name:       data.name,
      dataset:    data.sourceType === 'csv' ? (data.file?.name ?? 'upload.csv') : (data.sheetId ?? 'mock'),
      date_from:  data.date_from,
      date_to:    data.date_to,
      campaign:   data.campaign ?? null,
      created_at: new Date().toISOString(),
      last_message: null,
      confidence: null,
    }
    MOCK_ANALYSES.unshift(newAnalysis)
    MOCK_MESSAGES[newAnalysis.id] = [
      {
        id:         `m_init_${newAnalysis.id}`,
        role:       'bot',
        confidence: 1.0,
        content:    `Análisis **${data.name}** creado. Dataset: \`${newAnalysis.dataset}\`. Rango: ${data.date_from} → ${data.date_to}. ¿Por dónde empezamos?`,
        timestamp:  new Date().toISOString(),
        data_freshness: 'ahora',
        confidence_note: 'Dataset recién cargado.',
      },
    ]
    MOCK_DATASET_INFO[newAnalysis.id] = {
      source: newAnalysis.dataset,
      records: 500, nulls: 12, schema_status: 'ok', discrepancies: 0, integrity: 92,
    }
    return newAnalysis
  }

  // Real backend implementation
  if (data.sourceType === 'csv') {
    const formData = new FormData()
    formData.append('name', data.name)
    formData.append('sourceType', data.sourceType)
    if (data.file) formData.append('file', data.file)
    formData.append('date_from', data.date_from)
    formData.append('date_to', data.date_to)
    if (data.campaign) formData.append('campaign', data.campaign)

    const res = await fetch(`${BASE_URL}/api/analyses`, {
      method: 'POST',
      body: formData, // fetch will automatically set Content-Type to multipart/form-data with boundary
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Error de servidor')
    }
    return res.json()
  } else {
    // sourceType === 'sheets'
    return apiFetch('/api/analyses', { method: 'POST', body: JSON.stringify({
      name: data.name,
      sourceType: data.sourceType,
      sheetId: data.sheetId,
      date_from: data.date_from,
      date_to: data.date_to,
      campaign: data.campaign
    }) })
  }
}

/** GET /api/analyses/:id/messages */
export async function getMessages(analysisId) {
  if (IS_MOCK) {
    await randomDelay(300, 600)
    return MOCK_MESSAGES[analysisId] ?? []
  }
  return apiFetch(`/api/analyses/${analysisId}/messages`)
}

/** GET /api/analyses/:id/dataset */
export async function getDatasetInfo(analysisId) {
  if (IS_MOCK) {
    await delay(200)
    return MOCK_DATASET_INFO[analysisId] ?? { source: 'unknown', records: 0, nulls: 0, schema_status: 'ok', discrepancies: 0, integrity: 0 }
  }
  return apiFetch(`/api/analyses/${analysisId}/dataset`)
}

/** POST /api/chat */
export async function sendMessage(analysisId, text) {
  if (IS_MOCK) {
    await randomDelay(1000, 2200)
    const response = BOT_RESPONSES[Math.floor(Math.random() * BOT_RESPONSES.length)]
    const msg = {
      id:        `m_${Date.now()}`,
      role:      'bot',
      ...response,
      timestamp: new Date().toISOString(),
    }
    if (!MOCK_MESSAGES[analysisId]) MOCK_MESSAGES[analysisId] = []
    MOCK_MESSAGES[analysisId].push(msg)
    // Update last_message on the analysis
    const analysis = MOCK_ANALYSES.find(a => a.id === analysisId)
    if (analysis) {
      analysis.last_message = text
      analysis.confidence   = response.confidence
    }
    return msg
  }
  return apiFetch('/api/chat', {
    method: 'POST',
    body:   JSON.stringify({ analysis_id: analysisId, message: text }),
  })
}

/** POST /api/config/test — connection test during onboarding */
export async function testConnection(config) {
  if (IS_MOCK) {
    await randomDelay(1200, 1800)
    if (config.model === 'mock') return { ok: true, model: 'mock', latency_ms: 0 }
    return { ok: true, model: config.model, latency_ms: Math.floor(Math.random() * 400 + 200) }
  }
  return apiFetch('/api/config/test', { method: 'POST', body: JSON.stringify(config) })
}
