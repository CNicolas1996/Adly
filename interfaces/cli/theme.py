# theme.py — Adly · Data-Buddy
# Fuente única de verdad para colores, iconos y helpers visuales
# Blade Runner: azul eléctrico + naranja neón sobre negro

from rich.console import Console
from rich.text import Text

# ─────────────────────────────────────────
# CONSOLA GLOBAL
# ─────────────────────────────────────────
console = Console()
VERSION = "v0.2.0"

# ─────────────────────────────────────────
# PALETA
# ─────────────────────────────────────────
C = {
    "primary": "color(39)",    # azul eléctrico
    "accent":  "color(208)",   # naranja neón
    "success": "color(82)",    # verde
    "warning": "color(214)",   # ámbar
    "error":   "color(196)",   # rojo
    "dim":     "color(240)",   # gris oscuro
    "white":   "color(255)",   # blanco
    "muted":   "color(244)",   # gris medio
    "cyan":    "color(51)",    # cian brillante
}

# ─────────────────────────────────────────
# ICONOS UNICODE
# ─────────────────────────────────────────
ICON = {
    "ok":      "✓",
    "warn":    "⚠",
    "crit":    "⚡",
    "info":    "◈",
    "arrow":   "→",
    "bullet":  "◆",
    "adly":    "▸",
    "sep":     "─",
    "tabla":   "⊞",
    "lista":   "≡",
    "debug":   "⌗",
}

# ─────────────────────────────────────────
# MAPA SEVERIDAD → (color, label, icono)
# ─────────────────────────────────────────
SEV = {
    "info":     (C["primary"], "INFO", ICON["info"]),
    "warning":  (C["warning"], "WARN", ICON["warn"]),
    "critical": (C["error"],   "CRIT", ICON["crit"]),
}

# ─────────────────────────────────────────
# BARRA DE CONFIANZA VISUAL
# ─────────────────────────────────────────
def barra_confianza(valor: float, ancho: int = 10) -> Text:
    """
    Genera una barra visual de confianza estilo terminal.
    valor: 0.0 - 1.0
    Retorna Rich Text con colores.

    Ejemplo: ████████░░  80%
    """
    llenas = round(valor * ancho)
    vacias = ancho - llenas

    if valor >= 0.75:
        color = C["success"]
    elif valor >= 0.5:
        color = C["warning"]
    else:
        color = C["error"]

    pct_color = color
    t = Text()
    t.append("█" * llenas, style=f"bold {color}")
    t.append("░" * vacias, style=C["dim"])
    t.append(f"  {valor:.0%}", style=f"bold {pct_color}")
    return t


# ─────────────────────────────────────────
# SEPARADOR DE TURNO CON TIMESTAMP
# ─────────────────────────────────────────
def separador_turno() -> None:
    """Línea dim con timestamp entre respuestas."""
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    console.print(
        f"\n  [{C['dim']}]{ICON['sep'] * 3}  {ts}  {ICON['sep'] * 3}[/{C['dim']}]\n"
    )
