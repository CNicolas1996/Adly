# INSTRUCCIONES PARA CLAUDE CODE
# Tarea: Reescribir query_engine.py con rapidfuzz
# Proyecto: Adly · Data-Buddy
# Archivo objetivo: src/processing/query_engine.py
# Tiempo estimado: 20-30 minutos

---

## CONTEXTO QUE DEBES LEER PRIMERO

Lee estos archivos antes de tocar cualquier cosa:
1. `src/processing/query_engine.py` — el archivo actual (tiene código duplicado al final, línea 637+)
2. `MAESTRO_ADLY.md` — arquitectura general de Adly

---

## PROBLEMA QUE RESUELVES

El query_engine actual usa diccionarios hardcodeados (COL_MAP, ESTADO_MAP) para detectar
columnas y valores. Esto falla cuando:
- El usuario escribe con typos: "campanas" en vez de "campana", "vetnas" en vez de "venta"
- El CSV tiene columnas que no están en el diccionario: "source", "pipeline", "etapa_crm"
- El usuario pregunta por valores que no están mapeados: "sold", "interesado", "hot lead"
- El engine se usa con un CSV completamente distinto al de Camí

La solución: reemplazar los diccionarios hardcodeados por fuzzy matching dinámico
con rapidfuzz — el engine lee el DataFrame real y matchea contra lo que realmente existe.

---

## DEPENDENCIA NUEVA

```bash
pip install rapidfuzz
```

Agrega también a requirements.txt:
```
rapidfuzz>=3.0.0
```

---

## ARQUITECTURA DEL NUEVO query_engine.py

El archivo nuevo tiene TRES capas bien separadas. No mezcles responsabilidades.

### CAPA 1 — Schema Reader (agnóstico, sin hardcodeo)
Lee el DataFrame y construye un mapa dinámico de:
- Columnas categóricas: nombre + valores únicos (máx 50)
- Columnas numéricas: nombre + rango
- Columna de fecha: detección automática

```python
def _leer_schema(df: pd.DataFrame) -> dict:
    """
    Retorna:
    {
      "categoricas": {"campana": ["Leads_Marzo", "Retargeting", ...], ...},
      "numericas":   ["costo_lead", "valor_venta", ...],
      "fecha":       "fecha_creacion"  # o None
    }
    """
```

### CAPA 2 — Fuzzy Matcher (rapidfuzz, <5ms)
Dos funciones principales:

```python
def _match_columna(palabra: str, df: pd.DataFrame, umbral: int = 75) -> tuple[str, int] | None:
    """
    Busca la columna más similar a 'palabra' usando rapidfuzz.
    Retorna (nombre_columna_real, score) o None si score < umbral.
    
    Ejemplo:
      _match_columna("campanas", df) → ("campana", 92)
      _match_columna("xyz123",   df) → None
    """

def _match_valor(palabra: str, col: str, df: pd.DataFrame, umbral: int = 75) -> tuple[str, int] | None:
    """
    Busca el valor más similar a 'palabra' dentro de df[col] usando rapidfuzz.
    Retorna (valor_real, score) o None si score < umbral.
    Normaliza antes de comparar: lowercase, sin acentos, sin guiones/guiones bajos.
    
    Ejemplo:
      _match_valor("vetnas",    "estado", df) → ("venta",  88)
      _match_valor("retargeti", "campana", df) → ("Campaña_Retargeting", 85)
    """
```

**Normalización obligatoria antes de comparar:**
```python
import unicodedata

def _normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")  # quita acentos
    texto = texto.replace("_", " ").replace("-", " ")
    return texto
```

### CAPA 3 — Intent Detector + Executor (lógica de negocio)

#### 3.1 — Detección de intent
```python
def _detectar_intent(p: str) -> str | None:
    """
    Detecta el tipo de operación que pide la pregunta.
    Retorna: "conteo" | "agrupacion" | "suma" | "promedio" | "ranking" | "comparacion" | None
    
    IMPORTANTE: el orden importa. Evalúa de más específico a más general.
    """
    PATRONES = {
        "suma":       ["cuánto gastamos", "cuanto gastamos", "total gasto", "suma de",
                       "cuánto se gastó", "cuanto se gasto", "gasto total", "total de"],
        "promedio":   ["promedio", "media", "average", "avg", "en promedio"],
        "ranking":    ["mejor", "peor", "top", "mayor", "menor", "más eficiente",
                       "mas eficiente", "más rentable", "mas rentable", "más convierte",
                       "mas convierte", "más vendedor", "mas vendedor"],
        "comparacion":["vs", "versus", "compara", "diferencia entre", "contra"],
        "agrupacion": ["agrupa", "agrupar", "desglose", "desglos", "por cada",
                       "resumen por", "total de cada", "cuántos hay", "cuantos hay",
                       "muéstrame", "muestrame", "conteo", "categorias", "categorías",
                       "distribución", "distribucion", "breakdown"],
        "conteo":     ["cuántos", "cuantos", "cuenta", "total", "número de", "numero de",
                       "cuántas", "cuantas"],
    }
    for intent, keywords in PATRONES.items():
        if any(k in p for k in keywords):
            return intent
    return None
```

#### 3.2 — Detección de filtro temporal
Mantener `_detectar_filtro_temporal()` y `_aplicar_filtro_temporal()` exactamente
como están en el archivo actual (líneas 201-299). No los toques — funcionan bien.

También mantener `_detectar_columna_fecha()` como está (líneas 180-198).

#### 3.3 — Engine principal
```python
def ejecutar_query_analitica(pregunta: str, df: pd.DataFrame) -> str | None:
    """
    FLUJO EXACTO (no cambiar el orden):

    1. Normalizar pregunta → lowercase, sin acentos
    2. Detectar intent → si None, retornar None inmediatamente
    3. Detectar filtro temporal → aplicar al df si existe
    4. Para cada palabra de la pregunta (>3 chars):
       a. Intentar match contra columnas del df (umbral 75)
       b. Si hay match de columna → intentar match de valor dentro de esa columna
    5. Si hay ambigüedad (score entre 75-85) → retornar string de confirmación
       Formato: "CONFIRMAR: ¿quisiste decir '[valor_real]' en '[columna_real]'?"
    6. Si hay match claro (score >85) → ejecutar pandas según intent
    7. Siempre incluir advertencias de calidad al final

    Retorna: string con resultado para inyectar al LLM, o None si no hay intent claro.
    """
```

---

## COMPORTAMIENTO DE AMBIGÜEDAD

Cuando el score está entre 75 y 85 (zona gris), el engine NO ejecuta — pregunta primero:

```python
# El engine retorna esto (no una respuesta de Adly, sino un string especial)
return "CONFIRMAR: ¿quisiste decir 'venta' en la columna 'estado'? (escribe sí para confirmar)"
```

El CLI detecta si la respuesta del query_engine empieza con "CONFIRMAR:" y la muestra
al usuario antes de llamar al LLM. Si el usuario confirma, re-ejecuta con el valor confirmado.

**IMPORTANTE:** Este comportamiento de confirmación en cli.py NO lo implementes ahora.
Solo deja el string "CONFIRMAR:..." retornado por el engine. El CLI lo tratará como
contexto adicional para el LLM por ahora. La integración completa va en Fase 2.

---

## AGRUPACIÓN DINÁMICA — caso especial importante

Cuando el usuario pregunta "agrupa por estado" o "conteo de categorías en estado",
la columna de agrupación ES la columna de estado — no un filtro sobre ella.

El engine debe distinguir:
- "cuántos leads hay" → estado es FILTRO (filtra estado="lead", agrupa por otra col)
- "agrupa por estado" → estado es COLUMNA DE AGRUPACIÓN (groupby("estado"))
- "cuántos hay por estado" → estado es COLUMNA DE AGRUPACIÓN

Heurística: si la columna detectada aparece después de "por" o "según" en la pregunta,
es columna de agrupación. Si aparece como sustantivo solo, es filtro.

---

## COLUMNAS NUMÉRICAS — detección dinámica

NO uses COLUMNAS_NUMERICAS_MAP hardcodeado. En cambio:

```python
def _detectar_columna_numerica(p: str, df: pd.DataFrame) -> str | None:
    """
    1. Obtener todas las columnas numéricas del df: df.select_dtypes(include='number').columns
    2. Para cada palabra de la pregunta (>2 chars):
       a. Fuzzy match contra nombres de columnas numéricas (umbral 70 — más permisivo)
    3. Retornar la columna con mayor score, o None
    """
```

Esto funciona con cualquier CSV sin importar los nombres de columnas.

---

## ADVERTENCIAS DE CALIDAD — mantener y mejorar

Mantener `_advertencias_calidad()` pero agregar:
- Si se usó fuzzy match: indicar qué se interpretó
  `"INTERPRETACIÓN: 'campanas' interpretado como columna 'campana' (score 92%)"`
- Si hay valores negativos en columna numérica:
  `"CALIDAD: 'costo_lead' tiene valores negativos (mín: -20,520) — pueden distorsionar sumas/promedios"`

---

## LO QUE NO DEBES CAMBIAR

1. La firma de `ejecutar_query_analitica(pregunta, df)` — el CLI la llama así
2. El formato de retorno — siempre string o None
3. Los imports de `re` y `pandas` — solo agregar `rapidfuzz`
4. `_detectar_filtro_temporal()` y `_aplicar_filtro_temporal()` — no tocar
5. `_detectar_columna_fecha()` — no tocar

---

## LO QUE SÍ ELIMINAS

1. `COL_MAP` — reemplazado por fuzzy matching dinámico
2. `ESTADO_MAP` — reemplazado por fuzzy matching contra df[col].unique()
3. `COLUMNAS_NUMERICAS_MAP` — reemplazado por `df.select_dtypes(include='number')`
4. `ESTADOS_VALIDOS` — ya no se necesita
5. El código duplicado al final del archivo (líneas 637-851 en el archivo actual)
   — son copias exactas de funciones que ya existen arriba

---

## TESTS MÍNIMOS AL TERMINAR

Corre esto para verificar que funciona antes de entregar:

```python
# test_query_engine.py — corre desde la raíz del proyecto
import pandas as pd
from src.processing.query_engine import ejecutar_query_analitica

df = pd.read_csv("data/raw/mock_danado.csv")

casos = [
    # (pregunta, debe_retornar_None)
    ("cuántos leads hay por campaña",          False),  # agrupacion
    ("agrupa por estado",                      False),  # agrupacion por estado
    ("cuántas vetnas tiene la campana leads",  False),  # typos: vetnas→venta, campana→campana
    ("total de costo por campanas",            False),  # suma con typo
    ("promedio de costo por adset",            False),  # promedio
    ("cuántos hay en enero",                   False),  # temporal
    ("compara adset 18 vs adset 35",           False),  # comparacion
    ("hola",                                   True),   # debe retornar None
    ("qué es el marketing",                    True),   # debe retornar None
    ("ctr por campaña",                        True),   # columna que no existe → None
]

print("=" * 60)
for pregunta, espera_none in casos:
    resultado = ejecutar_query_analitica(pregunta, df)
    ok = (resultado is None) == espera_none
    estado = "✅" if ok else "❌"
    print(f"{estado} '{pregunta}'")
    if not ok:
        print(f"   Esperaba None={espera_none}, obtuvo: {resultado[:80] if resultado else None}")
print("=" * 60)
```

---

## CRITERIO DE ÉXITO

- Todos los casos de test pasan ✅
- El archivo no tiene código duplicado
- No hay ningún diccionario hardcodeado de columnas o valores
- `rapidfuzz` está en requirements.txt
- Typos simples (1-2 caracteres) son resueltos automáticamente
- Typos graves (>3 caracteres diferentes) disparan "CONFIRMAR:"
