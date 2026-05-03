# RapidFuzz Query Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded column/value mappings with rapidfuzz fuzzy matching, remove code duplication, ensure all tests pass.

**Architecture:**
- Use rapidfuzz.fuzz.ratio() for fuzzy matching against column names and values
- Dynamic column detection: match user input against actual df.columns
- Dynamic value detection: match user input against df[col].unique()
- Threshold: 75 for ambiguous (return CONFIRMAR), >85 for clear match

**Tech Stack:** Python 3.11, pandas, rapidfuzz

---

## Task 1: Add rapidfuzz to requirements.txt

**Files:**
- Modify: `Adly/requirements.txt`

- [ ] **Step 1: Add rapidfuzz to requirements.txt**

```bash
# Check current requirements.txt
cat Adly/requirements.txt | grep -i rapidfuzz
```

If not found, add it:
```bash
echo "rapidfuzz" >> Adly/requirements.txt
```

- [ ] **Step 2: Commit**

```bash
git add Adly/requirements.txt
git commit -m "feat: add rapidfuzz dependency"
```

---

## Task 2: Create test file for query_engine

**Files:**
- Create: `Adly/tests/test_query_engine.py`

- [ ] **Step 1: Write the test file**

```python
# tests/test_query_engine.py
import pandas as pd
from src.processing.query_engine import ejecutar_query_analitica

df = pd.read_csv("data/raw/mock_danado.csv")

casos = [
    # (pregunta, debe_retornar_None)
    ("cuántos leads hay por campaña", False),  # agrupacion
    ("agrupa por estado", False),  # agrupacion por estado
    ("cuántas vetnas tiene la campana leads", False),  # typos: vetnas→venta, campana→campana
    ("total de costo por campanas", False),  # suma con typo
    ("promedio de costo por adset", False),  # promedio
    ("cuántos hay en enero", False),  # temporal
    ("compara adset 18 vs adset 35", False),  # comparacion
    ("hola", True),  # debe retornar None
    ("qué es el marketing", True),  # debe retornar None
    ("ctr por campaña", True),  # columna que no existe → None
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

- [ ] **Step 2: Commit**

```bash
git add Adly/tests/test_query_engine.py
git commit -m "test: add query engine test cases"
```

---

## Task 3: Implement rapidfuzz fuzzy matching (replace hardcoded dicts)

**Files:**
- Modify: `Adly/src/processing/query_engine.py`

**Important:** Delete lines 590-851 (the duplicate code section), keeping only lines 1-589.

- [ ] **Step 1: Add rapidfuzz import at top**

Add after line 14:
```python
from rapidfuzz import fuzz
from rapidfuzz.fuzz import ratio as fuzzy_ratio
```

- [ ] **Step 2: Remove duplicate code section**

Delete lines 590-851 (everything after `return None` in first function)

- [ ] **Step 3: Replace _detectar_columna with fuzzy matching**

Replace the current `_detectar_columna` function (lines 122-127):

```python
def _detectar_columna(p: str, df: pd.DataFrame, threshold: int = 75) -> str | None:
    """
    Detecta la columna principal de agrupación en la pregunta usando fuzzy matching.
    """
    # Keywords that user might mention
    keywords = ["adset", "campaña", "campana", "ad", "estado", "campana",
                "costo", "gasto", "ingreso", "lead", "mql", "sql", "venta"]
    
    # Get actual columns from df
    columnas_df = {col.lower(): col for col in df.columns}
    
    best_match = None
    best_score = 0
    
    for kw in keywords:
        for col_lower, col_real in columnas_df.items():
            # Match keyword against column name
            score = fuzzy_ratio(kw, col_lower)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = col_real
    
    return best_match
```

- [ ] **Step 4: Replace _detectar_estado_filtro with dynamic matching**

Replace current function (lines 130-138):

```python
def _detectar_estado_filtro(p: str, df: pd.DataFrame, threshold: int = 75) -> str | None:
    """
    Detecta si la pregunta pide filtrar por un estado del embudo.
    Busca en los valores reales de df["estado"] si existe.
    """
    # Keywords user might use
    keywords = ["lead", "leads", "mql", "sql", "venta", "ventas", "perdido", "perdidos"]
    
    if "estado" not in df.columns:
        return None
    
    valores_estado = df["estado"].dropna().unique()
    valores_str = [str(v).lower() for v in valores_estado]
    
    best_match = None
    best_score = 0
    
    for kw in keywords:
        for val in valores_str:
            score = fuzzy_ratio(kw, val)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = val
    
    return best_match
```

- [ ] **Step 5: Replace _detectar_valor_en_columna with fuzzy matching**

Replace current function (lines 141-152):

```python
def _detectar_valor_en_columna(p: str, df: pd.DataFrame, col: str, threshold: int = 75) -> str | None:
    """
    Busca un valor específico de la columna mencionado en la pregunta.
    Usa fuzzy matching: 'adset 35' encuentra 'Adset_35-50'
    """
    valores_unicos = df[col].dropna().unique()
    
    # Get words from question (>3 chars)
    palabras = [w for w in p.split() if len(w) > 3]
    
    best_match = None
    best_score = 0
    
    for val in valores_unicos:
        val_str = str(val).lower()
        for palabra in palabras:
            # Match against the value
            score = fuzzy_ratio(palabra, val_str)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = val
    
    return best_match
```

- [ ] **Step 6: Add fuzzy column detection for numeric columns**

Add new function after `_detectar_columna_numerica`:

```python
def _detectar_columna_numerica(p: str, df: pd.DataFrame, threshold: int = 75) -> str | None:
    """
    Detecta si la pregunta menciona una métrica numérica específica.
    Busca fuzzy match en columnas numéricas del df.
    """
    # Keywords user might use
    keywords = ["gasto", "spend", "inversion", "inversión", "presupuesto",
                "ingreso", "revenue", "facturación", "facturacion",
                "cpl", "cpa", "roas", "ctr", "impresiones", "clicks", "costo"]
    
    # Get numeric columns from df
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    numeric_lower = {col.lower(): col for col in numeric_cols}
    
    best_match = None
    best_score = 0
    
    for kw in keywords:
        for col_lower, col_real in numeric_lower.items():
            score = fuzzy_ratio(kw, col_lower)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = col_real
    
    return best_match
```

- [ ] **Step 7: Remove hardcoded dictionaries**

Delete these lines from the file (approximately lines 18-72):
- COL_MAP (lines 23-29)
- ESTADOS_VALIDOS (line 32)
- ESTADO_MAP (lines 35-44)
- COLUMNAS_NUMERICAS_MAP (lines 47-56)
- MESES_MAP (lines 59-72) - keep but make it a local variable inside _detectar_filtro_temporal

- [ ] **Step 8: Update function calls in ejecutar_query_analitica**

The main function needs to pass `df` to the detection functions:

- Line 335: `col_detectada = _detectar_columna(p, df)`
- Line 336: `estado_filtro = _detectar_estado_filtro(p, df)`
- Line 338: `col_numerica = _detectar_columna_numerica(p, df)`
- Line 485: `valor_detectado = _detectar_valor_en_columna(p, df_filtrado, col_detectada) if col_detectada else None`

- [ ] **Step 9: Commit**

```bash
git add Adly/src/processing/query_engine.py
git commit -m "refactor: replace hardcoded dicts with rapidfuzz fuzzy matching"
```

---

## Task 4: Handle ambiguous matches with CONFIRMAR

**Files:**
- Modify: `Adly/src/processing/query_engine.py`

- [ ] **Step 1: Add CONFIRMAR logic for ambiguous column matches**

In `ejecutar_query_analitica`, after detecting column but before executing:

```python
# After col_detectada is set
if col_detectada:
    # Check if match was ambiguous (score 75-85)
    # If ambiguous, return confirmation string
    # This requires storing the score - modify _detectar_columna to return (col, score)
    pass
```

Actually, simpler approach: modify the threshold logic so that scores 75-85 trigger CONFIRMAR:

- [ ] **Step 2: Modify detection to return match info**

Change functions to return tuple (value, score) or add a check:

```python
def _detectar_columna(p: str, df: pd.DataFrame) -> tuple[str | None, int]:
    """
    Returns (column_name, confidence_score)
    """
    keywords = ["adset", "campaña", "campana", "ad", "estado", "costo", "gasto"]
    columnas_df = {col.lower(): col for col in df.columns}
    
    best_match = None
    best_score = 0
    
    for kw in keywords:
        for col_lower, col_real in columnas_df.items():
            score = fuzzy_ratio(kw, col_lower)
            if score > best_score:
                best_score = score
                best_match = col_real
    
    return best_match, best_score
```

- [ ] **Step 3: Add CONFIRMAR response in main function**

```python
# After detection
col_detectada, col_score = _detectar_columna(p, df)

if col_detectada and 75 <= col_score <= 85:
    return f"CONFIRMAR: ¿quisiste decir '{col_detectada}'?"
```

- [ ] **Step 4: Commit**

```bash
git add Adly/src/processing/query_engine.py
git commit -m "feat: add CONFIRMAR for ambiguous fuzzy matches"
```

---

## Task 5: Run tests and fix failures

**Files:**
- Test: `Adly/tests/test_query_engine.py`

- [ ] **Step 1: Run the tests**

```bash
cd Adly && python -m pytest tests/test_query_engine.py -v
```

- [ ] **Step 2: Fix any failures**

Iterate until all tests pass.

- [ ] **Step 3: Commit**

```bash
git add Adly/tests/test_query_engine.py
git commit -m "test: fix query engine tests"
```

---

## Task 6: Final verification

**Files:**
- Verify: `Adly/src/processing/query_engine.py`, `Adly/requirements.txt`

- [ ] **Step 1: Verify no hardcoded dictionaries**

```bash
grep -E "COL_MAP|ESTADO_MAP|COLUMNAS_NUMERICAS_MAP|ESTADOS_VALIDOS" Adly/src/processing/query_engine.py
```

Expected: no output

- [ ] **Step 2: Verify rapidfuzz is in requirements.txt**

```bash
grep rapidfuzz Adly/requirements.txt
```

Expected: `rapidfuzz`

- [ ] **Step 3: Verify no code duplication**

Count lines in query_engine.py - should be ~400 lines, not 850

```bash
wc -l Adly/src/processing/query_engine.py
```

Expected: < 600

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete rapidfuzz query engine implementation"
```

---

## Success Criteria

- [ ] All test cases pass ✅
- [ ] No code duplication in file
- [ ] No hardcoded column/value dictionaries
- [ ] rapidfuzz in requirements.txt
- [ ] Simple typos (1-2 chars) resolved automatically via fuzzy matching
- [ ] Major typos (>3 chars different) trigger "CONFIRMAR:"