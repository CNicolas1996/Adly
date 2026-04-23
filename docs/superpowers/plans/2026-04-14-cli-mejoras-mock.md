# CLI Mejoras + Mock Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mejorar el formato de respuestas del CLI con Rich, agregar comandos de exploración de datos (/head, /sample, /describe, /exportar), ampliar Mock A a 500+ leads con historia temporal, y crear Mock C con datos dañados para probar validación.

**Architecture:** Cuatro tareas independientes sobre dos archivos — `src/ingestion/mock_data.py` (Tasks 3 y 4) y `interfaces/cli/cli.py` + `src/ai/engine.py` (Tasks 1 y 2). No hay dependencias entre sí — se pueden trabajar en cualquier orden. El DataFrame activo (`df_ghl`) ya circula en `main()` pero está descartado con `_`; la Task 2 lo rescata.

**Tech Stack:** Python 3.11 · Rich · pandas · python-dotenv

---

## Task 1: Formato de respuestas — prohibir markdown + Rich panels

**Contexto:** El LLM a veces mete `**negritas**` o `##` dentro del campo `"respuesta"` del JSON. El CLI los imprime como texto crudo, lo que se ve feo. Hay que prohibirlo en el system prompt y mejorar `renderizar_respuesta()` para que use paneles Rich estructurados.

**Files:**
- Modify: `src/ai/engine.py:464-550` — SYSTEM_PROMPT, sección CÓMO HABLAS y RESTRICCIONES DURAS
- Modify: `interfaces/cli/cli.py:623-645` — función `renderizar_respuesta()`

---

- [ ] **Step 1: Agregar restricción anti-markdown en SYSTEM_PROMPT**

En `src/ai/engine.py`, al final de la sección `RESTRICCIONES DURAS` (línea ~546), agregar:

```python
# Reemplazar el cierre actual del SYSTEM_PROMPT:
# "- Devuelve SOLO el JSON. Sin texto antes, sin texto después, sin bloques markdown."
# por esto:

"""...
RESTRICCIONES DURAS:
- Nunca inventes métricas ni números que no están en los datos.
- Nunca pongas acción si no tienes claridad suficiente — mejor pregunta.
- Responde siempre en español.
- Devuelve SOLO el JSON. Sin texto antes, sin texto después, sin bloques markdown.
- PROHIBIDO en los valores del JSON: asteriscos (**texto**), almohadillas (## Título), guiones como viñetas (- item), backticks (`code`). El texto dentro de "respuesta" y "accion" debe ser prosa plana sin ningún símbolo de markdown.
- Usa punto y coma o coma para listas dentro de "respuesta". Ejemplo correcto: "CPL: $15k; ROAS: 1.2; Tasa MQL: 28%". Nunca: "**CPL**: $15k\\n- ROAS: 1.2"."""
```

- [ ] **Step 2: Verificar que el engine sigue respondiendo con JSON válido**

```bash
cd C:\Users\moonw\Proyectos\Adly
venv\Scripts\activate
python src/ai/engine.py
```

Esperado: conversación simulada completa sin errores de parsing. La salida debe mostrar respuestas sin `**` ni `##`.

- [ ] **Step 3: Mejorar renderizar_respuesta() en cli.py**

Reemplazar la función actual (líneas 623-645) por una versión que:
1. Muestra la severidad como badge coloreado
2. Imprime `respuesta.respuesta` dentro de un Panel Rich con borde de color según severidad
3. Si hay `accion`, la muestra en un sub-panel ámbar separado
4. La confianza va en el título del panel principal

```python
def renderizar_respuesta(respuesta) -> None:
    sev_map = {
        "info":     (C["primary"], "INFO"),
        "warning":  (C["warning"], "WARN"),
        "critical": (C["error"],   "CRIT"),
    }
    color, label = sev_map.get(respuesta.severidad, (C["primary"], "INFO"))
    cc = C["success"] if respuesta.confianza >= 0.8 else C["warning"] if respuesta.confianza >= 0.5 else C["error"]

    titulo = Text.assemble(
        (f" {label} ", f"bold reverse {color}"),
        ("  confianza: ", C["dim"]),
        (f"{respuesta.confianza:.0%}", f"bold {cc}"),
    )

    console.print(Panel(
        Text(f"  {respuesta.respuesta}", style=C["white"]),
        title=titulo,
        border_style=color,
        padding=(1, 2),
    ))

    if respuesta.accion:
        console.print(Panel(
            Text.assemble(
                ("  → ", f"bold {C['accent']}"),
                (respuesta.accion, C["white"]),
            ),
            border_style=C["accent"],
            padding=(0, 2),
        ))

    console.print()
```

- [ ] **Step 4: Probar visualmente**

```bash
python interfaces/cli/cli.py
```

Hacer una pregunta como `¿cuál campaña tiene mejor CPL?` y verificar:
- La respuesta aparece en un panel con borde azul (info) / ámbar (warning) / rojo (critical)
- No hay `**`, `##`, ni `-` como viñetas en el texto
- Si hay acción, aparece en panel ámbar separado

- [ ] **Step 5: Commit**

```bash
git add src/ai/engine.py interfaces/cli/cli.py
git commit -m "feat(cli): prohibir markdown en respuestas + Rich panels para renderizar_respuesta"
```

---

## Task 2: Comandos de exploración — /head, /sample, /describe, /exportar

**Contexto:** Actualmente `main()` descarta `df_ghl` con `_`. Hay que rescatarlo y exponer comandos pandas sobre él como comandos del chat, renderizados con Rich Tables.

**Files:**
- Modify: `interfaces/cli/cli.py:651-750` — `main()` para guardar `df_ghl`, agregar 4 funciones cmd_*, actualizarlas en el loop y en `cmd_ayuda()`

---

- [ ] **Step 1: Rescatar df_ghl en main()**

En `main()`, línea ~658, cambiar:

```python
# ANTES:
_, _, metricas, resumen_llm, resultado, manager = cargar_datos(...)

# DESPUÉS:
df_ghl, _, metricas, resumen_llm, resultado, manager = cargar_datos(...)
```

Y dentro del bloque `/refresh` (~línea 707), igual:

```python
# ANTES:
_, _, metricas, resumen_llm, resultado, manager = cargar_datos(...)

# DESPUÉS:
df_ghl, _, metricas, resumen_llm, resultado, manager = cargar_datos(...)
```

Inicializar `df_ghl = None` junto a las otras variables (línea ~656).

- [ ] **Step 2: Agregar las 4 funciones de comando**

Agregar después de `cmd_dashboard()` (línea ~618):

```python
def cmd_head(df, n: int = 5) -> None:
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos. Usa /refresh.[/{C['warning']}]\n")
        return
    sub = df.head(n)
    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['primary']}", padding=(0, 1))
    for col in sub.columns:
        t.add_column(str(col), style=C["muted"], no_wrap=True)
    for _, row in sub.iterrows():
        t.add_row(*[str(v) if v is not None else "—" for v in row])
    console.print(Panel(
        t,
        title=f"[{C['primary']}] HEAD — primeras {n} filas [/{C['primary']}]",
        border_style=C["primary"],
    ))
    console.print()


def cmd_sample(df, n: int = 5) -> None:
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos. Usa /refresh.[/{C['warning']}]\n")
        return
    sub = df.sample(min(n, len(df)), random_state=None)
    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['accent']}", padding=(0, 1))
    for col in sub.columns:
        t.add_column(str(col), style=C["muted"], no_wrap=True)
    for _, row in sub.iterrows():
        t.add_row(*[str(v) if v is not None else "—" for v in row])
    console.print(Panel(
        t,
        title=f"[{C['accent']}] SAMPLE — {n} filas aleatorias [/{C['accent']}]",
        border_style=C["accent"],
    ))
    console.print()


def cmd_describe(df) -> None:
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos. Usa /refresh.[/{C['warning']}]\n")
        return
    numericas = df.select_dtypes(include="number")
    if numericas.empty:
        console.print(f"  [{C['warning']}]No hay columnas numéricas en el dataset activo.[/{C['warning']}]\n")
        return
    desc = numericas.describe().round(2)
    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['primary']}", padding=(0, 1))
    t.add_column("STAT", style=f"bold {C['accent']}", width=8)
    for col in desc.columns:
        t.add_column(str(col), style=C["muted"], justify="right")
    for idx, row in desc.iterrows():
        t.add_row(str(idx), *[f"{v:,.2f}" for v in row])
    console.print(Panel(
        t,
        title=f"[{C['primary']}] DESCRIBE — estadísticas numéricas [/{C['primary']}]",
        border_style=C["primary"],
    ))
    console.print(f"  [{C['dim']}]{len(df)} filas · {len(df.columns)} columnas[/{C['dim']}]\n")


def cmd_exportar_df(df) -> None:
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos. Usa /refresh.[/{C['warning']}]\n")
        return
    fn = f"adly_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(fn, index=False)
    console.print(
        f"  [{C['success']}]✓  Exportado:[/{C['success']}] "
        f"[{C['primary']}]{fn}[/{C['primary']}] "
        f"[{C['dim']}]({len(df)} filas)[/{C['dim']}]\n"
    )
```

- [ ] **Step 3: Registrar los comandos en cmd_ayuda()**

En `cmd_ayuda()`, agregar las 4 entradas a la lista de comandos:

```python
("/head [N]",    "Muestra primeras N filas del dataset (default: 5)"),
("/sample [N]",  "Muestra N filas aleatorias (default: 5)"),
("/describe",    "Estadísticas numéricas del dataset activo"),
("/exportar",    "Guarda el dataset activo como CSV"),
```

- [ ] **Step 4: Agregar los elif en el loop de main()**

En el bloque `while True:`, después del `elif cmd == "/dashboard":`, agregar:

```python
elif cmd.startswith("/head"):
    partes = cmd.split()
    n = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else 5
    cmd_head(df_ghl, n)
elif cmd.startswith("/sample"):
    partes = cmd.split()
    n = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else 5
    cmd_sample(df_ghl, n)
elif cmd == "/describe":
    cmd_describe(df_ghl)
elif cmd == "/exportar":
    cmd_exportar_df(df_ghl)
```

- [ ] **Step 5: Probar los 4 comandos**

```bash
python interfaces/cli/cli.py
```

Probar:
- `/head` → tabla con 5 filas
- `/head 10` → tabla con 10 filas
- `/sample 3` → tabla con 3 filas aleatorias
- `/describe` → tabla de estadísticas (mean, std, min, max)
- `/exportar` → archivo CSV creado en directorio actual

- [ ] **Step 6: Commit**

```bash
git add interfaces/cli/cli.py
git commit -m "feat(cli): agregar comandos /head, /sample, /describe, /exportar con Rich Tables"
```

---

## Task 3: Mock A ampliado — 500+ leads con historia temporal

**Contexto:** `generar_datos_ghl()` genera 100 leads con fechas en un rango de 20 días. Necesitamos 500+ leads con historia realista de 2-4 meses por campaña para poder hacer análisis temporal en el CLI.

**Files:**
- Modify: `src/ingestion/mock_data.py:23-51` — función `generar_datos_ghl()`
- Modify: `src/ingestion/mock_data.py:102-124` — función `exportar_mock()` — actualizar n_leads a 500

---

- [ ] **Step 1: Reescribir generar_datos_ghl() con distribución temporal por campaña**

Reemplazar la función entera (líneas 23-51):

```python
# Rango de historia por campaña — cuántos días hacia atrás tiene datos
HISTORIA_CAMPANAS = {
    "Campaña_Retargeting":  120,  # 4 meses
    "Campaña_Branding":      60,  # 2 meses
    "Campaña_Leads_Marzo":   42,  # 6 semanas
}

def generar_datos_ghl(n_leads: int = 500) -> pd.DataFrame:
    """
    Simula los datos que viven en GoHighLevel CRM.
    Cada fila es un lead con su ID único y estado en el embudo.
    v2: 500+ leads · fecha_creacion con distribución realista por campaña · fecha_cierre para ventas.
    """
    random.seed(42)
    fecha_tope = datetime(2026, 4, 1)  # fecha más reciente del dataset

    registros = []
    for i in range(1, n_leads + 1):
        campana = random.choice(CAMPANAS)
        historia_dias = HISTORIA_CAMPANAS.get(campana, 60)
        dias_offset = random.randint(0, historia_dias)
        fecha_creacion = fecha_tope - timedelta(days=dias_offset)

        estado = random.choices(ESTADOS, weights=PESOS)[0]

        # fecha_cierre solo si el lead llegó a venta — entre 3 y 30 días después
        if estado == "venta":
            fecha_cierre = fecha_creacion + timedelta(days=random.randint(3, 30))
            fecha_cierre_str = fecha_cierre.strftime("%Y-%m-%d %H:%M:%S")
        else:
            fecha_cierre_str = ""

        registros.append({
            "ghl_id":          f"GHL-{i:04d}",
            "nombre":          f"Lead_{i:04d}",
            "email":           f"lead{i}@ejemplo.com",
            "telefono":        f"300{i:07d}",
            "campana":         campana,
            "adset":           random.choice(ADSETS),
            "ad":              random.choice(ADS),
            "estado":          estado,
            "costo_lead":      round(random.uniform(8000, 25000), 2),
            "valor_venta":     round(random.uniform(200000, 800000), 2) if estado == "venta" else 0,
            "fecha_creacion":  fecha_creacion.strftime("%Y-%m-%d %H:%M:%S"),
            "fecha_cierre":    fecha_cierre_str,
            "fecha_update":    (fecha_creacion + timedelta(hours=random.randint(1, 72))).strftime("%Y-%m-%d %H:%M:%S"),
        })

    return pd.DataFrame(registros)
```

- [ ] **Step 2: Actualizar exportar_mock() para usar n_leads=500**

En `exportar_mock()` (línea ~110), cambiar:

```python
# ANTES:
df_ghl = generar_datos_ghl(n_leads=100)

# DESPUÉS:
df_ghl = generar_datos_ghl(n_leads=500)
```

- [ ] **Step 3: Verificar que el CSV se genera correctamente**

```bash
cd C:\Users\moonw\Proyectos\Adly
venv\Scripts\activate
python src/ingestion/mock_data.py
```

Esperado:
- `[GHL] 500 registros → data/raw/mock_ghl.csv`
- CSV tiene columnas `fecha_creacion` y `fecha_cierre`
- Campaña_Retargeting tiene leads con `fecha_creacion` de hasta 120 días atrás

- [ ] **Step 4: Verificar que el CLI carga bien los 500 leads**

```bash
python interfaces/cli/cli.py
```

En pantalla de estado debe mostrar `Registros GHL: 500`. Probar `/describe` para ver distribución de `costo_lead`.

- [ ] **Step 5: Commit**

```bash
git add src/ingestion/mock_data.py data/raw/mock_ghl.csv data/raw/mock_sheet.csv
git commit -m "feat(mock): ampliar Mock A a 500 leads con fecha_creacion historica por campaña y fecha_cierre"
```

---

## Task 4: Mock C — datos dañados para probar validación

**Contexto:** Necesitamos un dataset con errores severos para verificar que `DataValidator` y `AlertManager` los detectan sin explotar. Este mock es independiente — no deriva del `df_ghl` estándar sino que se genera solo.

**Files:**
- Modify: `src/ingestion/mock_data.py` — agregar función `generar_datos_danados()` y `exportar_mock_danado()` al final del archivo, antes del bloque `if __name__ == "__main__":`

---

- [ ] **Step 1: Agregar generar_datos_danados() en mock_data.py**

Agregar antes del bloque `if __name__ == "__main__":` (línea ~212):

```python
# ─────────────────────────────────────────
# MOCK C — datos dañados para probar validación
# 15% nulos críticos · 10% estados inválidos · 5% costos negativos
# 3% fechas mal formateadas · duplicados por ID
# ─────────────────────────────────────────

def generar_datos_danados(n_leads: int = 200) -> pd.DataFrame:
    """
    Dataset con errores graves — para verificar que DataValidator y AlertManager
    los detectan sin explotar. Nunca usar en producción.

    Errores introducidos:
    - 15% de filas con nulos en campana, estado o costo_lead
    - 10% de filas con estados inválidos (typos, estados inventados)
    - 5% de filas con costo_lead negativo
    - 3% de filas con fecha_creacion en formato incorrecto (dd/mm/yy)
    - 3% de filas duplicadas por ghl_id
    """
    random.seed(55)
    fecha_base = datetime(2026, 1, 1)

    ESTADOS_INVALIDOS = ["LEAD", "MQL", "sold", "interesado", "pendiente", "", "n/a"]

    registros = []
    for i in range(1, n_leads + 1):
        dias = random.randint(0, 90)
        fecha = fecha_base + timedelta(days=dias)
        registros.append({
            "ghl_id":         f"GHL-{i:04d}",
            "nombre":         f"Lead_{i:04d}",
            "campana":        random.choice(CAMPANAS),
            "adset":          random.choice(ADSETS),
            "estado":         random.choices(ESTADOS, weights=PESOS)[0],
            "costo_lead":     round(random.uniform(8000, 25000), 2),
            "fecha_creacion": fecha.strftime("%Y-%m-%d %H:%M:%S"),
        })

    df = pd.DataFrame(registros)

    # ERROR 1 — 15% nulos en campos críticos
    for col in ["campana", "estado", "costo_lead"]:
        idx = random.sample(list(df.index), int(len(df) * 0.15))
        df.loc[idx, col] = None

    # ERROR 2 — 10% estados inválidos
    idx_est = random.sample(list(df.index), int(len(df) * 0.10))
    for i in idx_est:
        df.loc[i, "estado"] = random.choice(ESTADOS_INVALIDOS)

    # ERROR 3 — 5% costos negativos
    idx_neg = random.sample(list(df.index), int(len(df) * 0.05))
    df.loc[idx_neg, "costo_lead"] = df.loc[idx_neg, "costo_lead"] * -1

    # ERROR 4 — 3% fechas en formato incorrecto
    idx_fecha = random.sample(list(df.index), int(len(df) * 0.03))
    for i in idx_fecha:
        fecha_orig = pd.to_datetime(df.loc[i, "fecha_creacion"])
        df.loc[i, "fecha_creacion"] = fecha_orig.strftime("%d/%m/%y")  # formato incorrecto

    # ERROR 5 — 3% duplicados por ID
    idx_dup = random.sample(list(df.index), max(1, int(len(df) * 0.03)))
    duplicados = df.loc[idx_dup].copy()
    df = pd.concat([df, duplicados], ignore_index=True)

    return df


def exportar_mock_danado(output_dir: str = "data/raw") -> pd.DataFrame:
    """Genera y guarda el dataset dañado en data/raw/mock_danado.csv."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    df = generar_datos_danados(n_leads=200)
    path = f"{output_dir}/mock_danado.csv"
    df.to_csv(path, index=False)

    print(f"[Dañado] {len(df)} registros → {path}")
    print("\nErrores introducidos intencionalmente:")
    print(f"  Nulos en campos críticos : ~15% en campana, estado, costo_lead")
    print(f"  Estados inválidos        : ~10% con valores como 'LEAD', 'sold', 'n/a'")
    print(f"  Costos negativos         : ~5% de registros")
    print(f"  Fechas mal formateadas   : ~3% en formato dd/mm/yy")
    print(f"  Duplicados por ID        : ~{max(1, int(200*0.03))} filas duplicadas")

    return df
```

- [ ] **Step 2: Actualizar el bloque __main__ para soportar modo "danado"**

En el bloque `if __name__ == "__main__":` (línea ~212), agregar el nuevo modo:

```python
if __name__ == "__main__":
    import sys
    modo = sys.argv[1] if len(sys.argv) > 1 else "standard"

    if modo == "ambiguo":
        print(">> Generando mock ambiguo (para Sheets + ColumnMapper)...\n")
        exportar_mock_ambiguo()
    elif modo == "danado":
        print(">> Generando mock dañado (para probar validación)...\n")
        exportar_mock_danado()
    else:
        print(">> Generando datos de prueba...\n")
        df_ghl, df_sheet = exportar_mock()
        print("\n>> Muestra GHL (primeras 3 filas):")
        print(df_ghl.head(3).to_string())
        print("\n>> Muestra Sheet (primeras 3 filas):")
        print(df_sheet.head(3).to_string())
        print("\n>> Mock data listo.")
        print("\n>> Para generar mock ambiguo : python src/ingestion/mock_data.py ambiguo")
        print(">> Para generar mock dañado  : python src/ingestion/mock_data.py danado")
```

- [ ] **Step 3: Generar el CSV y verificar los errores**

```bash
python src/ingestion/mock_data.py danado
```

Esperado:
```
[Dañado] ~206 registros → data/raw/mock_danado.csv
Errores introducidos intencionalmente:
  Nulos en campos críticos : ~15% en campana, estado, costo_lead
  Estados inválidos        : ~10% con valores como 'LEAD', 'sold', 'n/a'
  Costos negativos         : ~5% de registros
  Fechas mal formateadas   : ~3% en formato dd/mm/yy
  Duplicados por ID        : ~6 filas duplicadas
```

- [ ] **Step 4: Probar mock_danado.csv en el CLI**

```bash
python interfaces/cli/cli.py
```

En onboarding, fuente → 1 (mock), CSV → `data/raw/mock_danado.csv`

Verificar que:
- La pantalla de estado muestra score de integridad bajo (rojo o ámbar)
- Se listan alertas críticas o advertencias
- El CLI no explota — llega al chat funcional
- `/alertas` muestra los problemas detectados

- [ ] **Step 5: Commit**

```bash
git add src/ingestion/mock_data.py data/raw/mock_danado.csv
git commit -m "feat(mock): agregar Mock C con datos danados — 15% nulos, estados invalidos, costos negativos, duplicados"
```

---

## Orden de ejecución sugerido

Las 4 tasks son independientes. Orden recomendado:

1. **Task 3** (Mock A) — base de datos más rica para probar todo lo demás
2. **Task 4** (Mock C) — mientras tenemos mock_data.py abierto
3. **Task 1** (Formato Rich) — mejora visual, fácil de verificar
4. **Task 2** (Comandos exploración) — rescata df_ghl y agrega los 4 comandos
