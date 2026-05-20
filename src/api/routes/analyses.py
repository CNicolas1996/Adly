import uuid
import re
from datetime import datetime
from fastapi import APIRouter, Form, UploadFile, File, HTTPException, Request
import pandas as pd
from typing import Optional

from src.api.state import state
from src.ai.engine import AdlyEngine, LLMFactory
from src.processing.metrics import MetricsCalculator
from src.ingestion.sheets import SheetsConnector
from src.ingestion.ingestion_normalizer import normalizar
from src.api.limiter import limiter
from src.processing.column_mapper import ColumnMapper
from src.processing.data_quality import DataQualityReport

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

MAX_CSV_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

@router.get("")
@limiter.limit("20/minute")
async def get_analyses(request: Request):
    sorted_analyses = sorted(state.analyses.values(), key=lambda x: x["created_at"], reverse=True)
    return sorted_analyses

@router.post("")
@limiter.limit("10/minute")
async def create_analysis(
    request: Request,
    name: str = Form(...),
    sourceType: str = Form(...),
    date_from: str = Form(...),
    date_to: str = Form(...),
    campaign: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    sheetId: Optional[str] = Form(None)
):
    analysis_id = str(uuid.uuid4())

    try:
        # 1. Load Data
        df = None
        dataset_name = "unknown"
        schema_cols = None
        norm_report = {}

        if sourceType == 'csv':
            if not file:
                raise HTTPException(status_code=400, detail="Se requiere un archivo CSV")

            if file.size and file.size > MAX_CSV_SIZE_BYTES:
                raise HTTPException(status_code=413, detail="El archivo es demasiado grande (Máximo 25MB).")

            raw_bytes = await file.read()
            if len(raw_bytes) > MAX_CSV_SIZE_BYTES:
                raise HTTPException(status_code=413, detail="El archivo excede el tamaño máximo permitido (25MB).")

            for enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
                try:
                    from io import BytesIO
                    df_raw = pd.read_csv(BytesIO(raw_bytes), encoding=enc)
                    break
                except (UnicodeDecodeError, Exception):
                    continue
            else:
                raise HTTPException(status_code=400, detail="No se pudo leer el archivo — prueba guardarlo como CSV UTF-8 desde Excel.")

            dataset_name = file.filename
            df_raw.columns = [c.strip() for c in df_raw.columns]  # PASO 0 — strip antes de todo

            # ── Pipeline semántico ───────────────────────────────────────────
            # Paso 1: SemanticInferencer infiere columnas y stages (embeddings locales)
            # Paso 2: normalizar() recibe el schema — usa columnas detectadas, no hardcodeo
            # Paso 3: MetricsCalculator recibe config desde el schema
            #
            # Si SemanticInferencer no está disponible (sentence-transformers no instalado),
            # cae al ColumnMapper LLM como antes — backward compatible.

            semantic_schema = None
            inferencer = state.semantic_inferencer

            if inferencer is not None:
                try:
                    df_inferido, semantic_schema = inferencer.analizar(df_raw, cache_key=dataset_name)
                    # df_inferido puede tener columnas nuevas (_adly_campana, etc.)
                    # lo usamos como base para el normalizer
                    df_raw = df_inferido
                    schema_cols = semantic_schema.as_config()
                except Exception as e:
                    print(f"[analyses] SemanticInferencer falló ({e}) — fallback a ColumnMapper")
                    semantic_schema = None

            # Normalización — pasa el schema si está disponible
            df, norm_report = normalizar(df_raw, schema=semantic_schema)

            # Fallback a ColumnMapper LLM si SemanticInferencer no corrió
            if schema_cols is None:
                mapper = ColumnMapper()
                schema_cols = mapper.mapear(df, cache_key=dataset_name)

        elif sourceType == 'sheets':
            if not sheetId:
                raise HTTPException(status_code=400, detail="Se requiere un ID de Google Sheets")

            if not re.match(r"^[a-zA-Z0-9-_]{30,60}$", sheetId):
                raise HTTPException(status_code=400, detail="El ID de Google Sheets proporcionado no tiene un formato válido.")

            connector = SheetsConnector(sheet_id=sheetId)
            df = connector.leer()  # normalizar() corre dentro de SheetsConnector.leer()
            if df.empty:
                raise HTTPException(status_code=400, detail="El Google Sheet está vacío o no se pudo leer")
            dataset_name = f"Sheet: {sheetId[:10]}..."
            schema_cols = connector.schema
            norm_report = getattr(connector, "reporte_normalización", {})
        else:
            raise HTTPException(status_code=400, detail="Tipo de fuente no válido")

        # 2. Calcular métricas y contexto
        calc = MetricsCalculator(config=schema_cols)
        try:
            metricas = calc.calcular(df, nivel="campana")
            resumen_llm = calc.resumen_para_llm(metricas, nivel="campana")
            schema_llm = calc.resumen_schema(df)
            dataset_status = "ok"
        except Exception as e:
            print(f"Error al calcular métricas para LLM: {e}")
            resumen_llm = "No se pudieron calcular las métricas estándar debido a columnas faltantes o datos atípicos."
            schema_llm = calc.resumen_schema(df)
            dataset_status = "error"

        # 3. Inicializar Engine
        try:
            llm_provider = state.config.get("model", "groq")
            engine = AdlyEngine(llm=LLMFactory.crear(llm_provider))
        except Exception as e:
            print(f"Error cargando LLM: {e}, usando default")
            engine = AdlyEngine()

        engine.set_contexto_completo(resumen_llm, schema_llm, fuente=sourceType)

        # 4. Guardar info
        created_at = datetime.utcnow().isoformat() + "Z"
        analysis_data = {
            "id": analysis_id,
            "name": name,
            "dataset": dataset_name,
            "date_from": date_from,
            "date_to": date_to,
            "campaign": campaign,
            "created_at": created_at,
            "last_message": None,
            "confidence": None,
        }

        first_msg = {
            "id": f"m_init_{analysis_id}",
            "role": "bot",
            "confidence": 1.0,
            "content": f"Análisis **{name}** inicializado. Se cargaron {len(df)} registros. Puedes preguntarme sobre tus métricas.",
            "timestamp": created_at,
            "data_freshness": "ahora",
            "confidence_note": "Dataset recién cargado."
        }

        dataset_info = {
            "source": dataset_name,
            "records": len(df),
            "nulls": int(df.isna().sum().sum()),
            "schema_status": dataset_status,
            "discrepancies": 0,
            "integrity": 100 if dataset_status == "ok" else 50
        }

        state.add_analysis(analysis_id, analysis_data, df, engine, dataset_info, first_msg, normalization_report=norm_report, semantic_schema=semantic_schema)

        try:
            quality_report = DataQualityReport.from_df(df)
            if not hasattr(state, "_quality_reports"):
                state._quality_reports = {}
            state._quality_reports[analysis_id] = quality_report
        except Exception as e:
            print(f"[analyses] DataQualityReport falló (no crítico): {e}")

        return analysis_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{analysis_id}/messages")
async def get_messages(analysis_id: str):
    if analysis_id not in state.messages:
        return []
    return state.messages[analysis_id]

@router.get("/{analysis_id}/dataset")
async def get_dataset(analysis_id: str):
    if analysis_id not in state.dataset_info:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")
    return state.dataset_info[analysis_id]
