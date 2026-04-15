# cli.py — Adly · Data-Buddy
# Terminal User Interface — MVP
# Estética: Blade Runner — azul eléctrico + naranja sobre negro
# Rich + logo geométrico neón + onboarding + comandos + conversación

import os
import sys
import time
import csv
import webbrowser
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv, set_key

def limpiar_pantalla() -> None:
    """Limpia la terminal — compatible con Windows y Unix."""
    os.system('cls' if os.name == 'nt' else 'clear')

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.prompt import Prompt
    from rich.align import Align
    from rich.rule import Rule
    from rich import box
except ImportError:
    print("[ERROR] Instala dependencias: pip install rich python-dotenv")
    sys.exit(1)

console  = Console()
VERSION  = "v0.1.0-mvp"
ENV_PATH = Path(".env")

# ─────────────────────────────────────────
# PALETA — BLADE RUNNER
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
}

# ─────────────────────────────────────────
# LOGO GEOMÉTRICO — BLADE RUNNER NEÓN
# ─────────────────────────────────────────

LOGO = [
    ("  ██████╗  ██████╗   ██╗      ██╗   ██╗ ", "color(27)"),
    (" ██╔═══██╗ ██╔══██╗  ██║      ╚██╗ ██╔╝ ", "color(33)"),
    (" ███████║  ██║  ██║  ██║       ╚████╔╝  ", "color(39)"),
    (" ██╔══  ║  ██║  ██║  ██║        ╚██╔╝   ", "color(45)"),
    (" ██║  ██║  ██████╔╝  ███████╗   ██║     ", "color(51)"),
    (" ╚═╝  ╚═╝  ╚═════╝   ╚══════╝   ╚═╝     ", "color(255)"),
]

def mostrar_logo() -> None:
    console.print()
    for linea, color in LOGO:
        console.print(Align.center(Text(linea, style=f"bold {color}")))
    console.print()

# ─────────────────────────────────────────
# BOOT SCREEN
# ─────────────────────────────────────────

def boot_screen() -> None:
    limpiar_pantalla()
    mostrar_logo()

    console.print(Align.center(Text(
        "El analista de pauta que tu agencia necesita pero no tiene.",
        style=f"italic {C['muted']}"
    )))
    console.print(Align.center(Text(
        f"━━━  {VERSION}  ·  Data-Buddy  ·  2026  ━━━",
        style=f"bold {C['accent']}"
    )))
    console.print()
    console.rule(style=C["dim"])
    console.print()

    boot_seq = [
        ("SYS", "Iniciando núcleo de análisis...",    C["dim"]),
        ("MEM", "Cargando modelos de métricas...",    C["dim"]),
        ("NET", "Verificando proveedores LLM...",     C["dim"]),
        ("DAT", "Preparando pipeline de datos...",    C["dim"]),
        ("SEC", "Validando credenciales...",          C["dim"]),
        ("OK ", "Sistema listo.",                     C["success"]),
    ]
    for tag, msg, color in boot_seq:
        time.sleep(0.28)
        console.print(Text.assemble(
            (f"  {tag}  ", f"bold {C['primary']}"),
            (msg,          color),
        ))

    console.print()
    time.sleep(0.8)
    limpiar_pantalla()

# ─────────────────────────────────────────
# PROVEEDORES LLM — completos
# ─────────────────────────────────────────

PROVEEDORES_LLM = {
    "1":  ("ollama",      "Ollama          — local, gratis, sin internet"),
    "2":  ("gemini",      "Google Gemini   — gratis con límites generosos"),
    "3":  ("deepseek",    "DeepSeek        — muy bueno, muy económico"),
    "4":  ("openai",      "OpenAI          — GPT-4o y familia"),
    "5":  ("groq",        "Groq            — ultra rápido, gratis"),
    "6":  ("claude",      "Anthropic Claude— máxima calidad"),
    "7":  ("mistral",     "Mistral AI      — buena relación costo/calidad"),
    "8":  ("together",    "Together AI     — 50+ modelos open source"),
    "9":  ("perplexity",  "Perplexity      — con búsqueda web integrada"),
    "10": ("cohere",      "Cohere          — especializado en RAG"),
    "11": ("huggingface", "HuggingFace     — miles de modelos"),
}

FUENTES_DATOS = {
    "1": ("mock",   "Mock data    — datos de prueba  <- empieza aqui"),
    "2": ("sheets", "Google Sheets— Sheet real"),
    "3": ("meta",   "Meta + GHL  — conexion directa APIs"),
}

MODELOS_DEFAULT = {
    "gemini":      "gemini-2.0-flash",
    "deepseek":    "deepseek-chat",
    "openai":      "gpt-4o-mini",
    "groq":        "llama-3.3-70b-versatile",
    "claude":      "claude-opus-4-6",
    "mistral":     "mistral-small-latest",
    "together":    "meta-llama/Llama-3-70b-chat-hf",
    "perplexity":  "llama-3.1-sonar-small-128k-online",
    "cohere":      "command-r-plus",
    "huggingface": "HuggingFaceH4/zephyr-7b-beta",
    "ollama":      "qwen2.5-coder:7b",
}

BASE_URLS = {
    "openai":      "https://api.openai.com/v1",
    "deepseek":    "https://api.deepseek.com",
    "groq":        "https://api.groq.com/openai/v1",
    "claude":      "https://api.anthropic.com/v1",
    "mistral":     "https://api.mistral.ai/v1",
    "together":    "https://api.together.xyz/v1",
    "perplexity":  "https://api.perplexity.ai",
    "cohere":      "https://api.cohere.com/v1",
    "huggingface": "https://api-inference.huggingface.co/v1",
    "gemini":      "",
    "ollama":      "http://localhost:11434",
}

# ─────────────────────────────────────────
# ONBOARDING
# ─────────────────────────────────────────

def onboarding() -> dict:
    limpiar_pantalla()
    mostrar_logo()

    console.print(Panel(
        Text.assemble(
            ("\n  Bienvenido a Adly\n\n",          f"bold {C['primary']}"),
            ("  Configuración inicial en ",        C["muted"]),
            ("4 pasos.\n\n",                       f"bold {C['accent']}"),
            ("  Credenciales guardadas en .env\n", C["dim"]),
            ("  Solo en tu máquina.\n",            C["dim"]),
        ),
        border_style=C["primary"],
        padding=(0, 2),
    ))
    console.print()

    config = {}

    # PASO 1 — Nombre
    limpiar_pantalla()
    mostrar_logo()
    console.print(Panel(
        Text.assemble(
            (f"  PASO 1 de 4  ", f"bold reverse {C['accent']}"),
            ("  ¿Cómo te llamas?\n\n", f"bold {C['white']}"),
            ("  El nombre que Adly usará para saludarte.", C["dim"]),
        ),
        border_style=C["primary"],
        padding=(0, 2),
    ))
    console.print()
    config["nombre"] = Prompt.ask(f"  [{C['accent']}]Nombre[/{C['accent']}]")
    console.print()

    # PASO 2 — LLM
    limpiar_pantalla()
    mostrar_logo()
    console.print(Panel(
        Text.assemble(
            (f"  PASO 2 de 4  ", f"bold reverse {C['accent']}"),
            ("  ¿Qué proveedor LLM usas?\n\n", f"bold {C['white']}"),
            ("  Puedes cambiarlo después editando .env", C["dim"]),
        ),
        border_style=C["primary"],
        padding=(0, 2),
    ))
    console.print()
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style=f"bold {C['primary']}", width=5)
    t.add_column(style=C["muted"])
    for k, (_, desc) in PROVEEDORES_LLM.items():
        t.add_row(k, desc)
    console.print(t)
    console.print()
    llm_key = Prompt.ask(
        f"  [{C['accent']}]Número[/{C['accent']}]",
        choices=list(PROVEEDORES_LLM.keys()),
        default="1",
    )
    config["llm_provider"] = PROVEEDORES_LLM[llm_key][0]
    console.print()

    # PASO 3 — Credenciales
    limpiar_pantalla()
    mostrar_logo()
    console.print(Panel(
        Text.assemble(
            (f"  PASO 3 de 4  ", f"bold reverse {C['accent']}"),
            (f"  Credenciales — {config['llm_provider'].upper()}\n\n", f"bold {C['white']}"),
            ("  Se guardan en .env y nunca salen de tu máquina.", C["dim"]),
        ),
        border_style=C["primary"],
        padding=(0, 2),
    ))
    console.print()
    if config["llm_provider"] == "ollama":
        console.print(f"  [{C['success']}]✓  Ollama no requiere API Key[/{C['success']}]")
        console.print()
        config["llm_api_key"]  = ""
        config["llm_base_url"] = Prompt.ask(
            f"  [{C['accent']}]URL Ollama[/{C['accent']}]",
            default="http://localhost:11434",
        )
        console.print()
        config["llm_model"] = Prompt.ask(
            f"  [{C['accent']}]Modelo[/{C['accent']}]",
            default="qwen2.5-coder:7b",
        )
    else:
        console.print(f"  [{C['dim']}]La API Key no se mostrará mientras escribes.[/{C['dim']}]")
        console.print()
        config["llm_api_key"]  = Prompt.ask(
            f"  [{C['accent']}]API Key[/{C['accent']}]",
            password=True,
        )
        console.print()
        config["llm_model"] = Prompt.ask(
            f"  [{C['accent']}]Modelo[/{C['accent']}]",
            default=MODELOS_DEFAULT.get(config["llm_provider"], ""),
        )
        config["llm_base_url"] = BASE_URLS.get(config["llm_provider"], "")
    console.print()

    # PASO 4 — Fuente
    limpiar_pantalla()
    mostrar_logo()
    console.print(Panel(
        Text.assemble(
            (f"  PASO 4 de 4  ", f"bold reverse {C['accent']}"),
            ("  ¿Qué fuente de datos usas?\n\n", f"bold {C['white']}"),
            ("  Puedes empezar con Mock y conectar datos reales después.", C["dim"]),
        ),
        border_style=C["primary"],
        padding=(0, 2),
    ))
    console.print()
    t2 = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t2.add_column(style=f"bold {C['primary']}", width=5)
    t2.add_column(style=C["muted"])
    for k, (_, desc) in FUENTES_DATOS.items():
        t2.add_row(k, desc)
    console.print(t2)
    console.print()
    fuente_key = Prompt.ask(
        f"  [{C['accent']}]Número[/{C['accent']}]",
        choices=list(FUENTES_DATOS.keys()),
        default="1",
    )
    config["fuente"] = FUENTES_DATOS[fuente_key][0]
    console.print()

    if config["fuente"] == "sheets":
        config["sheet_id"] = Prompt.ask(f"  [{C['accent']}]Google Sheet ID[/{C['accent']}]")
        config["mock_csv"]  = ""
    elif config["fuente"] == "meta":
        config["meta_token"]  = Prompt.ask(f"  [{C['accent']}]Meta Access Token[/{C['accent']}]", password=True)
        config["ghl_api_key"] = Prompt.ask(f"  [{C['accent']}]GHL API Key[/{C['accent']}]",       password=True)
        config["mock_csv"]    = ""
    else:
        config["sheet_id"] = ""
        console.print(f"  [{C['dim']}]CSV de prueba (Enter para usar datos generados):[/{C['dim']}]")
        mock_csv = Prompt.ask(
            f"  [{C['accent']}]Ruta CSV[/{C['accent']}]",
            default="",
        )
        config["mock_csv"] = mock_csv

    _guardar_env(config)

    console.print()
    console.print(Panel(
        Text.assemble(
            ("\n  ✓  Configurado para ",            C["success"]),
            (config["nombre"],                      f"bold {C['accent']}"),
            ("\n  ✓  LLM:    ",                     C["success"]),
            (config["llm_provider"],                f"bold {C['white']}"),
            (f"  ({config.get('llm_model','')})",   C["dim"]),
            ("\n  ✓  Fuente: ",                     C["success"]),
            (config["fuente"],                      f"bold {C['white']}"),
            ("\n\n  Arrancando Adly...\n",           C["dim"]),
        ),
        border_style=C["success"],
        padding=(0, 2),
    ))
    time.sleep(1.2)
    return config


def _guardar_env(config: dict) -> None:
    ENV_PATH.touch(exist_ok=True)
    for k, v in {
        "ADLY_CLIENTE_NOMBRE": config.get("nombre", ""),
        "ADLY_LLM_PROVIDER":   config.get("llm_provider", "ollama"),
        "ADLY_LLM_API_KEY":    config.get("llm_api_key", ""),
        "ADLY_LLM_MODEL":      config.get("llm_model", ""),
        "ADLY_LLM_BASE_URL":   config.get("llm_base_url", ""),
        "ADLY_LLM_FALLBACK":   "ollama,gemini,groq",
        "ADLY_FUENTE":         config.get("fuente", "mock"),
        "ADLY_MOCK_CSV":       config.get("mock_csv", ""),
        "GOOGLE_SHEET_ID":     config.get("sheet_id", ""),
        "META_ACCESS_TOKEN":   config.get("meta_token", ""),
        "GHL_API_KEY":         config.get("ghl_api_key", ""),
    }.items():
        set_key(str(ENV_PATH), k, v)


def cargar_config() -> dict:
    load_dotenv()
    return {
        "nombre":       os.getenv("ADLY_CLIENTE_NOMBRE", "Usuario"),
        "llm_provider": os.getenv("ADLY_LLM_PROVIDER",  "ollama"),
        "llm_model":    os.getenv("ADLY_LLM_MODEL",     ""),
        "fuente":       os.getenv("ADLY_FUENTE",         "mock"),
        "mock_csv":     os.getenv("ADLY_MOCK_CSV",       ""),
    }


def necesita_onboarding() -> bool:
    if not ENV_PATH.exists():
        return True
    load_dotenv()
    return not os.getenv("ADLY_CLIENTE_NOMBRE")

# ─────────────────────────────────────────
# CARGA DE DATOS
# ─────────────────────────────────────────

def cargar_datos(fuente: str, mock_csv: str = ""):
    sys.path.insert(0, ".")
    from src.ingestion.mock_data import generar_datos_ghl, generar_datos_sheet
    from src.processing.validation import DataValidator
    from src.processing.alerts import AlertManager
    from src.processing.metrics import MetricsCalculator, CONFIG_DEFAULT

    with console.status(
        f"  [{C['primary']}]Cargando [{fuente.upper()}]...[/{C['primary']}]",
        spinner="dots2",
    ):
        time.sleep(0.6)
        config_cols = CONFIG_DEFAULT  # se sobreescribe si el conector infiere columnas

        if fuente == "mock":
            if not mock_csv:
                mock_csv = os.getenv("ADLY_MOCK_CSV", "")
            if mock_csv:
                from src.ingestion.sheets import MockConnector
                conn        = MockConnector(csv_path=mock_csv)
                df_ghl      = conn.leer()
                df_sheet    = df_ghl
                config_cols = conn.schema
            else:
                df_ghl   = generar_datos_ghl(n_leads=100)
                df_sheet = generar_datos_sheet(df_ghl)
        elif fuente == "sheets":
            from src.ingestion.sheets import SheetsConnector
            conn     = SheetsConnector()
            df_sheet = conn.leer()
            df_ghl   = df_sheet
            config_cols = conn.schema
        else:
            df_ghl = df_sheet = generar_datos_ghl(n_leads=100)

        validator  = DataValidator()
        resultado  = validator.validar(df_ghl, df_sheet)
        calc       = MetricsCalculator(config=config_cols)
        metricas   = calc.calcular(df_ghl, nivel="campana")
        resumen_llm = calc.resumen_para_llm(metricas, nivel="campana")
        schema_llm  = calc.resumen_schema(df_ghl)  # v2 — schema del raw
        manager    = AlertManager(resultado, metricas, config_cols)

    return df_ghl, df_sheet, metricas, resumen_llm, schema_llm, resultado, manager, validator, calc


# ─────────────────────────────────────────
# ESTADO INICIAL
# ─────────────────────────────────────────

def mostrar_estado_inicial(config, resultado, manager) -> None:
    n_crit = sum(1 for a in manager.alertas if a.nivel.value == "critica")
    n_warn = sum(1 for a in manager.alertas if a.nivel.value == "advertencia")
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style=C["dim"],   width=14)
    t.add_column(style=C["white"])
    t.add_row("Usuario", Text(config["nombre"],       style=f"bold {C['accent']}"))
    t.add_row("LLM",     Text(config["llm_provider"], style=f"bold {C['primary']}"))
    t.add_row("Fuente",  Text(config["fuente"],       style=C["muted"]))
    t.add_row("Score",   Text(
        f"{resultado.score:.1f}%",
        style=f"bold {C['success'] if resultado.score>=90 else C['warning'] if resultado.score>=70 else C['error']}"
    ))
    t.add_row("Alertas", Text(
        f"{'[CRIT] '+str(n_crit)+' criticas   ' if n_crit else ''}"
        f"{'[WARN] '+str(n_warn)+' advertencias' if n_warn else ''}"
        f"{'[OK] Todo en orden' if not n_crit and not n_warn else ''}",
        style=C["white"]
    ))
    console.print(Panel(t, title=f"[{C['dim']}] ESTADO [/{C['dim']}]", border_style=C["dim"]))
    console.print()

    if manager.tiene_criticas():
        for a in manager.alertas:
            if a.nivel.value == "critica":
                console.print(f"  [{C['error']}][CRIT][/{C['error']}]  {a.mensaje}")
                console.print(f"  [{C['dim']}]  -> {a.recomendacion}[/{C['dim']}]")
        console.print()

    console.print(
        f"  [{C['dim']}]Escribe tu pregunta o [/{C['dim']}]"
        f"[{C['accent']}]/ayuda[/{C['accent']}]"
        f"[{C['dim']}] para ver comandos.[/{C['dim']}]"
    )
    console.print()

# ─────────────────────────────────────────
# COMANDOS
# ─────────────────────────────────────────

def cmd_ayuda() -> None:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style=f"bold {C['accent']}", width=30)
    t.add_column(style=C["muted"])
    for cmd, desc in [
        ("/alertas",                           "Reporte de integridad de datos"),
        ("/metricas",                          "Resumen de todas las campañas"),
        ("/head [N]",                          "Primeras N filas del dataset (default: 5)"),
        ("/sample [N]",                        "N filas aleatorias (default: 5)"),
        ("/describe",                          "Estadísticas numéricas del dataset activo"),
        ("/exportar",                          "Guarda el dataset activo como CSV"),
        ("/refresh",                           "Recargar datos desde la fuente"),
        ("/limpiar",                           "Nueva conversación"),
        ("/estado",                            "Estado del engine y LLM"),
        ("/guardar",                           "Exportar conversación a CSV"),
        ("/dashboard",                         "Generar dashboard HTML"),
        ("/limpiar_duplicados",                "Eliminar filas duplicadas del dataset"),
        ("/rellenar [columna] [estrategia]",   "Rellenar nulos — estrategias: media|mediana|moda|valor"),
        ("/eliminar_por [col] [op] [valor]",   "Filtrar filas — ops: == != > < >= <= isnull notnull"),
        ("/ayuda",                             "Esta pantalla"),
        ("salir",                              "Cerrar Adly"),
    ]:
        t.add_row(cmd, desc)
    console.print(Panel(t, title=f"[{C['accent']}] COMANDOS [/{C['accent']}]", border_style=C["accent"]))
    console.print()


def cmd_alertas(manager) -> None:
    if not manager.alertas:
        console.print(f"  [{C['success']}][OK]  Datos en buen estado.[/{C['success']}]\n")
        return
    for a in manager.alertas:
        color = C["error"] if a.nivel.value=="critica" else C["warning"] if a.nivel.value=="advertencia" else C["success"]
        icono = "[CRIT]" if a.nivel.value=="critica" else "[WARN]" if a.nivel.value=="advertencia" else "[OK] "
        console.print(f"  [{color}]{icono}  {a.nivel.value.upper()}[/{color}]  {a.mensaje}")
        console.print(f"  [{C['dim']}]  -> {a.recomendacion}[/{C['dim']}]")
        if a.ids_afectados:
            m = a.ids_afectados[:3]
            e = len(a.ids_afectados) - 3
            console.print(f"  [{C['dim']}]  IDs: {m}{' y '+str(e)+' mas' if e>0 else ''}[/{C['dim']}]")
        console.print()


def cmd_metricas(metricas, col: str = "campana") -> None:
    if metricas is None or metricas.empty:
        console.print(f"  [{C['warning']}]Sin métricas. Usa /refresh.[/{C['warning']}]\n")
        return
    t = Table(box=box.SIMPLE_HEAD, border_style=C["dim"],
              header_style=f"bold {C['primary']}", padding=(0,1))
    t.add_column("CAMPAÑA",  style=C["white"],   min_width=22)
    t.add_column("LEADS",    style=C["muted"],   justify="right")
    t.add_column("MQL",      style=C["muted"],   justify="right")
    t.add_column("CPL",      style=C["accent"],  justify="right")
    t.add_column("CPMQL",    style=C["accent"],  justify="right")
    t.add_column("ROAS",     justify="right")
    t.add_column("ICL",      style=C["primary"], justify="right")
    for _, f in metricas.iterrows():
        roas = f.get("roas", 0)
        rc   = C["success"] if roas>=1 else C["warning"] if roas>=0.5 else C["error"]
        t.add_row(
            str(f.get(col,"—")),
            str(int(f.get("total_leads",0))),
            str(int(f.get("total_mql",0))),
            f"${f.get('cpl',0):,.0f}",
            f"${f.get('cpmql',0):,.0f}",
            Text(f"{roas:.2f}", style=f"bold {rc}"),
            f"{f.get('icl',0):.4f}",
        )
    console.print(Panel(t, title=f"[{C['primary']}] MÉTRICAS POR CAMPAÑA [/{C['primary']}]", border_style=C["primary"]))
    console.print()


def cmd_estado(engine, config: dict) -> None:
    mem = engine.memoria.resumen() if engine else "Engine no iniciado"
    console.print(Panel(
        Text.assemble(
            ("  Usuario  ", C["dim"]), (config["nombre"],               f"bold {C['accent']}"),  ("\n",""),
            ("  LLM      ", C["dim"]), (config["llm_provider"],         f"bold {C['white']}"),   ("\n",""),
            ("  Modelo   ", C["dim"]), (config.get("llm_model","—"),    C["muted"]),              ("\n",""),
            ("  Fuente   ", C["dim"]), (config["fuente"],               f"bold {C['white']}"),   ("\n",""),
            ("  Memoria  ", C["dim"]), (mem,                            C["muted"]),
        ),
        title=f"[{C['accent']}] ESTADO [/{C['accent']}]",
        border_style=C["accent"],
        padding=(1, 2),
    ))
    console.print()


def cmd_guardar(historial: list) -> None:
    if not historial:
        console.print(f"  [{C['warning']}]No hay conversación para guardar.[/{C['warning']}]\n")
        return
    fn = f"adly_sesion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(fn, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp","rol","mensaje","severidad","confianza"])
        for item in historial:
            w.writerow([item.get("ts",""), item.get("rol",""),
                        item.get("mensaje",""), item.get("severidad",""), item.get("confianza","")])
    console.print(f"  [{C['success']}]✓  Guardado:[/{C['success']}] [{C['primary']}]{fn}[/{C['primary']}]\n")


def cmd_dashboard(metricas, config: dict) -> None:
    if metricas is None or metricas.empty:
        console.print(f"  [{C['warning']}]Sin datos para dashboard.[/{C['warning']}]\n")
        return
    with console.status(f"  [{C['primary']}]Generando...[/{C['primary']}]", spinner="dots2"):
        time.sleep(0.7)
        col  = config.get("col_campana","campana")
        rows = ""
        for _, f in metricas.iterrows():
            roas  = f.get("roas",0)
            color = "#00e5ff" if roas>=1 else "#ff9100" if roas>=0.5 else "#ff1744"
            rows += f"<tr><td>{f.get(col,'—')}</td><td>{int(f.get('total_leads',0))}</td>" \
                    f"<td>{int(f.get('total_mql',0))}</td><td>${f.get('cpl',0):,.0f}</td>" \
                    f"<td>${f.get('cpmql',0):,.0f}</td>" \
                    f"<td style='color:{color};font-weight:700'>{roas:.2f}</td>" \
                    f"<td>{f.get('icl',0):.4f}</td></tr>"
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
<h1>▸ ADLY</h1>
<div class="sub">{datetime.now().strftime('%Y-%m-%d %H:%M')} · {config.get('nombre','—')} · {VERSION}</div>
<table><thead><tr><th>CAMPAÑA</th><th>LEADS</th><th>MQL</th><th>CPL</th><th>CPMQL</th><th>ROAS</th><th>ICL</th></tr></thead>
<tbody>{rows}</tbody></table></body></html>"""
        fn = f"adly_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(html)
    console.print(f"  [{C['success']}]✓[/{C['success']}] [{C['primary']}]{fn}[/{C['primary']}]")
    try:
        webbrowser.open(f"file://{Path(fn).resolve()}")
        console.print(f"  [{C['dim']}]Abriendo en navegador...[/{C['dim']}]\n")
    except Exception:
        console.print(f"  [{C['dim']}]Ábrelo manualmente.[/{C['dim']}]\n")

# ─────────────────────────────────────────
# COMANDOS DE EXPLORACIÓN DE DATOS
# ─────────────────────────────────────────

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
        f"  [{C['success']}]Exportado:[/{C['success']}] "
        f"[{C['primary']}]{fn}[/{C['primary']}] "
        f"[{C['dim']}]({len(df)} filas)[/{C['dim']}]\n"
    )


# ─────────────────────────────────────────
# RENDERIZAR RESPUESTA — v2
# ─────────────────────────────────────────

def renderizar_respuesta(respuesta) -> None:
    """
    v2 — detecta respuesta.tipo y renderiza accordingly:
      texto  → Panel con texto (comportamiento original)
      tabla  → Rich Table con respuesta.columnas + respuesta.datos
      lista  → Panel con numeración limpia
      debug  → Panel monospace
    """
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

    tipo = getattr(respuesta, "tipo", "texto")

    # ── TABLA ───────────────────────────
    if tipo == "tabla" and getattr(respuesta, "columnas", []) and getattr(respuesta, "datos", []):
        # Texto intro si existe
        if respuesta.respuesta:
            console.print(Panel(
                Text(f"  {respuesta.respuesta}", style=C["white"]),
                title=titulo,
                border_style=color,
                padding=(1, 2),
            ))

        # Rich Table
        t = Table(
            box=box.SIMPLE_HEAD,
            border_style=color,
            header_style=f"bold {color}",
            padding=(0, 1),
            show_lines=False,
        )
        for col in respuesta.columnas:
            # Detectar si la columna es numérica para alinear a la derecha
            es_num = _es_columna_numerica(col, respuesta.datos)
            t.add_column(str(col), style=C["muted"], justify="right" if es_num else "left")

        for fila in respuesta.datos:
            t.add_row(*[str(fila.get(col, "—")) for col in respuesta.columnas])

        console.print(Panel(
            t,
            title=f"[{color}] TABLA ({len(respuesta.datos)} filas) [/{color}]",
            border_style=color,
            padding=(0, 1),
        ))

    # ── LISTA ───────────────────────────
    elif tipo == "lista":
        console.print(Panel(
            Text(f"  {respuesta.respuesta}", style=C["white"]),
            title=titulo,
            border_style=color,
            padding=(1, 2),
        ))

    # ── DEBUG ───────────────────────────
    elif tipo == "debug":
        console.print(Panel(
            Text(respuesta.respuesta, style=f"bold {C['muted']}"),
            title=titulo,
            border_style=C["dim"],
            padding=(1, 2),
        ))

    # ── TEXTO (default) ─────────────────
    else:
        console.print(Panel(
            Text(f"  {respuesta.respuesta}", style=C["white"]),
            title=titulo,
            border_style=color,
            padding=(1, 2),
        ))

    # Acción siempre al final (todos los tipos)
    if respuesta.accion:
        console.print(Panel(
            Text.assemble(
                ("  -> ", f"bold {C['accent']}"),
                (respuesta.accion, C["white"]),
            ),
            border_style=C["accent"],
            padding=(0, 2),
        ))

    console.print()


def _es_columna_numerica(col: str, datos: list) -> bool:
    """Heurística — si los primeros valores de la columna parecen numéricos, alinear derecha."""
    for fila in datos[:3]:
        v = str(fila.get(col, "")).strip().replace("$", "").replace(",", "").replace("%", "")
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False


# ─────────────────────────────────────────
# COMANDOS DE CLEANUP — helpers
# ─────────────────────────────────────────

def _recalcular_contexto(df_ghl, engine, calc):
    """
    Recalcula métricas y schema tras modificar df_ghl.
    Actualiza engine.set_contexto_completo() automáticamente.
    Retorna (metricas, resumen_llm, schema_llm).
    """
    try:
        metricas    = calc.calcular(df_ghl, nivel="campana")
        resumen_llm = calc.resumen_para_llm(metricas, nivel="campana")
        schema_llm  = calc.resumen_schema(df_ghl)
        if engine:
            engine.set_contexto_completo(resumen_llm, schema_llm)
            engine.limpiar_memoria()
        return metricas, resumen_llm, schema_llm
    except Exception as e:
        console.print(f"  [{C['warning']}]⚠ No se pudo recalcular contexto: {e}[/{C['warning']}]\n")
        return None, None, None


def cmd_limpiar_duplicados(df_ghl, engine, validator, calc):
    """
    /limpiar_duplicados
    Elimina filas duplicadas y actualiza el engine.
    """
    if df_ghl is None or df_ghl.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return df_ghl

    df_limpio, reporte = validator.limpiar_duplicados(df_ghl)

    if reporte.get("error"):
        console.print(f"  [{C['error']}]✗ {reporte['error']}[/{C['error']}]\n")
        return df_ghl

    n = reporte["eliminados"]
    if n == 0:
        console.print(f"  [{C['success']}]✓ Sin duplicados — datos ya están limpios.[/{C['success']}]\n")
        return df_ghl

    ejemplos = reporte.get("ejemplos_ids", [])
    console.print(
        f"  [{C['success']}]✓ Eliminados:[/{C['success']}] "
        f"[{C['accent']}]{n} duplicados[/{C['accent']}]"
        f"  [{C['dim']}]IDs: {ejemplos}{'...' if len(ejemplos)==5 else ''}[/{C['dim']}]"
    )

    metricas_new, _, _ = _recalcular_contexto(df_limpio, engine, calc)
    if metricas_new is not None:
        console.print(f"  [{C['dim']}]Contexto actualizado — {len(df_limpio)} filas activas.[/{C['dim']}]\n")

    return df_limpio


def cmd_rellenar(df_ghl, engine, validator, calc, partes: list):
    """
    /rellenar [columna] [estrategia]
    Rellena nulos en columna con estrategia dada.
    Uso: /rellenar costo_lead media
         /rellenar estado moda
    """
    if df_ghl is None or df_ghl.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return df_ghl

    if len(partes) < 2:
        console.print(f"  [{C['warning']}]Uso: /rellenar [columna] [media|mediana|moda|valor_custom][/{C['warning']}]\n")
        return df_ghl

    columna    = partes[1]
    estrategia = partes[2] if len(partes) > 2 else "media"
    valor_custom = partes[3] if len(partes) > 3 and estrategia == "valor_custom" else None

    # Convertir valor_custom a número si aplica
    if valor_custom is not None:
        try:
            valor_custom = float(valor_custom)
        except ValueError:
            pass  # dejar como string

    df_nuevo, reporte = validator.rellenar_nulos(df_ghl, columna, estrategia, valor_custom)

    if reporte.get("error"):
        console.print(f"  [{C['error']}]✗ {reporte['error']}[/{C['error']}]\n")
        return df_ghl

    n = reporte.get("rellenados", 0)
    val = reporte.get("valor_usado")
    val_str = f"{val:,.2f}" if isinstance(val, float) else str(val)

    if n == 0:
        console.print(f"  [{C['success']}]✓ Sin nulos en '{columna}' — nada que rellenar.[/{C['success']}]\n")
        return df_ghl

    console.print(
        f"  [{C['success']}]✓ Rellenados:[/{C['success']}] "
        f"[{C['accent']}]{n} nulos[/{C['accent']}] en "
        f"[{C['primary']}]{columna}[/{C['primary']}] "
        f"  [{C['dim']}]estrategia={estrategia} valor={val_str}[/{C['dim']}]"
    )

    _recalcular_contexto(df_nuevo, engine, calc)
    console.print(f"  [{C['dim']}]Contexto actualizado.[/{C['dim']}]\n")

    return df_nuevo


def cmd_eliminar_por(df_ghl, engine, validator, calc, partes: list):
    """
    /eliminar_por [columna] [operador] [valor]
    Elimina filas que cumplen el criterio.
    Uso: /eliminar_por costo_lead <= 0
         /eliminar_por estado == nan
         /eliminar_por email isnull
    """
    if df_ghl is None or df_ghl.empty:
        console.print(f"  [{C['warning']}]Sin datos activos.[/{C['warning']}]\n")
        return df_ghl

    OPERADORES_UNARIOS = {"isnull", "notnull"}

    if len(partes) < 3:
        console.print(
            f"  [{C['warning']}]Uso: /eliminar_por [columna] [op] [valor]\n"
            f"  Ops: == != > < >= <= isnull notnull[/{C['warning']}]\n"
        )
        return df_ghl

    columna  = partes[1]
    operador = partes[2]

    if operador in OPERADORES_UNARIOS:
        valor = None
    elif len(partes) < 4:
        console.print(f"  [{C['warning']}]El operador '{operador}' requiere un valor: /eliminar_por {columna} {operador} [valor][/{C['warning']}]\n")
        return df_ghl
    else:
        raw = partes[3]
        # Intentar parsear como número
        try:
            valor = float(raw) if "." in raw else int(raw)
        except ValueError:
            valor = raw  # dejar como string

    df_filtrado, reporte = validator.eliminar_por_criterio(df_ghl, columna, operador, valor)

    if reporte.get("error"):
        console.print(f"  [{C['error']}]✗ {reporte['error']}[/{C['error']}]\n")
        return df_ghl

    n = reporte["eliminados"]
    criterio = reporte["criterio"]

    if n == 0:
        console.print(f"  [{C['success']}]✓ Ninguna fila cumple '{criterio}' — dataset sin cambios.[/{C['success']}]\n")
        return df_ghl

    console.print(
        f"  [{C['success']}]✓ Eliminadas:[/{C['success']}] "
        f"[{C['accent']}]{n} filas[/{C['accent']}] donde "
        f"[{C['primary']}]{criterio}[/{C['primary']}]"
    )

    metricas_new, _, _ = _recalcular_contexto(df_filtrado, engine, calc)
    if metricas_new is not None:
        console.print(f"  [{C['dim']}]Contexto actualizado — {len(df_filtrado)} filas activas.[/{C['dim']}]\n")

    return df_filtrado


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main() -> None:
    boot_screen()

    config = onboarding() if necesita_onboarding() else cargar_config()

    df_ghl = None
    metricas = resumen_llm = schema_llm = resultado = manager = validator = calc = None
    try:
        df_ghl, _, metricas, resumen_llm, schema_llm, resultado, manager, validator, calc = cargar_datos(
            config["fuente"], config.get("mock_csv", "")
        )
    except Exception as e:
        console.print(f"\n  [{C['error']}]✗ Error cargando datos: {e}[/{C['error']}]\n")

    engine = None
    try:
        sys.path.insert(0, ".")
        from src.ai.engine import AdlyEngine, LLMFactory
        from src.processing.metrics import CONFIG_DEFAULT
        engine = AdlyEngine(llm=LLMFactory.crear(config["llm_provider"]))
        if resumen_llm and schema_llm:
            engine.set_contexto_completo(resumen_llm, schema_llm)
        elif resumen_llm:
            engine.set_contexto(resumen_llm)
    except Exception as e:
        console.print(f"\n  [{C['warning']}]⚠ Engine: {e}[/{C['warning']}]")
        try:
            from src.processing.metrics import CONFIG_DEFAULT
        except Exception:
            CONFIG_DEFAULT = {"col_campana": "campana"}

    if resultado and manager:
        mostrar_estado_inicial(config, resultado, manager)
    else:
        console.print(f"  [{C['warning']}]Sin datos. Usa /refresh.[/{C['warning']}]\n")

    historial = []

    while True:
        try:
            entrada = Prompt.ask(f"\n[{C['primary']}] {config['nombre']}[/{C['primary']}]").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not entrada:
            continue

        cmd = entrada.lower()

        if cmd in ("salir","exit","quit"):
            break

        elif cmd == "/ayuda":
            cmd_ayuda()

        elif cmd == "/alertas":
            cmd_alertas(manager) if manager else \
                console.print(f"  [{C['warning']}]Sin alertas.[/{C['warning']}]\n")

        elif cmd == "/metricas":
            cmd_metricas(metricas, CONFIG_DEFAULT.get("col_campana","campana")) if metricas is not None else \
                console.print(f"  [{C['warning']}]Sin métricas. Usa /refresh.[/{C['warning']}]\n")

        elif cmd == "/refresh":
            try:
                df_ghl, _, metricas, resumen_llm, schema_llm, resultado, manager, validator, calc = cargar_datos(
                    config["fuente"], config.get("mock_csv", "")
                )
                if engine:
                    if schema_llm:
                        engine.set_contexto_completo(resumen_llm, schema_llm)
                    else:
                        engine.set_contexto(resumen_llm)
                    engine.limpiar_memoria()
                console.print(f"  [{C['success']}]✓ Datos actualizados.[/{C['success']}]\n")
            except Exception as e:
                console.print(f"  [{C['error']}]✗ {e}[/{C['error']}]\n")

        elif cmd == "/limpiar":
            if engine: engine.limpiar_memoria()
            historial = []
            console.print(f"  [{C['success']}]✓ Conversación reiniciada.[/{C['success']}]\n")

        elif cmd == "/estado":
            cmd_estado(engine, config)

        elif cmd == "/guardar":
            cmd_guardar(historial)

        elif cmd == "/dashboard":
            cmd_dashboard(metricas, CONFIG_DEFAULT) if metricas is not None else \
                console.print(f"  [{C['warning']}]Sin datos.[/{C['warning']}]\n")

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

        # ── CLEANUP COMMANDS v2 ───────────────────────────────────────

        elif cmd == "/limpiar_duplicados":
            if validator and calc:
                df_ghl = cmd_limpiar_duplicados(df_ghl, engine, validator, calc)
                # Recalcular metricas locales para /metricas
                if df_ghl is not None and calc:
                    try:
                        metricas = calc.calcular(df_ghl, nivel="campana")
                    except Exception:
                        pass
            else:
                console.print(f"  [{C['warning']}]Validator no disponible. Usa /refresh primero.[/{C['warning']}]\n")

        elif cmd.startswith("/rellenar"):
            if validator and calc:
                partes = entrada.split()  # usar entrada original para preservar mayúsculas en columna
                df_ghl = cmd_rellenar(df_ghl, engine, validator, calc, partes)
                if df_ghl is not None and calc:
                    try:
                        metricas = calc.calcular(df_ghl, nivel="campana")
                    except Exception:
                        pass
            else:
                console.print(f"  [{C['warning']}]Validator no disponible. Usa /refresh primero.[/{C['warning']}]\n")

        elif cmd.startswith("/eliminar_por"):
            if validator and calc:
                partes = entrada.split()  # usar entrada original
                df_ghl = cmd_eliminar_por(df_ghl, engine, validator, calc, partes)
                if df_ghl is not None and calc:
                    try:
                        metricas = calc.calcular(df_ghl, nivel="campana")
                    except Exception:
                        pass
            else:
                console.print(f"  [{C['warning']}]Validator no disponible. Usa /refresh primero.[/{C['warning']}]\n")

        # ── CHAT (fallback) ────────────────────────────────────────────

        else:
            if not engine:
                console.print(f"  [{C['error']}]✗ Engine no disponible. Verifica con /estado[/{C['error']}]\n")
                continue

            historial.append({"ts": datetime.now().isoformat(), "rol":"user",
                               "mensaje":entrada, "severidad":"", "confianza":""})

            with console.status(f"  [{C['primary']}]Analizando...[/{C['primary']}]", spinner="dots2"):
                respuesta = engine.chat(entrada)

            console.print(f"\n  [{C['primary']}]▸ Adly[/{C['primary']}]")
            renderizar_respuesta(respuesta)

            historial.append({"ts": datetime.now().isoformat(), "rol":"adly",
                               "mensaje":respuesta.respuesta, "severidad":respuesta.severidad,
                               "confianza":respuesta.confianza})

    console.print()
    console.rule(style=C["dim"])
    console.print(Align.center(Text(
        f"  ADLY {VERSION}  ·  hasta pronto, {config['nombre']}  ",
        style=C["dim"]
    )))
    console.print()


if __name__ == "__main__":
    main()
