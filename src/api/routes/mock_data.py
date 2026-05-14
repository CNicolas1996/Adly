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

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

MAX_CSV_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

@router.get("")
@limiter.limit("20/minute")
async def get_analyses(request: Request):
    # Return list of created analyses sorted by creation date
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
            
            # File size limit check
            if file.size and file.size > MAX_CSV_SIZE_BYTES:
                raise HTTPException(status_code=413, detail=f"El archivo es demasiado grande (Máximo 25MB).")
            
            # Additional check by reading chunks if file.size is not reliable
            content = await file.read(MAX_CSV_SIZE_BYTES + 1)
            if len(content) > MAX_CSV_SIZE_BYTES:
                raise HTTPException(status_code=413, detail="El archivo excede el tamaño máximo permitido (25MB).")
            await file.seek(0)
            
            df_raw = pd.read_csv(file.file)
            dataset_name = file.filename

            # Normalización defensiva — siempre antes de cualquier análisis
            df, norm_report = normalizar(df_raw)

            # Detección de schema con ColumnMapper
            mapper = ColumnMapper()
            schema_cols = mapper.mapear(df, cache_key=dataset_name)

        elif sourceType == 'sheets':
            if not sheetId:
                raise HTTPException(status_code=400, detail="Se requiere un ID de Google Sheets")
            
            # Validar formato del Sheet ID contra inyecciones
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
        
        # Generar primer mensaje
        first_msg = {
            "id": f"m_init_{analysis_id}",
            "role": "bot",
            "confidence": 1.0,
            "content": f"Análisis **{name}** inicializado. Se cargaron {len(df)} registros. Puedes preguntarme sobre tus métricas.",
            "timestamp": created_at,
            "data_freshness": "ahora",
            "confidence_note": "Dataset recién cargado."
        }
        
        # Info del dataset
        dataset_info = {
            "source": dataset_name,
            "records": len(df),
            "nulls": int(df.isna().sum().sum()),
            "schema_status": dataset_status,
            "discrepancies": 0,
            "integrity": 100 if dataset_status == "ok" else 50
        }
        
        # Use state's enforce limit save
        state.add_analysis(analysis_id, analysis_data, df, engine, dataset_info, first_msg, normalization_report=norm_report)
        
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
