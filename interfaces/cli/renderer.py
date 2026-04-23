# renderer.py — Adly · Data-Buddy
# Renderizado de respuestas del engine — v2
# Soporta: texto | tabla | lista | debug
# Usa theme.py como fuente única de estilos

from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box

from interfaces.cli.theme import console, C, ICON, SEV, barra_confianza, separador_turno


# ─────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────

def renderizar_respuesta(respuesta) -> None:
    """
    Detecta respuesta.tipo y renderiza con Rich.

    Tipos soportados:
      texto  → Panel con prosa
      tabla  → Rich Table con columnas + datos
      lista  → Items numerados desde datos[]
      debug  → Panel monospace gris
    """
    color, label, icono = SEV.get(respuesta.severidad, (C["primary"], "INFO", ICON["info"]))
    tipo = getattr(respuesta, "tipo", "texto")

    # Título del card: badge severidad + barra confianza
    titulo = Text.assemble(
        (f" {icono} {label} ", f"bold reverse {color}"),
        ("  ", ""),
    )
    titulo.append_text(barra_confianza(respuesta.confianza))

    # ── TABLA ───────────────────────────────────────────────────
    if tipo == "tabla" and getattr(respuesta, "columnas", []) and getattr(respuesta, "datos", []):
        _renderizar_tabla(respuesta, color, titulo)

    # ── LISTA ───────────────────────────────────────────────────
    elif tipo == "lista" and getattr(respuesta, "datos", []):
        _renderizar_lista(respuesta, color, titulo)

    # ── DEBUG ───────────────────────────────────────────────────
    elif tipo == "debug":
        console.print(Panel(
            Text(respuesta.respuesta, style=f"bold {C['muted']}"),
            title=Text.assemble((f" {ICON['debug']} DEBUG ", f"bold reverse {C['dim']}")),
            border_style=C["dim"],
            padding=(1, 2),
        ))

    # ── TEXTO (default) ─────────────────────────────────────────
    else:
        _renderizar_texto(respuesta, color, titulo)

# Acción inline al pie — siempre visible si existe
    if respuesta.accion:
        console.print(
            Text.assemble(
                (f"  {ICON['arrow']} ", f"bold {C['accent']}"),
                (respuesta.accion, C["white"]),
            )
        )

    # Footer de integridad — solo en respuestas de análisis, no en saludos
    freshness_raw = getattr(respuesta, "data_freshness", "")
    conf_note     = getattr(respuesta, "confidence_note", "")
    es_analisis   = getattr(respuesta, "confianza", 0) > 0.0

    if (freshness_raw or conf_note) and es_analisis:
        # Parsear texto y nivel — formato "texto|nivel" desde engine
        if "|" in freshness_raw:
            freshness_texto, freshness_nivel = freshness_raw.rsplit("|", 1)
        else:
            freshness_texto, freshness_nivel = freshness_raw, "ok"

        # Color según nivel de antigüedad del dato
        FRESHNESS_COLOR = {
            "ok":       C["dim"],
            "warning":  C["warning"],
            "critical": C["error"],
        }
        freshness_color = FRESHNESS_COLOR.get(freshness_nivel, C["dim"])

        partes = []
        if freshness_texto:
            partes.append((f"  ⏱ {freshness_texto}", freshness_color))
        if freshness_texto and conf_note:
            partes.append(("  ·  ", C["dim"]))
        if conf_note:
            partes.append((f"⚑ {conf_note}", C["dim"]))
        console.print(Text.assemble(*partes))

    console.print()



# ─────────────────────────────────────────
# RENDERIZADORES ESPECÍFICOS
# ─────────────────────────────────────────

def _renderizar_texto(respuesta, color: str, titulo: Text) -> None:
    """Respuesta en prosa — Panel con borde de severidad."""
    console.print(Panel(
        Text(f"  {respuesta.respuesta}", style=C["white"]),
        title=titulo,
        border_style=color,
        padding=(1, 2),
    ))


def _renderizar_tabla(respuesta, color: str, titulo: Text) -> None:
    """Respuesta tipo tabla — intro + Rich Table."""
    # Intro si existe
    if respuesta.respuesta and respuesta.respuesta != "Datos extraídos automáticamente":
        console.print(Panel(
            Text(f"  {respuesta.respuesta}", style=C["white"]),
            title=titulo,
            border_style=color,
            padding=(0, 2),
        ))
        subtitulo = Text.assemble(
            (f" {ICON['tabla']} TABLA ", f"bold {color}"),
            (f"({len(respuesta.datos)} filas)", C["dim"]),
        )
    else:
        subtitulo = titulo

    t = Table(
        box=box.SIMPLE_HEAD,
        border_style=color,
        header_style=f"bold {color}",
        padding=(0, 1),
        show_lines=False,
    )

    for col in respuesta.columnas:
        es_num = _es_columna_numerica(col, respuesta.datos)
        t.add_column(
            str(col).upper(),
            style=C["muted"],
            justify="right" if es_num else "left",
        )

    for fila in respuesta.datos:
        celdas = []
        for col in respuesta.columnas:
            val = str(fila.get(col, "—"))
            celdas.append(val)
        t.add_row(*celdas)

    console.print(Panel(
        t,
        title=subtitulo,
        border_style=color,
        padding=(0, 1),
    ))


def _renderizar_lista(respuesta, color: str, titulo: Text) -> None:
    """
    Respuesta tipo lista — items numerados desde datos[].
    Cada item es {"item": "texto"} — numerados con color de severidad.
    """
    # Intro si existe
    intro = respuesta.respuesta
    if intro and intro != "Lista detectada automáticamente":
        console.print(Panel(
            Text(f"  {intro}", style=C["white"]),
            title=titulo,
            border_style=color,
            padding=(0, 2),
        ))
        subtitulo = Text.assemble(
            (f" {ICON['lista']} LISTA ", f"bold {color}"),
        )
    else:
        subtitulo = titulo

    # Construir contenido de la lista
    contenido = Text()
    items = respuesta.datos

    for i, fila in enumerate(items, 1):
        # Soporta {"item": "texto"} o dict con cualquier clave como primera columna
        if "item" in fila:
            texto = fila["item"]
        else:
            texto = " · ".join(str(v) for v in fila.values())

        contenido.append(f"\n  {i}. ", style=f"bold {color}")
        contenido.append(texto, style=C["white"])

    contenido.append("\n")

    console.print(Panel(
        contenido,
        title=subtitulo,
        border_style=color,
        padding=(0, 2),
    ))


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _es_columna_numerica(col: str, datos: list) -> bool:
    """Heurística — si los primeros valores parecen numéricos, alinear derecha."""
    for fila in datos[:3]:
        v = str(fila.get(col, "")).strip().replace("$", "").replace(",", "").replace("%", "")
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False
