# commands.py — Adly · Data-Buddy
# Handlers de comandos del CLI v3
# Nuevos: /columnas /nulos /outliers /correlacion /unicos /rango /top
# Fix: /eliminar_por con isnull/notnull
# /ayuda con flags --[cmd] para detalle

import csv
import math
import webbrowser
from datetime import datetime
from pathlib import Path

from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.columns import Columns
from rich import box

from interfaces.cli.theme import console, C, ICON, VERSION


# ─────────────────────────────────────────
# /ayuda  y  /ayuda --[cmd]
# ─────────────────────────────────────────

# Mapa de comandos: nombre → (sintaxis, descripción corta, detalle, ejemplos)
AYUDA_CMDS = {
    "alertas":          ("/alertas",                        "Integridad de datos",
        "Muestra alertas críticas y advertencias sobre la calidad del dataset.",
        []),
    "metricas":         ("/metricas",                       "Métricas por campaña",
        "Tabla con Leads, MQL, CPL, CPMQL, ROAS e ICL por campaña.",
        []),
    "columnas":         ("/columnas",                       "Schema con tipos semánticos",
        "Lista todas las columnas con tipo pandas, tipo semántico inferido, nulos y % completitud.",
        ["/columnas"]),
    "nulos":            ("/nulos",                          "Reporte de nulos por columna",
        "Ranking de columnas con más valores nulos. Muestra conteo, porcentaje e impacto.",
        ["/nulos"]),
    "outliers":         ("/outliers [col]",                 "Detección de valores extremos",
        "Detecta outliers en una columna numérica usando IQR (rango intercuartílico).\n"
        "  Marca como outlier todo valor fuera de [Q1 - 1.5·IQR, Q3 + 1.5·IQR].\n"
        "  Sin columna: corre en todas las numéricas.",
        ["/outliers costo_lead", "/outliers valor_venta", "/outliers"]),
    "correlacion":      ("/correlacion",                    "Matriz de correlación",
        "Correlación de Pearson entre todas las columnas numéricas.\n"
        "  Valores cercanos a 1 o -1 indican relación fuerte.\n"
        "  Útil para detectar redundancia entre variables.",
        ["/correlacion"]),
    "unicos":           ("/unicos [col]",                   "Valores únicos de una columna",
        "Muestra los valores únicos de una columna categórica con su frecuencia.\n"
        "  Útil para explorar estados, campañas, fuentes, etc.",
        ["/unicos estado", "/unicos campana", "/unicos adset"]),
    "rango":            ("/rango [col]",                    "Estadísticas de una columna numérica",
        "Min, max, media, mediana, std, Q1, Q3 e IQR de una columna.\n"
        "  Más preciso que /describe para una sola variable.",
        ["/rango costo_lead", "/rango valor_venta"]),
    "cohorts":          ("/cohorts",                        "Análisis de cohortes por mes",
        "Agrupa leads por mes de entrada y calcula tasa de conversión, CPL y valor por cohorte.\n"
        "Detecta si las campañas recientes convierten mejor o peor que las anteriores.\n"
        "Funciona con cualquier columna de fecha de entrada y estado detectados automáticamente.",
        ["/cohorts"]),
    "rentabilidad":     ("/rentabilidad",                    "CAC / LTV por campaña",
        "CAC  = costo total invertido / número de ventas\n"
        "LTV  = valor promedio por venta cerrada\n"
        "ROI  = (LTV - CAC) / CAC × 100\n"
        "Clasifica cada campaña como rentable, ajustada o en pérdida.",
        ["/rentabilidad"]),
    "rfm":              ("/rfm",                             "Segmentación RFM de leads",
        "Segmenta leads en 4 grupos según Recency y Monetary:\n"
        "  Campeón   — reciente + alto valor → escalar\n"
        "  Potencial — reciente + no cerró  → seguimiento\n"
        "  En riesgo — antiguo + no cerró   → reactivar\n"
        "  Frío      — antiguo + bajo valor → excluir\n"
        "Vista global y por campaña.",
        ["/rfm"]),
    "embudo":           ("/embudo [campaña]",                "Cuello de botella del funnel",
        "Detecta etapas del embudo desde col_estado y calcula:\n"
        "  conversión entre etapas y pérdida en leads y pesos.\n"
        "Sin campaña: vista global. Con campaña: drill-down específico.",
        ["/embudo", "/embudo Leads_Marzo", "/embudo Retargeting"]),
    "velocidad":        ("/velocidad",                       "Tiempo lead → venta por campaña",
        "Calcula días promedio y mediana entre entrada del lead y cierre de venta.\n"
        "Compara cada campaña contra el promedio global.\n"
        "Requiere fecha_creacion y fecha_cierre con ventas registradas.",
        ["/velocidad"]),
    "top":              ("/top [col] [N]",                  "Top N valores más frecuentes",
        "Los N valores más frecuentes de cualquier columna.\n"
        "  Default: N=10. Funciona con texto y números.",
        ["/top campana", "/top estado 5", "/top adset 3"]),
    "describe":         ("/describe",                       "Estadísticas numéricas",
        "count, mean, std, min, Q1, mediana, Q3, max — solo columnas numéricas.\n"
        "  Excluye automáticamente columnas de tipo ID/teléfono.",
        ["/describe"]),
    "head":             ("/head [N]",                       "Primeras N filas",
        "Muestra las primeras N filas del dataset activo. Default: 5.",
        ["/head", "/head 10"]),
    "sample":           ("/sample [N]",                     "N filas aleatorias",
        "Muestra N filas aleatorias del dataset activo. Default: 5.",
        ["/sample", "/sample 20"]),
    "exportar":         ("/exportar",                       "Exportar dataset a CSV",
        "Guarda el dataset activo (con todas las modificaciones) en un archivo CSV.",
        []),
    "limpiar_duplicados": ("/limpiar_duplicados",           "Eliminar filas duplicadas",
        "Detecta y elimina filas exactamente duplicadas. Actualiza el contexto del engine.",
        []),
    "rellenar":         ("/rellenar [columna] [estrategia]", "Rellenar nulos",
        "Estrategias disponibles:\n"
        "  media    → promedio de la columna\n"
        "  mediana  → valor central (robusto a outliers)\n"
        "  moda     → valor más frecuente\n"
        "  valor    → un valor literal que tú defines",
        ["/rellenar costo_lead media",
         "/rellenar estado moda",
         "/rellenar valor_venta valor 0"]),
    "eliminar_por":     ("/eliminar_por [col] [op] [valor]", "Filtrar y eliminar filas",
        "Operadores disponibles:\n"
        "  ==  !=  >  <  >=  <=  →  comparación con un valor\n"
        "  isnull                →  elimina filas donde col está vacía\n"
        "  notnull               →  elimina filas donde col tiene valor",
        ["/eliminar_por campana isnull",
         "/eliminar_por costo_lead < 0",
         "/eliminar_por estado == venta"]),
    "refresh":          ("/refresh",                        "Recargar datos",
        "Recarga el dataset desde la fuente configurada y actualiza el engine.",
        []),
    "limpiar":          ("/limpiar",                        "Nueva conversación",
        "Reinicia el historial de chat sin recargar datos.",
        []),
    "estado":           ("/estado",                         "Estado del sistema",
        "Muestra usuario, LLM activo, modelo, fuente de datos y mensajes en memoria.",
        []),
    "guardar":          ("/guardar",                        "Exportar conversación",
        "Guarda el historial de la sesión actual en un archivo CSV.",
        []),
    "dashboard":        ("/dashboard",                      "Dashboard HTML",
        "Genera un dashboard HTML con métricas de campañas y lo abre en el navegador.",
        []),
}

GRUPOS = {
    "Exploración":  ["columnas", "nulos", "describe", "head", "sample", "unicos", "rango", "top"],
    "Estadística":  ["outliers", "correlacion"],
    "Limpieza":     ["limpiar_duplicados", "rellenar", "eliminar_por"],
    "Campañas":     ["alertas", "metricas", "dashboard"],
    "Modelos":      ["cohorts", "rentabilidad", "rfm", "embudo", "velocidad"],
    "Sistema":      ["refresh", "limpiar", "estado", "guardar", "exportar"],
}


def cmd_ayuda(flag: str = "") -> None:
    """
    /ayuda           → vista general por grupos
    /ayuda --[cmd]   → detalle de un comando específico
    """
    # Detalle de comando específico
    if flag.startswith("--"):
        nombre = flag[2:].lower()
        if nombre not in AYUDA_CMDS:
            console.print(f"  [{C['warning']}]Comando '{nombre}' no encontrado.[/{C['warning']}]\n")
            return
        sintaxis, desc_corta, detalle, ejemplos = AYUDA_CMDS[nombre]
        contenido = Text()
        contenido.append(f"\n  {sintaxis}\n", style=f"bold {C['accent']}")
        contenido.append(f"\n  {detalle}\n", style=C["white"])
        if ejemplos:
            contenido.append("\n  Ejemplos:\n", style=f"bold {C['dim']}")
            for ej in ejemplos:
                contenido.append(f"    {ej}\n", style=C["primary"])
        console.print(Panel(
            contenido,
            title=Text.assemble((f" {ICON['info']} AYUDA: {nombre.upper()} ", f"bold {C['accent']}")),
            border_style=C["accent"],
            padding=(0, 2),
        ))
        console.print()
        return

    # Vista general por grupos
    for grupo, cmds in GRUPOS.items():
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        t.add_column(style=f"bold {C['accent']}", width=36)
        t.add_column(style=C["muted"])
        t.add_column(style=C["dim"], width=28)
        for nombre in cmds:
            if nombre not in AYUDA_CMDS:
                continue
            sintaxis, desc_corta, _, _ = AYUDA_CMDS[nombre]
            t.add_row(sintaxis, desc_corta, f"/ayuda --{nombre}")
        console.print(Panel(
            t,
            title=Text.assemble((f" {ICON['bullet']} {grupo.upper()} ", f"bold {C['primary']}")),
            border_style=C["dim"],
        ))

    console.print(
        f"  [{C['dim']}]Detalle de cualquier comando: [/{C['dim']}]"
        f"[{C['accent']}]/ayuda --[comando][/{C['accent']}]"
        f"[{C['dim']}]  ej: /ayuda --eliminar_por[/{C['dim']}]\n"
    )


# ─────────────────────────────────────────
# /alertas
# ─────────────────────────────────────────

def cmd_alertas(manager) -> None:
    if not manager.alertas:
        console.print(f"  [{C['success']}]{ICON['ok']}  Datos en buen estado.[/{C['success']}]\n")
        return
    for a in manager.alertas:
        if a.nivel.value == "critica":
            color, icono = C["error"], ICON["crit"]
        elif a.nivel.value == "advertencia":
            color, icono = C["warning"], ICON["warn"]
        else:
            color, icono = C["success"], ICON["ok"]
        console.print(Text.assemble(
            (f"  {icono}  ", f"bold {color}"),
            (a.nivel.value.upper(), f"bold {color}"),
            ("  ", ""),
            (a.mensaje, C["white"]),
        ))
        console.print(f"  [{C['dim']}]  {ICON['arrow']} {a.recomendacion}[/{C['dim']}]")
        if a.ids_afectados:
            m = a.ids_afectados[:3]
            e = len(a.ids_afectados) - 3
            console.print(f"  [{C['dim']}]  IDs: {m}{' y ' + str(e) + ' más' if e > 0 else ''}[/{C['dim']}]")
        console.print()


# ─────────────────────────────────────────
# /metricas
# ─────────────────────────────────────────

def cmd_metricas(metricas, col: str = "campana", excluidos: int = 0) -> None:
    if metricas is None or metricas.empty:
        console.print(f"  [{C['warning']}]Sin métricas. Usa /refresh.[/{C['warning']}]\n")
        return
    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['primary']}", padding=(0, 1))
    t.add_column("CAMPAÑA",  style=C["white"],   min_width=22)
    t.add_column("LEADS",    style=C["muted"],   justify="right")
    t.add_column("MQL",      style=C["muted"],   justify="right")
    t.add_column("CPL",      style=C["accent"],  justify="right")
    t.add_column("CPMQL",    style=C["accent"],  justify="right")
    t.add_column("ROAS",     justify="right")
    t.add_column("ICL",      style=C["primary"], justify="right")
    for _, f in metricas.iterrows():
        roas = f.get("roas", 0)
        rc = C["success"] if roas >= 1 else C["warning"] if roas >= 0.5 else C["error"]
        t.add_row(
            str(f.get(col, "—")),
            str(int(f.get("total_leads", 0))),
            str(int(f.get("total_mql", 0))),
            f"${f.get('cpl', 0):,.0f}",
            f"${f.get('cpmql', 0):,.0f}",
            Text(f"{roas:.2f}", style=f"bold {rc}"),
            f"{f.get('icl', 0):.4f}",
        )
    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['tabla']} MÉTRICAS POR CAMPAÑA ", f"bold {C['primary']}")
    ), border_style=C["primary"]))
    if excluidos > 0:
        console.print(
            f"  [{C['warning']}]{ICON['warn']}  "
            f"{excluidos} leads sin campaña asignada — excluidos del cálculo."
            f"[/{C['warning']}]"
        )
    console.print()


# ─────────────────────────────────────────
# /estado
# ─────────────────────────────────────────

def cmd_estado(engine, config: dict) -> None:
    mem = engine.memoria.resumen() if engine else "Engine no iniciado"
    console.print(Panel(
        Text.assemble(
            ("  Usuario  ", C["dim"]), (config["nombre"],             f"bold {C['accent']}"),  ("\n", ""),
            ("  LLM      ", C["dim"]), (config["llm_provider"],       f"bold {C['white']}"),   ("\n", ""),
            ("  Modelo   ", C["dim"]), (config.get("llm_model", "—"), C["muted"]),             ("\n", ""),
            ("  Fuente   ", C["dim"]), (config["fuente"],             f"bold {C['white']}"),   ("\n", ""),
            ("  Memoria  ", C["dim"]), (mem,                           C["muted"]),
        ),
        title=Text.assemble((f" {ICON['info']} ESTADO ", f"bold {C['accent']}")),
        border_style=C["accent"], padding=(1, 2),
    ))
    console.print()


# ─────────────────────────────────────────
# /guardar
# ─────────────────────────────────────────

def cmd_guardar(historial: list) -> None:
    if not historial:
        console.print(f"  [{C['warning']}]No hay conversación para guardar.[/{C['warning']}]\n")
        return
    fn = f"adly_sesion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(fn, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "rol", "mensaje", "severidad", "confianza"])
        for item in historial:
            w.writerow([item.get("ts",""), item.get("rol",""),
                        item.get("mensaje",""), item.get("severidad",""), item.get("confianza","")])
    console.print(f"  [{C['success']}]{ICON['ok']}  Guardado:[/{C['success']}] [{C['primary']}]{fn}[/{C['primary']}]\n")


# ─────────────────────────────────────────
# /dashboard
# ─────────────────────────────────────────

def cmd_dashboard(metricas, config: dict) -> None:
    if metricas is None or metricas.empty:
        console.print(f"  [{C['warning']}]Sin datos para dashboard.[/{C['warning']}]\n")
        return
    with console.status(f"  [{C['primary']}]Generando dashboard...[/{C['primary']}]", spinner="arc"):
        import time; time.sleep(0.7)
        col  = config.get("col_campana", "campana")
        rows = ""
        for _, f in metricas.iterrows():
            roas  = f.get("roas", 0)
            color = "#00e5ff" if roas >= 1 else "#ff9100" if roas >= 0.5 else "#ff1744"
            rows += (f"<tr><td>{f.get(col,'—')}</td><td>{int(f.get('total_leads',0))}</td>"
                     f"<td>{int(f.get('total_mql',0))}</td><td>${f.get('cpl',0):,.0f}</td>"
                     f"<td>${f.get('cpmql',0):,.0f}</td>"
                     f"<td style='color:{color};font-weight:700'>{roas:.2f}</td>"
                     f"<td>{f.get('icl',0):.4f}</td></tr>")
        html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<title>Adly Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@700&display=swap" rel="stylesheet">
<style>body{{background:#000;color:#b0bec5;font-family:'Share Tech Mono',monospace;padding:48px;}}
h1{{font-family:'Orbitron',sans-serif;color:#00e5ff;text-shadow:0 0 30px #00e5ff66;font-size:2rem;margin-bottom:4px;}}
.sub{{color:#455a64;margin-bottom:48px;font-size:.82rem;letter-spacing:.1em;}}
table{{width:100%;border-collapse:collapse;}}
th{{font-family:'Orbitron',sans-serif;font-size:.6rem;letter-spacing:.2em;color:#00e5ff;padding:14px 16px;border-bottom:1px solid #00e5ff33;text-align:left;}}
td{{padding:12px 16px;border-bottom:1px solid #ffffff08;}}
tr:hover td{{background:#00e5ff08;}}</style></head><body>
<h1>▸ ADLY</h1><div class="sub">{datetime.now().strftime('%Y-%m-%d %H:%M')} · {config.get('nombre','—')} · {VERSION}</div>
<table><thead><tr><th>CAMPAÑA</th><th>LEADS</th><th>MQL</th><th>CPL</th><th>CPMQL</th><th>ROAS</th><th>ICL</th></tr></thead>
<tbody>{rows}</tbody></table></body></html>"""
        fn = f"adly_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(html)
    console.print(f"  [{C['success']}]{ICON['ok']}[/{C['success']}] [{C['primary']}]{fn}[/{C['primary']}]")
    try:
        webbrowser.open(f"file://{Path(fn).resolve()}")
        console.print(f"  [{C['dim']}]Abriendo en navegador...[/{C['dim']}]\n")
    except Exception:
        console.print(f"  [{C['dim']}]Ábrelo manualmente.[/{C['dim']}]\n")


# ─────────────────────────────────────────
# /head  /sample  /describe  /exportar
# ─────────────────────────────────────────

# Columnas que pandas ve como número pero son semánticamente IDs
_PATRONES_ID = {"id", "telefono", "phone", "tel", "cel", "celular", "codigo", "code", "zip", "cp"}

def _es_id_semantico(col: str) -> bool:
    return any(p in col.lower() for p in _PATRONES_ID)


def cmd_head(df, n: int = 5) -> None:
    _tabla_dataframe(df, df.head(n) if df is not None else None,
                     f"HEAD — primeras {n} filas", C["primary"])


def cmd_sample(df, n: int = 5) -> None:
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return
    _tabla_dataframe(df, df.sample(min(n, len(df))),
                     f"SAMPLE — {n} filas aleatorias", C["accent"])


def _tabla_dataframe(df, sub, titulo_str: str, color: str) -> None:
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos. Usa /refresh.[/{C['warning']}]\n")
        return
    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {color}", padding=(0, 1))
    for col in sub.columns:
        t.add_column(str(col), style=C["muted"], no_wrap=True)
    for _, row in sub.iterrows():
        t.add_row(*[str(v) if v is not None else "—" for v in row])
    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['tabla']} {titulo_str} ", f"bold {color}")
    ), border_style=color))
    console.print()


def cmd_describe(df) -> None:
    """
    /describe mejorado — excluye columnas semánticas tipo ID/teléfono.
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos. Usa /refresh.[/{C['warning']}]\n")
        return
    numericas = df.select_dtypes(include="number")
    # Excluir columnas semánticas tipo ID
    cols_analisis = [c for c in numericas.columns if not _es_id_semantico(c)]
    if not cols_analisis:
        console.print(f"  [{C['warning']}]No hay columnas numéricas analizables (excluyendo IDs).[/{C['warning']}]\n")
        return
    desc = numericas[cols_analisis].describe().round(2)
    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['primary']}", padding=(0, 1))
    t.add_column("STAT", style=f"bold {C['accent']}", width=8)
    for col in desc.columns:
        t.add_column(str(col), style=C["muted"], justify="right")
    for idx, row in desc.iterrows():
        t.add_row(str(idx), *[f"{v:,.2f}" for v in row])
    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['tabla']} DESCRIBE — columnas numéricas ", f"bold {C['primary']}")
    ), border_style=C["primary"]))
    excluidas = [c for c in numericas.columns if _es_id_semantico(c)]
    note = f" · excluidas como ID: {', '.join(excluidas)}" if excluidas else ""
    console.print(f"  [{C['dim']}]{len(df)} filas · {len(df.columns)} columnas{note}[/{C['dim']}]\n")


def cmd_exportar_df(df) -> None:
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos. Usa /refresh.[/{C['warning']}]\n")
        return
    fn = f"adly_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(fn, index=False)
    console.print(f"  [{C['success']}]{ICON['ok']} Exportado:[/{C['success']}] "
                  f"[{C['primary']}]{fn}[/{C['primary']}] [{C['dim']}]({len(df)} filas)[/{C['dim']}]\n")


# ─────────────────────────────────────────
# NUEVOS — EXPLORACIÓN ESTADÍSTICA
# ─────────────────────────────────────────

# Tipos semánticos inferidos por nombre de columna
_TIPOS_SEMANTICOS = {
    "id":       ["id", "ghl_id", "lead_id", "record_id", "uid"],
    "telefono": ["telefono", "phone", "tel", "cel", "celular", "mobile"],
    "email":    ["email", "correo", "mail"],
    "fecha":    ["fecha", "date", "ts", "timestamp", "creacion", "cierre", "update"],
    "nombre":   ["nombre", "name", "apellido"],
    "moneda":   ["costo", "valor", "precio", "ingreso", "revenue", "spend", "cost", "cpl", "cpa"],
    "tasa":     ["tasa", "rate", "ratio", "roas", "icl", "ctr"],
    "categoria": ["estado", "status", "campana", "campaign", "adset", "ad", "fuente", "source"],
}

def _tipo_semantico(col: str) -> str:
    col_lower = col.lower()
    for tipo, patrones in _TIPOS_SEMANTICOS.items():
        if any(p in col_lower for p in patrones):
            return tipo
    return "dato"


def cmd_columnas(df) -> None:
    """
    /columnas — schema completo con tipo pandas + tipo semántico + nulos + completitud.
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return

    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['primary']}", padding=(0, 1))
    t.add_column("COLUMNA",    style=C["white"],   min_width=20)
    t.add_column("TIPO",       style=C["muted"],   width=10)
    t.add_column("SEMÁNTICO",  style=C["primary"], width=12)
    t.add_column("NULOS",      justify="right",    width=8)
    t.add_column("COMPLETO",   justify="right",    width=10)

    total = len(df)
    for col in df.columns:
        dtype  = str(df[col].dtype)
        nulos  = int(df[col].isna().sum())
        pct    = (total - nulos) / total * 100
        sem    = _tipo_semantico(col)
        pct_color = C["success"] if pct >= 95 else C["warning"] if pct >= 80 else C["error"]

        t.add_row(
            col,
            dtype,
            sem,
            str(nulos) if nulos > 0 else Text("0", style=C["dim"]),
            Text(f"{pct:.1f}%", style=f"bold {pct_color}"),
        )

    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['tabla']} SCHEMA — {len(df.columns)} columnas · {total} filas ", f"bold {C['primary']}")
    ), border_style=C["primary"]))
    console.print(f"  [{C['dim']}]Tip: /ayuda --columnas para más info[/{C['dim']}]\n")


def cmd_nulos(df) -> None:
    """
    /nulos — ranking de columnas con más valores nulos.
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return

    total = len(df)
    nulos = df.isna().sum()
    nulos = nulos[nulos > 0].sort_values(ascending=False)

    if nulos.empty:
        console.print(f"  [{C['success']}]{ICON['ok']} Dataset sin valores nulos.[/{C['success']}]\n")
        return

    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['warning']}", padding=(0, 1))
    t.add_column("COLUMNA",  style=C["white"],   min_width=20)
    t.add_column("NULOS",    justify="right",    width=8)
    t.add_column("%",        justify="right",    width=8)
    t.add_column("IMPACTO",  style=C["muted"],   width=20)

    for col, n in nulos.items():
        pct = n / total * 100
        if pct >= 30:
            color, impacto = C["error"],   "⚡ crítico"
        elif pct >= 10:
            color, impacto = C["warning"], "⚠ revisar"
        else:
            color, impacto = C["muted"],   "ok"
        t.add_row(col, Text(str(n), style=f"bold {color}"),
                  Text(f"{pct:.1f}%", style=f"bold {color}"), impacto)

    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['warn']} NULOS — {len(nulos)} columnas afectadas ", f"bold {C['warning']}")
    ), border_style=C["warning"]))
    console.print(f"  [{C['dim']}]Tip: /rellenar [columna] [estrategia] para corregir[/{C['dim']}]\n")


def cmd_outliers(df, col: str = "") -> None:
    """
    /outliers [col] — detección IQR. Sin col: corre en todas las numéricas.
    Método: outlier = valor fuera de [Q1 - 1.5·IQR, Q3 + 1.5·IQR]
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return

    numericas = df.select_dtypes(include="number")
    cols = ([col] if col and col in numericas.columns
            else [c for c in numericas.columns if not _es_id_semantico(c)])

    if not cols:
        console.print(f"  [{C['warning']}]Columna '{col}' no encontrada o no es numérica.[/{C['warning']}]\n")
        return

    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['error']}", padding=(0, 1))
    t.add_column("COLUMNA",   style=C["white"],   min_width=18)
    t.add_column("OUTLIERS",  justify="right",    width=10)
    t.add_column("%",         justify="right",    width=8)
    t.add_column("LÍMITE INF", justify="right",   width=14)
    t.add_column("LÍMITE SUP", justify="right",   width=14)
    t.add_column("MIN DATOS", justify="right",    width=14)
    t.add_column("MAX DATOS", justify="right",    width=14)

    total = len(df)
    encontrados = 0

    for c in cols:
        serie = df[c].dropna()
        if serie.empty:
            continue
        q1  = serie.quantile(0.25)
        q3  = serie.quantile(0.75)
        iqr = q3 - q1
        lim_inf = q1 - 1.5 * iqr
        lim_sup = q3 + 1.5 * iqr
        outliers = serie[(serie < lim_inf) | (serie > lim_sup)]
        n = len(outliers)
        if n == 0:
            continue
        encontrados += 1
        pct = n / total * 100
        color = C["error"] if pct > 5 else C["warning"]
        t.add_row(
            c,
            Text(str(n), style=f"bold {color}"),
            Text(f"{pct:.1f}%", style=f"bold {color}"),
            f"{lim_inf:,.2f}",
            f"{lim_sup:,.2f}",
            f"{serie.min():,.2f}",
            f"{serie.max():,.2f}",
        )

    if encontrados == 0:
        console.print(f"  [{C['success']}]{ICON['ok']} Sin outliers detectados en {', '.join(cols)}.[/{C['success']}]\n")
        return

    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['crit']} OUTLIERS — método IQR ", f"bold {C['error']}")
    ), border_style=C["error"]))
    console.print(f"  [{C['dim']}]Outlier = valor fuera de [Q1 - 1.5·IQR, Q3 + 1.5·IQR][/{C['dim']}]")
    console.print(f"  [{C['dim']}]Tip: /eliminar_por [col] < [límite] para removerlos[/{C['dim']}]\n")


def cmd_correlacion(df) -> None:
    """
    /correlacion — matriz de Pearson entre columnas numéricas.
    Excluye IDs semánticos.
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return

    numericas = df.select_dtypes(include="number")
    cols = [c for c in numericas.columns if not _es_id_semantico(c)]

    if len(cols) < 2:
        console.print(f"  [{C['warning']}]Se necesitan al menos 2 columnas numéricas.[/{C['warning']}]\n")
        return

    corr = numericas[cols].corr().round(2)

    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['cyan']}", padding=(0, 1))
    t.add_column("", style=f"bold {C['primary']}", width=16)
    for c in corr.columns:
        t.add_column(c[:12], justify="right", width=10)

    for idx, row in corr.iterrows():
        celdas = []
        for c in corr.columns:
            v = row[c]
            if idx == c:
                celdas.append(Text("  1.00", style=C["dim"]))
            elif abs(v) >= 0.7:
                celdas.append(Text(f"{v:+.2f}", style=f"bold {C['error'] if v < 0 else C['success']}"))
            elif abs(v) >= 0.4:
                celdas.append(Text(f"{v:+.2f}", style=C["warning"]))
            else:
                celdas.append(Text(f"{v:+.2f}", style=C["dim"]))
        t.add_row(str(idx)[:16], *celdas)

    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['tabla']} CORRELACIÓN DE PEARSON ", f"bold {C['cyan']}")
    ), border_style=C["cyan"]))
    console.print(
        f"  [{C['dim']}]"
        f"[{C['success']}]verde ≥ 0.7[/{C['success']}]  "
        f"[{C['warning']}]ámbar ≥ 0.4[/{C['warning']}]  "
        f"[{C['error']}]rojo ≤ -0.7[/{C['error']}]  "
        f"gris = débil"
        f"[/{C['dim']}]\n"
    )


def cmd_unicos(df, col: str = "") -> None:
    """
    /unicos [col] — valores únicos con frecuencia, ordenados de mayor a menor.
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return
    if not col or col not in df.columns:
        console.print(f"  [{C['warning']}]Especifica una columna válida. Ej: /unicos estado[/{C['warning']}]\n")
        console.print(f"  [{C['dim']}]Columnas disponibles: {', '.join(df.columns.tolist())}[/{C['dim']}]\n")
        return

    vc = df[col].value_counts(dropna=False)
    total = len(df)

    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['accent']}", padding=(0, 1))
    t.add_column("VALOR",  style=C["white"],  min_width=20)
    t.add_column("COUNT",  justify="right",   width=8)
    t.add_column("%",      justify="right",   width=8)
    t.add_column("BAR",    style=C["primary"], width=20)

    for val, cnt in vc.items():
        pct = cnt / total * 100
        bar_len = int(pct / 5)  # max 20 chars = 100%
        bar = "█" * bar_len + "░" * (20 - bar_len)
        t.add_row(
            str(val) if str(val) != "nan" else Text("(nulo)", style=C["dim"]),
            str(cnt),
            f"{pct:.1f}%",
            bar,
        )

    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['lista']} ÚNICOS — {col} ({len(vc)} valores) ", f"bold {C['accent']}")
    ), border_style=C["accent"]))
    console.print()


def cmd_rango(df, col: str = "") -> None:
    """
    /rango [col] — estadísticas detalladas de una columna numérica.
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return
    if not col or col not in df.columns:
        numericas = [c for c in df.select_dtypes(include="number").columns if not _es_id_semantico(c)]
        console.print(f"  [{C['warning']}]Especifica una columna numérica. Ej: /rango costo_lead[/{C['warning']}]\n")
        console.print(f"  [{C['dim']}]Numéricas disponibles: {', '.join(numericas)}[/{C['dim']}]\n")
        return
    if col not in df.select_dtypes(include="number").columns:
        console.print(f"  [{C['warning']}]'{col}' no es numérica.[/{C['warning']}]\n")
        return

    s = df[col].dropna()
    q1  = s.quantile(0.25)
    q3  = s.quantile(0.75)
    iqr = q3 - q1

    stats = [
        ("count",    f"{len(s):,}",          "Registros sin nulos"),
        ("nulos",    f"{df[col].isna().sum():,}", "Valores faltantes"),
        ("min",      f"{s.min():,.2f}",       "Valor mínimo"),
        ("max",      f"{s.max():,.2f}",       "Valor máximo"),
        ("media",    f"{s.mean():,.2f}",      "Promedio aritmético"),
        ("mediana",  f"{s.median():,.2f}",    "Valor central (robusto a outliers)"),
        ("std",      f"{s.std():,.2f}",       "Desviación estándar"),
        ("Q1",       f"{q1:,.2f}",            "Percentil 25"),
        ("Q3",       f"{q3:,.2f}",            "Percentil 75"),
        ("IQR",      f"{iqr:,.2f}",           "Rango intercuartílico (Q3-Q1)"),
        ("lím. inf", f"{q1 - 1.5*iqr:,.2f}", "Límite inferior outliers (IQR)"),
        ("lím. sup", f"{q3 + 1.5*iqr:,.2f}", "Límite superior outliers (IQR)"),
    ]

    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style=f"bold {C['accent']}", width=12)
    t.add_column(style=f"bold {C['white']}",  width=16, justify="right")
    t.add_column(style=C["dim"])
    for label, val, desc in stats:
        t.add_row(label, val, desc)

    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['info']} RANGO — {col} ", f"bold {C['accent']}")
    ), border_style=C["accent"]))
    console.print()


def cmd_top(df, col: str = "", n: int = 10) -> None:
    """
    /top [col] [N] — top N valores más frecuentes de una columna.
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return
    if not col or col not in df.columns:
        console.print(f"  [{C['warning']}]Especifica una columna. Ej: /top campana 5[/{C['warning']}]\n")
        return

    vc = df[col].value_counts(dropna=True).head(n)
    total = len(df)

    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['primary']}", padding=(0, 1))
    t.add_column("#",      style=C["dim"],     width=4,  justify="right")
    t.add_column("VALOR",  style=C["white"],   min_width=20)
    t.add_column("COUNT",  justify="right",    width=8)
    t.add_column("%",      justify="right",    width=8)

    for i, (val, cnt) in enumerate(vc.items(), 1):
        pct = cnt / total * 100
        t.add_row(str(i), str(val), str(cnt), f"{pct:.1f}%")

    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['bullet']} TOP {n} — {col} ", f"bold {C['primary']}")
    ), border_style=C["primary"]))
    console.print()


# ─────────────────────────────────────────
# /limpiar_duplicados  /rellenar  /eliminar_por
# ─────────────────────────────────────────

def _recalcular_contexto(df_ghl, engine, calc):
    try:
        metricas    = calc.calcular(df_ghl, nivel="campana")
        resumen_llm = calc.resumen_para_llm(metricas, nivel="campana")
        schema_llm  = calc.resumen_schema(df_ghl)
        if engine:
            engine.set_contexto_completo(resumen_llm, schema_llm)
            engine.limpiar_memoria()
        return metricas, resumen_llm, schema_llm
    except Exception as e:
        console.print(f"  [{C['warning']}]{ICON['warn']} No se pudo recalcular contexto: {e}[/{C['warning']}]\n")
        return None, None, None


def cmd_limpiar_duplicados(df_ghl, engine, validator, calc):
    if df_ghl is None or df_ghl.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return df_ghl
    n_antes = len(df_ghl)
    df_limpio, _ = validator.limpiar_duplicados(df_ghl)
    n_eliminados = n_antes - len(df_limpio)
    if n_eliminados == 0:
        console.print(f"  [{C['success']}]{ICON['ok']} Sin duplicados encontrados.[/{C['success']}]\n")
        return df_ghl
    console.print(
        f"  [{C['success']}]{ICON['ok']} Eliminados:[/{C['success']}] "
        f"[{C['accent']}]{n_eliminados} duplicados[/{C['accent']}] "
        f"[{C['dim']}]({n_antes} → {len(df_limpio)} filas)[/{C['dim']}]"
    )
    _recalcular_contexto(df_limpio, engine, calc)
    console.print(f"  [{C['dim']}]Contexto actualizado.[/{C['dim']}]\n")
    return df_limpio


def cmd_rellenar(df_ghl, engine, validator, calc, partes: list):
    ESTRATEGIAS = {"media", "mediana", "moda", "valor"}
    if len(partes) < 3:
        console.print(f"  [{C['warning']}]Uso: /rellenar [columna] [estrategia][/{C['warning']}]\n")
        console.print(f"  [{C['dim']}]Estrategias: {', '.join(ESTRATEGIAS)} · Ej: /rellenar costo_lead media[/{C['dim']}]\n")
        return df_ghl
    columna    = partes[1]
    estrategia = partes[2].lower()
    valor_relleno = partes[3] if len(partes) > 3 else None
    if estrategia not in ESTRATEGIAS:
        console.print(f"  [{C['warning']}]Estrategia '{estrategia}' inválida. Usa: {', '.join(ESTRATEGIAS)}[/{C['warning']}]\n")
        return df_ghl
    df_nuevo, reporte = validator.rellenar_nulos(df_ghl, columna, estrategia, valor_relleno)
    if reporte.get("error"):
        console.print(f"  [{C['error']}]{ICON['crit']} {reporte['error']}[/{C['error']}]\n")
        return df_ghl
    n = reporte.get("rellenados", 0)
    console.print(
        f"  [{C['success']}]{ICON['ok']} Rellenados:[/{C['success']}] "
        f"[{C['accent']}]{n} nulos[/{C['accent']}] en [{C['primary']}]{columna}[/{C['primary']}] con '{estrategia}'"
    )
    _recalcular_contexto(df_nuevo, engine, calc)
    console.print(f"  [{C['dim']}]Contexto actualizado.[/{C['dim']}]\n")
    return df_nuevo


def cmd_eliminar_por(df_ghl, engine, validator, calc, partes: list):
    """
    Fix: isnull/notnull son operadores unarios — solo necesitan columna, no valor.
    Sintaxis: /eliminar_por [col] [op]           → para isnull/notnull
              /eliminar_por [col] [op] [valor]   → para == != > < >= <=
    """
    OPERADORES_UNARIOS  = {"isnull", "notnull"}
    OPERADORES_BINARIOS = {"==", "!=", ">", "<", ">=", "<="}

    if len(partes) < 3:
        console.print(
            f"  [{C['warning']}]Uso: /eliminar_por [col] [op] ([valor])\n"
            f"  Unarios (sin valor): isnull · notnull\n"
            f"  Binarios (con valor): == != > < >= <=\n"
            f"  Ej: /eliminar_por campana isnull\n"
            f"  Ej: /eliminar_por costo_lead < 0[/{C['warning']}]\n"
        )
        return df_ghl

    columna  = partes[1]
    operador = partes[2].lower()

    if operador in OPERADORES_UNARIOS:
        valor = None
    elif operador in OPERADORES_BINARIOS:
        if len(partes) < 4:
            console.print(
                f"  [{C['warning']}]'{operador}' requiere un valor. "
                f"Ej: /eliminar_por costo_lead {operador} 0[/{C['warning']}]\n"
            )
            return df_ghl
        raw = partes[3]
        try:
            valor = float(raw) if "." in raw else int(raw)
        except ValueError:
            valor = raw
    else:
        console.print(
            f"  [{C['warning']}]Operador '{operador}' no reconocido.\n"
            f"  Unarios: isnull · notnull\n"
            f"  Binarios: == != > < >= <=[/{C['warning']}]\n"
        )
        return df_ghl

    df_filtrado, reporte = validator.eliminar_por_criterio(df_ghl, columna, operador, valor)

    if reporte.get("error"):
        console.print(f"  [{C['error']}]{ICON['crit']} {reporte['error']}[/{C['error']}]\n")
        return df_ghl

    n = reporte["eliminados"]
    criterio = reporte["criterio"]

    if n == 0:
        console.print(f"  [{C['success']}]{ICON['ok']} Ninguna fila cumple '{criterio}' — sin cambios.[/{C['success']}]\n")
        return df_ghl

    console.print(
        f"  [{C['success']}]{ICON['ok']} Eliminadas:[/{C['success']}] "
        f"[{C['accent']}]{n} filas[/{C['accent']}] donde [{C['primary']}]{criterio}[/{C['primary']}]"
    )
    _recalcular_contexto(df_filtrado, engine, calc)
    console.print(f"  [{C['dim']}]Contexto actualizado — {len(df_filtrado)} filas activas.[/{C['dim']}]\n")
    return df_filtrado


# ─────────────────────────────────────────
# MODELOS ESTADÍSTICOS — MARKETING ANALYTICS
# Agnósticos: detectan columnas por patrón semántico
# Comandos: /cohorts /rentabilidad /rfm /embudo /velocidad
# ─────────────────────────────────────────

import pandas as pd
import numpy as np
from datetime import timedelta


# ── Detección agnóstica de columnas clave ─────────────────────────────────────

def _detectar_col(df, patrones: list, excluir: list = []) -> str:
    """Detecta la primera columna que coincide con algún patrón semántico."""
    for col in df.columns:
        col_l = col.lower()
        if any(p in col_l for p in patrones) and col not in excluir:
            return col
    return ""

def _cols_modelo(df) -> dict:
    """
    Detecta columnas clave para modelos de marketing.
    Retorna dict con las columnas encontradas o "" si no existen.
    """
    return {
        "campana":        _detectar_col(df, ["campana", "campaign", "utm_campaign"]),
        "adset":          _detectar_col(df, ["adset", "ad_set", "conjunto"]),
        "estado":         _detectar_col(df, ["estado", "status", "stage", "funnel_stage"]),
        "costo":          _detectar_col(df, ["costo_lead", "cpl", "cost", "spend", "costo"]),
        "valor_venta":    _detectar_col(df, ["valor_venta", "revenue", "valor", "ingreso", "amount"]),
        "fecha_entrada":  _detectar_col(df, ["fecha_creacion", "created", "creacion", "record_ts", "fecha_entrada"]),
        "fecha_cierre":   _detectar_col(df, ["fecha_cierre", "closed", "close_date", "fecha_venta"]),
        "id":             _detectar_col(df, ["ghl_id", "lead_id", "id", "uid"]),
    }

def _estados_venta(df, col_estado: str) -> list:
    """Detecta qué valores de la columna estado representan una venta."""
    if not col_estado:
        return []
    vals = df[col_estado].dropna().unique()
    patrones_venta = {"venta", "sale", "won", "cerrado", "closed", "converted", "vendido"}
    return [v for v in vals if str(v).lower() in patrones_venta]


def _normalizar_estados_df(df: pd.DataFrame, col_estado: str) -> tuple:
    """
    Normaliza col_estado con ValueMapper antes de análisis.
    Retorna (df_normalizado, lista_no_reconocidos).
    Reutilizable en cohorts, rfm y cualquier comando que analice estados.
    """
    try:
        from src.processing.value_mapper import ValueMapper
        vm = ValueMapper()
        df, no_rec = vm.normalizar_estados(df, col_estado)
        return df, no_rec
    except Exception:
        return df, []


def _aviso_cols_faltantes(faltantes: list) -> None:
    console.print(
        f"  [{C['warning']}]{ICON['warn']} Columnas necesarias no detectadas: "
        f"{', '.join(faltantes)}[/{C['warning']}]"
    )
    console.print(
        f"  [{C['dim']}]Tip: /columnas para ver el schema completo[/{C['dim']}]\n"
    )


# ── /cohorts ─────────────────────────────────────────────────────────────────

def cmd_cohorts(df) -> str | None:
    """
    /cohorts — análisis de cohortes por mes de entrada.

    Agrupa leads por mes de creación y calcula tasa de conversión,
    CPL promedio y valor generado por cohorte.
    Detecta si las campañas recientes son mejores o peores que las anteriores.
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return

    cols = _cols_modelo(df)
    faltantes = [k for k in ["fecha_entrada", "estado"] if not cols[k]]
    if faltantes:
        _aviso_cols_faltantes(faltantes)
        return

    col_fecha   = cols["fecha_entrada"]
    col_estado  = cols["estado"]
    col_costo   = cols["costo"]
    col_valor   = cols["valor_venta"]
    col_campana = cols["campana"]

    estados_venta = _estados_venta(df, col_estado)
    if not estados_venta:
        console.print(f"  [{C['warning']}]{ICON['warn']} No se detectaron valores de venta en '{col_estado}'.[/{C['warning']}]\n")
        console.print(f"  [{C['dim']}]Valores únicos: {df[col_estado].unique().tolist()}[/{C['dim']}]\n")
        return

    df2 = df.copy()

    # Normalizar estados antes de analizar
    df2, no_rec = _normalizar_estados_df(df2, col_estado)
    if no_rec:
        vals_str = ", ".join(f"'{v}' ({c})" for v, c in no_rec)
        console.print(f"  [{C['warning']}]{ICON['warn']} Estados no reconocidos excluidos: {vals_str}[/{C['warning']}]")

    try:
        df2[col_fecha] = pd.to_datetime(df2[col_fecha], errors="coerce")
    except Exception:
        console.print(f"  [{C['error']}]No se pudo parsear '{col_fecha}' como fecha.[/{C['error']}]\n")
        return

    # Detectar y advertir fechas inválidas (NaT) antes de agrupar
    n_invalidas = df2[col_fecha].isna().sum()
    if n_invalidas > 0:
        console.print(
            f"  [{C['warning']}]{ICON['warn']} {n_invalidas} registros con fecha inválida excluidos de cohortes.[/{C['warning']}]"
        )
        df2 = df2[df2[col_fecha].notna()]

    if df2.empty:
        console.print(f"  [yellow]Sin registros con fechas válidas.[/yellow]\n")
        return

    df2["_cohorte"] = df2[col_fecha].dt.to_period("M").astype(str)
    df2["_es_venta"] = df2[col_estado].isin(estados_venta)

    grupos = df2.groupby("_cohorte")
    filas = []
    for cohorte, grupo in sorted(grupos):
        total    = len(grupo)
        ventas   = grupo["_es_venta"].sum()
        tasa     = ventas / total * 100 if total > 0 else 0
        cpl_avg  = grupo[col_costo].mean() if col_costo else None
        val_avg  = grupo[col_valor][grupo["_es_venta"]].mean() if col_valor else None
        val_tot  = grupo[col_valor][grupo["_es_venta"]].sum() if col_valor else None
        filas.append((cohorte, total, int(ventas), tasa, cpl_avg, val_avg, val_tot))

    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['cyan']}", padding=(0, 1))
    t.add_column("COHORTE",    style=C["white"],   min_width=10)
    t.add_column("LEADS",      justify="right",    width=7)
    t.add_column("VENTAS",     justify="right",    width=7)
    t.add_column("CONV %",     justify="right",    width=8)
    if col_costo:
        t.add_column("CPL PROM",  justify="right", width=12)
    if col_valor:
        t.add_column("VAL/VENTA", justify="right", width=12)
        t.add_column("TOTAL",     justify="right", width=14)

    tasas = [f[3] for f in filas]
    tasa_max = max(tasas) if tasas else 1

    for cohorte, total, ventas, tasa, cpl_avg, val_avg, val_tot in filas:
        color = C["success"] if tasa >= tasa_max * 0.8 else C["warning"] if tasa >= tasa_max * 0.5 else C["error"]
        fila = [
            cohorte,
            str(total),
            str(ventas),
            Text(f"{tasa:.1f}%", style=f"bold {color}"),
        ]
        if col_costo:
            fila.append(f"${cpl_avg:,.0f}" if cpl_avg and not np.isnan(cpl_avg) else "—")
        if col_valor:
            fila.append(f"${val_avg:,.0f}" if val_avg and not np.isnan(val_avg) else "—")
            fila.append(f"${val_tot:,.0f}" if val_tot and not np.isnan(val_tot) else "—")
        t.add_row(*fila)

    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['tabla']} COHORTES — por mes de entrada ", f"bold {C['cyan']}")
    ), border_style=C["cyan"]))

    # Insight automático
    if len(filas) >= 2:
        primera_tasa = filas[0][3]
        ultima_tasa  = filas[-1][3]
        diff = ultima_tasa - primera_tasa
        if abs(diff) > 2:
            trend_color = C["success"] if diff > 0 else C["error"]
            trend_txt   = f"mejorando +{diff:.1f}pp" if diff > 0 else f"cayendo {diff:.1f}pp"
            console.print(
                f"  [{trend_color}]{ICON['arrow']} Tendencia: la conversión va {trend_txt} "
                f"vs la primera cohorte[/{trend_color}]"
            )
    console.print(f"  [{C['dim']}]pp = puntos porcentuales[/{C['dim']}]\n")

    # Contexto para el engine
    resumen_filas = []
    for cohorte, total, ventas, tasa, cpl_avg, *_ in filas:
        cpl_str = f"CPL ${cpl_avg:,.0f}" if cpl_avg and not (cpl_avg != cpl_avg) else ""
        resumen_filas.append(f"{cohorte}: {total} leads, {ventas} ventas, conv {tasa:.1f}% {cpl_str}".strip())
    return "Cohortes por mes:\n" + "\n".join(resumen_filas)


# ── /rentabilidad ────────────────────────────────────────────────────────────

def cmd_rentabilidad(df) -> None:
    """
    /rentabilidad — CAC vs LTV por campaña.

    CAC  = costo total invertido / número de ventas
    LTV  = valor promedio por venta (simplificado, sin churn)
    ROI  = (LTV - CAC) / CAC × 100
    Payback = cuántos leads hay que convertir para recuperar el CAC
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return

    cols = _cols_modelo(df)
    faltantes = [k for k in ["campana", "costo", "valor_venta", "estado"] if not cols[k]]
    if faltantes:
        _aviso_cols_faltantes(faltantes)
        return

    col_campana = cols["campana"]
    col_costo   = cols["costo"]
    col_valor   = cols["valor_venta"]
    col_estado  = cols["estado"]

    estados_venta = _estados_venta(df, col_estado)
    if not estados_venta:
        console.print(f"  [{C['warning']}]No se detectaron ventas en '{col_estado}'.[/{C['warning']}]\n")
        return

    df2 = df.copy()
    df2["_es_venta"] = df2[col_estado].isin(estados_venta)

    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['success']}", padding=(0, 1))
    t.add_column("CAMPAÑA",   style=C["white"],   min_width=22)
    t.add_column("LEADS",     justify="right",    width=7)
    t.add_column("VENTAS",    justify="right",    width=7)
    t.add_column("CAC",       justify="right",    width=12)
    t.add_column("LTV",       justify="right",    width=12)
    t.add_column("ROI %",     justify="right",    width=9)
    t.add_column("VERDICT",   width=14)

    for campana, grupo in df2.groupby(col_campana):
        total       = len(grupo)
        ventas      = grupo["_es_venta"].sum()
        if ventas == 0:
            continue
        costo_total = grupo[col_costo].sum()
        cac         = costo_total / ventas
        ltv         = grupo[col_valor][grupo["_es_venta"]].mean()
        roi         = (ltv - cac) / cac * 100 if cac > 0 else 0

        if roi >= 100:
            roi_color, verdict = C["success"], f"{ICON['ok']} rentable"
        elif roi >= 0:
            roi_color, verdict = C["warning"], f"{ICON['warn']} ajustado"
        else:
            roi_color, verdict = C["error"],   f"{ICON['crit']} pérdida"

        t.add_row(
            str(campana),
            str(total),
            str(int(ventas)),
            f"${cac:,.0f}",
            f"${ltv:,.0f}" if not np.isnan(ltv) else "—",
            Text(f"{roi:+.0f}%", style=f"bold {roi_color}"),
            Text(verdict, style=roi_color),
        )

    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['bullet']} CAC / LTV — RENTABILIDAD POR CAMPAÑA ", f"bold {C['success']}")
    ), border_style=C["success"]))
    console.print(
        f"  [{C['dim']}]"
        f"CAC = costo total / ventas · "
        f"LTV = valor promedio por venta · "
        f"ROI = (LTV-CAC)/CAC"
        f"[/{C['dim']}]\n"
    )


# ── /rfm ─────────────────────────────────────────────────────────────────────

def cmd_rfm(df) -> str | None:
    """
    /rfm — segmentación RFM adaptada a leads de marketing.

    Recency   = días desde que entró el lead (más reciente = mejor)
    Frequency = no aplica en CRM de leads, se reemplaza por
                Funnel Stage Score (qué tan lejos llegó en el embudo)
    Monetary  = valor de venta si cerró, o costo_lead si no

    Segmentos resultantes:
      Campeón    — reciente, avanzó lejos, alto valor
      Potencial  — reciente pero no cerró aún
      En riesgo  — antiguo, no cerró
      Frío       — antiguo, bajo valor, no avanzó
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return

    cols = _cols_modelo(df)
    faltantes = [k for k in ["fecha_entrada", "estado"] if not cols[k]]
    if faltantes:
        _aviso_cols_faltantes(faltantes)
        return

    col_fecha  = cols["fecha_entrada"]
    col_estado = cols["estado"]
    col_valor  = cols["valor_venta"]
    col_costo  = cols["costo"]
    col_camp   = cols["campana"]

    estados_venta = _estados_venta(df, col_estado)

    df2 = df.copy()

    # Normalizar estados antes de analizar
    df2, no_rec = _normalizar_estados_df(df2, col_estado)
    if no_rec:
        vals_str = ", ".join(f"'{v}' ({c})" for v, c in no_rec)
        console.print(f"  [{C['warning']}]{ICON['warn']} Estados no reconocidos excluidos: {vals_str}[/{C['warning']}]")

    try:
        df2[col_fecha] = pd.to_datetime(df2[col_fecha], errors="coerce")
    except Exception:
        console.print(f"  [{C['error']}]No se pudo parsear '{col_fecha}'.[/{C['error']}]\n")
        return

    fecha_ref = df2[col_fecha].max()
    df2["_recency"] = (fecha_ref - df2[col_fecha]).dt.days
    df2["_es_venta"] = df2[col_estado].isin(estados_venta)

    # Score R (recency): 1-4, menor días = mayor score
    df2["_r"] = pd.qcut(
        df2["_recency"].rank(method="first", na_option="bottom"), 4,
        labels=[4, 3, 2, 1]
    ).cat.add_categories([0]).fillna(0).astype(int) 

    # Score M (monetary): valor_venta si cerró, costo_lead si no
    if col_valor:
        df2["_monetary"] = df2.apply(
            lambda row: row[col_valor] if row["_es_venta"] and row[col_valor] > 0 else row[col_costo]
            if col_costo else 0, axis=1
        )
    elif col_costo:
        df2["_monetary"] = df2[col_costo]
    else:
        df2["_monetary"] = 0

    df2["_m"] = pd.qcut(
        df2["_monetary"].rank(method="first", na_option="bottom"), 4,
        labels=[1, 2, 3, 4]).cat.add_categories([0]).fillna(0).astype(int)
    
    df2["_rfm_score"] = df2["_r"] + df2["_m"]

    # Segmentación
    def segmentar(row):
        if row["_es_venta"] and row["_rfm_score"] >= 7:
            return "Campeón"
        elif not row["_es_venta"] and row["_r"] >= 3:
            return "Potencial"
        elif not row["_es_venta"] and row["_r"] <= 2:
            return "En riesgo"
        else:
            return "Frío"

    df2["_segmento"] = df2.apply(segmentar, axis=1)

    seg_counts = df2["_segmento"].value_counts()
    total = len(df2)

    # Tabla resumen por segmento
    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['primary']}", padding=(0, 1))
    t.add_column("SEGMENTO",   style=C["white"],  min_width=14)
    t.add_column("LEADS",      justify="right",   width=8)
    t.add_column("%",          justify="right",   width=7)
    t.add_column("QUÉ HACER",  style=C["muted"],  min_width=36)

    ACCIONES = {
        "Campeón":   (C["success"], "Escalar inversión — duplicar presupuesto de su campaña"),
        "Potencial": (C["primary"], "Activar seguimiento comercial inmediato"),
        "En riesgo": (C["warning"], "Campaña de reactivación o win-back"),
        "Frío":      (C["dim"],     "Excluir de audiencias — no invertir más"),
    }

    for seg in ["Campeón", "Potencial", "En riesgo", "Frío"]:
        n = seg_counts.get(seg, 0)
        pct = n / total * 100
        color, accion = ACCIONES[seg]
        t.add_row(
            Text(seg, style=f"bold {color}"),
            str(n),
            f"{pct:.1f}%",
            accion,
        )

    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['lista']} RFM — SEGMENTACIÓN DE LEADS ", f"bold {C['primary']}")
    ), border_style=C["primary"]))

    # Por campaña si existe
    if col_camp:
        t2 = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
                   header_style=f"bold {C['accent']}", padding=(0, 1))
        t2.add_column("CAMPAÑA",   style=C["white"],   min_width=22)
        t2.add_column("CAMPEÓN",   justify="right",    width=9)
        t2.add_column("POTENCIAL", justify="right",    width=10)
        t2.add_column("EN RIESGO", justify="right",    width=10)
        t2.add_column("FRÍO",      justify="right",    width=8)

        for camp, grp in df2.groupby(col_camp):
            sc = grp["_segmento"].value_counts() if hasattr(grp["_segmento"], "value_calls") else grp["_segmento"].value_counts()
            t2.add_row(
                str(camp),
                Text(str(sc.get("Campeón",   0)), style=C["success"]),
                Text(str(sc.get("Potencial", 0)), style=C["primary"]),
                Text(str(sc.get("En riesgo", 0)), style=C["warning"]),
                Text(str(sc.get("Frío",      0)), style=C["dim"]),
            )
        console.print(Panel(t2, title=Text.assemble(
            (f" {ICON['tabla']} RFM POR CAMPAÑA ", f"bold {C['accent']}")
        ), border_style=C["accent"]))

    console.print(
        f"  [{C['dim']}]R=Recency (días desde entrada) · M=Monetary (valor generado)[/{C['dim']}]\n"
    )

    # Contexto para el engine
    conteos = df2["_segmento"].value_counts().to_dict()
    total_rfm = len(df2)
    partes_rfm = [f"{seg}={n} ({n/total_rfm:.0%})" for seg, n in conteos.items()]
    return f"RFM segmentación: {', '.join(partes_rfm)}. Total: {total_rfm} leads."


# ── /embudo ──────────────────────────────────────────────────────────────────

def cmd_embudo(df, col_campana: str = "") -> str | None:
    """
    /embudo [campaña] — análisis de cuello de botella del funnel.

    Detecta automáticamente las etapas del embudo por valores en col_estado.
    Calcula conversión entre etapas y pérdida en pesos en cada paso.
    Sin campaña: vista global. Con campaña: drill-down específico.
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return

    cols = _cols_modelo(df)
    if not cols["estado"]:
        _aviso_cols_faltantes(["estado"])
        return

    col_estado = cols["estado"]
    col_camp   = cols["campana"]
    col_costo  = cols["costo"]

    # Filtrar por campaña si se especifica
    df2 = df.copy()
    if col_campana and col_camp:
        matches = df2[col_camp].astype(str).str.lower().str.contains(col_campana.lower())
        df2 = df2[matches]
        if df2.empty:
            console.print(f"  [{C['warning']}]Campaña '{col_campana}' no encontrada.[/{C['warning']}]\n")
            return

    # Normalizar estados via ValueMapper — case + sinónimos + LLM fallback
    from src.processing.value_mapper import ValueMapper
    vm = ValueMapper()
    df2, no_reconocidos = vm.normalizar_estados(df2, col_estado)

    if no_reconocidos:
        vals_str = ", ".join(f"'{v}' ({c})" for v, c in no_reconocidos)
        console.print(
            f"  [{C['warning']}]{ICON['warn']} Estados no reconocidos excluidos: {vals_str}[/{C['warning']}]"
        )

    df2 = df2[df2[col_estado].notna()]

    if df2.empty:
        console.print(f"  [{C['warning']}]No hay registros con estados válidos.[/{C['warning']}]\n")
        return

    # Ordenar etapas del embudo por frecuencia descendente
    # (heurística: las etapas más tempranas tienen más leads)
    etapas_orden = df2[col_estado].value_counts().index.tolist()

    total = len(df2)
    cpl_global = df2[col_costo].mean() if col_costo else None

    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['primary']}", padding=(0, 1))
    t.add_column("ETAPA",       style=C["white"],   min_width=18)
    t.add_column("LEADS",       justify="right",    width=8)
    t.add_column("% DEL TOTAL", justify="right",    width=11)
    t.add_column("CONV ETAPA",  justify="right",    width=11)
    t.add_column("PÉRDIDA",     justify="right",    width=12)

    prev_n = None
    for etapa in etapas_orden:
        n = int((df2[col_estado] == etapa).sum())
        pct_total = n / total * 100
        conv_etapa = n / prev_n * 100 if prev_n else 100.0
        perdida_n  = (prev_n - n) if prev_n else 0
        perdida_usd = perdida_n * cpl_global if cpl_global and prev_n else None

        if prev_n is None:
            conv_txt = Text("entrada", style=C["dim"])
            perd_txt = Text("—", style=C["dim"])
        else:
            conv_color = C["success"] if conv_etapa >= 60 else C["warning"] if conv_etapa >= 30 else C["error"]
            conv_txt = Text(f"{conv_etapa:.1f}%", style=f"bold {conv_color}")
            perd_str = f"${perdida_usd:,.0f}" if perdida_usd else f"{perdida_n} leads"
            perd_color = C["error"] if (perdida_usd or perdida_n) and conv_etapa < 30 else C["warning"]
            perd_txt = Text(perd_str, style=perd_color)

        t.add_row(str(etapa), str(n), f"{pct_total:.1f}%", conv_txt, perd_txt)
        prev_n = n

    titulo_extra = f" — {col_campana}" if col_campana else ""
    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['arrow']} EMBUDO DE CONVERSIÓN{titulo_extra} ", f"bold {C['primary']}")
    ), border_style=C["primary"]))

    # Cuello de botella — etapa con mayor pérdida relativa
    console.print(
        f"  [{C['dim']}]Tip: /embudo [nombre_campaña] para drill-down por campaña[/{C['dim']}]\n"
    )

    # Contexto para el engine
    etapas_ctx = []
    prev_n2 = None
    for etapa in etapas_orden:
        n2 = int((df2[col_estado] == etapa).sum())
        conv = f"{n2/prev_n2:.0%}" if prev_n2 else "entrada"
        etapas_ctx.append(f"{etapa}={n2} (conv {conv})")
        prev_n2 = n2
    titulo_ctx = f" campaña {col_campana}" if col_campana else ""
    return f"Embudo{titulo_ctx}: {' → '.join(etapas_ctx)}."


# ── /velocidad ───────────────────────────────────────────────────────────────

def cmd_velocidad(df) -> None:
    """
    /velocidad — tiempo promedio de conversión lead → venta por campaña.

    Usa fecha_entrada y fecha_cierre.
    Detecta campañas con ciclos de venta más cortos (más eficientes).
    """
    if df is None or df.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return

    cols = _cols_modelo(df)
    faltantes = [k for k in ["fecha_entrada", "fecha_cierre", "estado"] if not cols[k]]
    if faltantes:
        _aviso_cols_faltantes(faltantes)
        return

    col_entrada = cols["fecha_entrada"]
    col_cierre  = cols["fecha_cierre"]
    col_estado  = cols["estado"]
    col_camp    = cols["campana"]

    estados_venta = _estados_venta(df, col_estado)
    if not estados_venta:
        console.print(f"  [{C['warning']}]No se detectaron ventas en '{col_estado}'.[/{C['warning']}]\n")
        return

    df2 = df.copy()
    try:
        df2[col_entrada] = pd.to_datetime(df2[col_entrada], errors="coerce")
        df2[col_cierre]  = pd.to_datetime(df2[col_cierre],  errors="coerce")
    except Exception as e:
        console.print(f"  [{C['error']}]Error parseando fechas: {e}[/{C['error']}]\n")
        return

    df_ventas = df2[df2[col_estado].isin(estados_venta)].copy()
    df_ventas["_dias"] = (df_ventas[col_cierre] - df_ventas[col_entrada]).dt.days
    df_ventas = df_ventas[df_ventas["_dias"] >= 0]  # excluir fechas inválidas

    if df_ventas.empty:
        console.print(f"  [{C['warning']}]Sin ventas con fechas válidas para calcular velocidad.[/{C['warning']}]\n")
        return

    global_avg = df_ventas["_dias"].mean()

    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['accent']}", padding=(0, 1))
    t.add_column("CAMPAÑA",    style=C["white"],  min_width=22)
    t.add_column("VENTAS",     justify="right",   width=8)
    t.add_column("DÍAS PROM",  justify="right",   width=10)
    t.add_column("DÍAS MED",   justify="right",   width=10)
    t.add_column("MÁS RÁPIDA", justify="right",   width=11)
    t.add_column("VS GLOBAL",  justify="right",   width=12)

    if col_camp:
        grupos = df_ventas.groupby(col_camp)
    else:
        grupos = [("(todas)", df_ventas)]

    for camp, grp in grupos:
        n    = len(grp)
        avg  = grp["_dias"].mean()
        med  = grp["_dias"].median()
        minv = grp["_dias"].min()
        diff = avg - global_avg
        color = C["success"] if diff <= -2 else C["warning"] if diff <= 5 else C["error"]
        diff_txt = f"{diff:+.0f}d" if abs(diff) >= 1 else "≈ global"
        t.add_row(
            str(camp),
            str(n),
            Text(f"{avg:.0f}d", style=f"bold {color}"),
            f"{med:.0f}d",
            f"{minv:.0f}d",
            Text(diff_txt, style=color),
        )

    console.print(Panel(t, title=Text.assemble(
        (f" {ICON['info']} VELOCIDAD DE VENTA — días lead→cierre ", f"bold {C['accent']}")
    ), border_style=C["accent"]))
    console.print(
        f"  [{C['dim']}]Global promedio: {global_avg:.0f} días · "
        f"[{C['success']}]verde = más rápido que promedio[/{C['success']}] · "
        f"[{C['error']}]rojo = más lento[/{C['error']}][/{C['dim']}]\n"
    )
