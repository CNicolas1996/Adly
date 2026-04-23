# onboarding.py — Adly · Data-Buddy
# Boot screen, onboarding y helpers de config
# Separado del main loop para mantener cli.py limpio

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv, set_key

from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt
from rich.align import Align
from rich import box

from interfaces.cli.theme import console, C, ICON, VERSION

ENV_PATH = Path(".env")

# ─────────────────────────────────────────
# LOGO
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


def limpiar_pantalla() -> None:
    os.system("cls" if os.name == "nt" else "clear")


# ─────────────────────────────────────────
# BOOT SCREEN
# ─────────────────────────────────────────

def boot_screen() -> None:
    limpiar_pantalla()
    mostrar_logo()

    console.print(Align.center(Text(
        "El analista de pauta que tu agencia necesita pero no tiene.",
        style=f"italic {C['muted']}",
    )))
    console.print(Align.center(Text(
        f"━━━  {VERSION}  ·  Data-Buddy  ·  2026  ━━━",
        style=f"bold {C['accent']}",
    )))
    console.print()
    console.rule(style=C["dim"])
    console.print()

    boot_seq = [
        ("SYS", "Iniciando núcleo de análisis...",  C["dim"]),
        ("MEM", "Cargando modelos de métricas...",  C["dim"]),
        ("NET", "Verificando proveedores LLM...",   C["dim"]),
        ("DAT", "Preparando pipeline de datos...",  C["dim"]),
        ("SEC", "Validando credenciales...",         C["dim"]),
        ("OK ", "Sistema listo.",                   C["success"]),
    ]
    for tag, msg, color in boot_seq:
        time.sleep(0.28)
        console.print(Text.assemble(
            (f"  {tag}  ", f"bold {C['primary']}"),
            (msg, color),
        ))

    console.print()
    time.sleep(0.8)
    limpiar_pantalla()


# ─────────────────────────────────────────
# PROVEEDORES Y FUENTES
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
    "1": ("mock",   "Mock data    — datos de prueba  ← empieza aquí"),
    "2": ("sheets", "Google Sheets— Sheet real"),
    "3": ("meta",   "Meta + GHL   — conexión directa APIs"),
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
# ONBOARDING — 4 pasos
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

    # Paso 1 — Nombre
    limpiar_pantalla(); mostrar_logo()
    console.print(Panel(
        Text.assemble(
            (f"  PASO 1 de 4  ", f"bold reverse {C['accent']}"),
            ("  ¿Cómo te llamas?\n\n", f"bold {C['white']}"),
            ("  El nombre que Adly usará para saludarte.", C["dim"]),
        ),
        border_style=C["primary"], padding=(0, 2),
    ))
    console.print()
    config["nombre"] = Prompt.ask(f"  [{C['accent']}]Nombre[/{C['accent']}]")
    console.print()

    # Paso 2 — LLM
    limpiar_pantalla(); mostrar_logo()
    console.print(Panel(
        Text.assemble(
            (f"  PASO 2 de 4  ", f"bold reverse {C['accent']}"),
            ("  ¿Qué proveedor LLM usas?\n\n", f"bold {C['white']}"),
            ("  Puedes cambiarlo editando .env", C["dim"]),
        ),
        border_style=C["primary"], padding=(0, 2),
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

    # Paso 3 — Credenciales
    limpiar_pantalla(); mostrar_logo()
    console.print(Panel(
        Text.assemble(
            (f"  PASO 3 de 4  ", f"bold reverse {C['accent']}"),
            (f"  Credenciales — {config['llm_provider'].upper()}\n\n", f"bold {C['white']}"),
            ("  Se guardan en .env y nunca salen de tu máquina.", C["dim"]),
        ),
        border_style=C["primary"], padding=(0, 2),
    ))
    console.print()
    if config["llm_provider"] == "ollama":
        console.print(f"  [{C['success']}]{ICON['ok']}  Ollama no requiere API Key[/{C['success']}]")
        console.print()
        config["llm_api_key"]  = ""
        config["llm_base_url"] = Prompt.ask(
            f"  [{C['accent']}]URL Ollama[/{C['accent']}]",
            default="http://localhost:11434",
        )
        config["llm_model"] = Prompt.ask(
            f"  [{C['accent']}]Modelo[/{C['accent']}]",
            default="qwen2.5-coder:7b",
        )
    else:
        console.print(f"  [{C['dim']}]La API Key no se mostrará mientras escribes.[/{C['dim']}]")
        console.print()
        config["llm_api_key"]  = Prompt.ask(f"  [{C['accent']}]API Key[/{C['accent']}]", password=True)
        console.print()
        config["llm_model"]    = Prompt.ask(
            f"  [{C['accent']}]Modelo[/{C['accent']}]",
            default=MODELOS_DEFAULT.get(config["llm_provider"], ""),
        )
        config["llm_base_url"] = BASE_URLS.get(config["llm_provider"], "")
    console.print()

    # Paso 4 — Fuente
    limpiar_pantalla(); mostrar_logo()
    console.print(Panel(
        Text.assemble(
            (f"  PASO 4 de 4  ", f"bold reverse {C['accent']}"),
            ("  ¿Qué fuente de datos usas?\n\n", f"bold {C['white']}"),
            ("  Puedes empezar con Mock y conectar datos reales después.", C["dim"]),
        ),
        border_style=C["primary"], padding=(0, 2),
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
        config["ghl_api_key"] = Prompt.ask(f"  [{C['accent']}]GHL API Key[/{C['accent']}]", password=True)
        config["mock_csv"]    = ""
    else:
        config["sheet_id"] = ""
        console.print(f"  [{C['dim']}]CSV de prueba (Enter para usar datos generados):[/{C['dim']}]")
        config["mock_csv"] = Prompt.ask(f"  [{C['accent']}]Ruta CSV[/{C['accent']}]", default="")

    _guardar_env(config)

    console.print()
    console.print(Panel(
        Text.assemble(
            ("\n  ✓  Configurado para ",          C["success"]),
            (config["nombre"],                    f"bold {C['accent']}"),
            ("\n  ✓  LLM:    ",                   C["success"]),
            (config["llm_provider"],              f"bold {C['white']}"),
            (f"  ({config.get('llm_model','')})", C["dim"]),
            ("\n  ✓  Fuente: ",                   C["success"]),
            (config["fuente"],                    f"bold {C['white']}"),
            ("\n\n  Arrancando Adly...\n",         C["dim"]),
        ),
        border_style=C["success"],
        padding=(0, 2),
    ))
    time.sleep(1.2)
    return config


# ─────────────────────────────────────────
# CONFIG HELPERS
# ─────────────────────────────────────────

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
