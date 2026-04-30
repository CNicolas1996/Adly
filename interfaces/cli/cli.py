# cli.py — Adly · Data-Buddy
# Terminal User Interface — v2
# Estética: Blade Runner — azul eléctrico + naranja sobre negro
#
# Arquitectura modular:
#   theme.py     — paleta, iconos, helpers visuales
#   renderer.py  — renderizado de respuestas Adly
#   commands.py  — handlers de comandos /cmd
#   onboarding.py— boot screen, onboarding, config

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Root del proyecto = dos niveles arriba de interfaces/cli/cli.py
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Silenciar warnings de pandas y librerías externas — no son errores del usuario
import warnings
warnings.filterwarnings("ignore")

try:
    from rich.prompt import Prompt
    from rich.text import Text
    from rich.align import Align
    from rich.panel import Panel
except ImportError:
    print("[ERROR] Instala dependencias: pip install rich python-dotenv")
    sys.exit(1)

# Módulos Adly CLI
from interfaces.cli.theme    import console, C, ICON, VERSION
from interfaces.cli.renderer import renderizar_respuesta
from interfaces.cli.commands import (
    cmd_ayuda, cmd_alertas, cmd_metricas, cmd_estado,
    cmd_guardar, cmd_dashboard,
    cmd_head, cmd_sample, cmd_describe, cmd_exportar_df,
    cmd_columnas, cmd_nulos, cmd_outliers, cmd_correlacion,
    cmd_unicos, cmd_rango, cmd_top,
    cmd_limpiar_duplicados, cmd_rellenar, cmd_eliminar_por,
    cmd_cohorts, cmd_rentabilidad, cmd_rfm, cmd_embudo, cmd_velocidad,
)
from interfaces.cli.onboarding import (
    boot_screen, onboarding, cargar_config, necesita_onboarding,
    limpiar_pantalla, mostrar_logo, reconfigurar,
)

ENV_PATH = Path(".env")


# ─────────────────────────────────────────
# CARGA DE DATOS
# ─────────────────────────────────────────

def cargar_datos(fuente: str, mock_csv: str = ""):
    sys.path.insert(0, ".")
    from src.ingestion.mock_data import generar_datos_ghl, generar_datos_sheet
    from src.processing.validation import DataValidator
    from src.processing.alerts import AlertManager
    from src.processing.metrics import MetricsCalculator, CONFIG_DEFAULT
    from src.processing.schema_watcher import SchemaWatcher

    with console.status(
        f"  [{C['primary']}]Cargando [{fuente.upper()}]...[/{C['primary']}]",
        spinner="arc",
    ):
        time.sleep(0.6)
        # Suprimir prints de librerías internas (column_mapper, sheets) durante carga
        import io
        _stdout = sys.stdout
        sys.stdout = io.StringIO()
        config_cols = CONFIG_DEFAULT

        try:
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

            validator   = DataValidator()
            resultado   = validator.validar(df_ghl, df_sheet)
            calc        = MetricsCalculator(config=config_cols)
            metricas    = calc.calcular(df_ghl, nivel="campana")
            # resumen_ejecutivo_llm → contexto comprimido para el LLM (~375 tokens)
            # resumen_para_llm     → texto completo para comandos CLI (/metricas, etc.)
            resumen_llm = calc.resumen_ejecutivo_llm(df_ghl)
            schema_llm  = calc.resumen_schema(df_ghl)
            manager     = AlertManager(resultado, metricas, config_cols)

            # Schema watcher — vigila cambios entre cargas
            watcher      = SchemaWatcher()
            reporte_carga = watcher.registrar(df_ghl)

        finally:
            sys.stdout = _stdout  # restaurar stdout siempre, incluso si hay excepción

    return df_ghl, df_sheet, metricas, resumen_llm, schema_llm, resultado, manager, validator, calc, reporte_carga


# ─────────────────────────────────────────
# MOSTRAR REPORTE DE CARGA
# ─────────────────────────────────────────

def mostrar_reporte_carga(reporte_carga) -> None:
    """Muestra el reporte del schema watcher después de cada carga."""
    if reporte_carga is None:
        return

    if reporte_carga.es_primera_carga:
        console.print(
            f"  [{C['dim']}]{ICON['ok']}  {reporte_carga.mensajes[0]}[/{C['dim']}]"
        )
        return

    for msg in reporte_carga.mensajes:
        if reporte_carga.nivel == "critica":
            console.print(f"  [{C['error']}]{ICON['crit']}  {msg}[/{C['error']}]")
        elif reporte_carga.nivel == "advertencia":
            console.print(f"  [{C['warning']}]{ICON['warn']}  {msg}[/{C['warning']}]")
        else:
            console.print(f"  [{C['dim']}]{ICON['ok']}  {msg}[/{C['dim']}]")


# ─────────────────────────────────────────
# ESTADO INICIAL — status bar compacta
# ─────────────────────────────────────────

def mostrar_estado_inicial(config, resultado, manager, reporte_carga=None) -> None:
    n_crit = sum(1 for a in manager.alertas if a.nivel.value == "critica")
    n_warn = sum(1 for a in manager.alertas if a.nivel.value == "advertencia")

    # Score color
    score = resultado.score
    sc = C["success"] if score >= 90 else C["warning"] if score >= 70 else C["error"]

    # Alertas compactas
    if n_crit:
        alerta_str = f"{ICON['crit']} {n_crit} críticas"
        alerta_color = C["error"]
    elif n_warn:
        alerta_str = f"{ICON['warn']} {n_warn} advertencias"
        alerta_color = C["warning"]
    else:
        alerta_str = f"{ICON['ok']} sin alertas"
        alerta_color = C["success"]

    # Status bar en una línea
    console.print(
        Text.assemble(
            ("  ", ""),
            (config["nombre"],       f"bold {C['accent']}"),
            ("  ·  ", C["dim"]),
            (config["fuente"],       C["muted"]),
            ("  ·  score ", C["dim"]),
            (f"{score:.1f}%",        f"bold {sc}"),
            ("  ·  ", C["dim"]),
            (alerta_str,             f"bold {alerta_color}"),
            ("  ·  ", C["dim"]),
            (config["llm_provider"], C["muted"]),
        )
    )
    console.print()

    # Reporte de carga (schema watcher)
    if reporte_carga:
        mostrar_reporte_carga(reporte_carga)
        console.print()

    # Alertas críticas al inicio si hay
    if manager.tiene_criticas():
        for a in manager.alertas:
            if a.nivel.value == "critica":
                console.print(
                    f"  [{C['error']}]{ICON['crit']}  {a.mensaje}[/{C['error']}]"
                )
                console.print(f"  [{C['dim']}]  {ICON['arrow']} {a.recomendacion}[/{C['dim']}]")
        console.print()

    console.print(
        f"  [{C['dim']}]Escribe tu pregunta o [/{C['dim']}]"
        f"[{C['accent']}]/ayuda[/{C['accent']}]"
        f"[{C['dim']}] para ver comandos.[/{C['dim']}]"
    )
    console.print()


# ─────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────

def main() -> None:
    boot_screen()

    config = onboarding() if necesita_onboarding() else cargar_config()

    df_ghl = None
    metricas = resumen_llm = schema_llm = resultado = manager = validator = calc = reporte_carga = None
    try:
        df_ghl, _, metricas, resumen_llm, schema_llm, resultado, manager, validator, calc, reporte_carga = cargar_datos(
            config["fuente"], config.get("mock_csv", "")
        )
    except Exception as e:
        console.print(f"\n  [{C['error']}]{ICON['crit']} Error cargando datos: {e}[/{C['error']}]\n")

    engine = None
    try:
        sys.path.insert(0, ".")
        from src.ai.engine import AdlyEngine, LLMFactory
        from src.processing.metrics import CONFIG_DEFAULT
        engine = AdlyEngine(llm=LLMFactory.crear(config["llm_provider"]))
        if resumen_llm and schema_llm:
            engine.set_contexto_completo(resumen_llm, schema_llm, fuente=config["fuente"])
        elif resumen_llm:
            engine.set_contexto(resumen_llm, fuente=config["fuente"])
    except Exception as e:
        console.print(f"\n  [{C['warning']}]{ICON['warn']} Engine: {e}[/{C['warning']}]")
        try:
            from src.processing.metrics import CONFIG_DEFAULT
        except Exception:
            CONFIG_DEFAULT = {"col_campana": "campana"}

    if resultado and manager:
        mostrar_estado_inicial(config, resultado, manager, reporte_carga)
    else:
        console.print(f"  [{C['warning']}]Sin datos. Usa /refresh.[/{C['warning']}]\n")

    historial = []

    # ── Loop principal ─────────────────────────────────────────
    while True:
        try:
            entrada = Prompt.ask(
                f"\n[{C['primary']}] {config['nombre']}[/{C['primary']}]"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not entrada:
            continue

        cmd = entrada.lower()

        # ── Comandos de salida ─────────────────────────────────
        if cmd in ("salir", "exit", "quit"):
            break

        # ── Comandos info ──────────────────────────────────────
        elif cmd.startswith("/ayuda"):
            partes = entrada.split()
            flag = partes[1] if len(partes) > 1 else ""
            cmd_ayuda(flag)

        elif cmd == "/alertas":
            if manager:
                cmd_alertas(manager)
            else:
                console.print(f"  [{C['warning']}]Sin alertas.[/{C['warning']}]\n")

        elif cmd == "/metricas":
            if metricas is not None:
                cmd_metricas(metricas, CONFIG_DEFAULT.get("col_campana", "campana"), excluidos=getattr(calc, "_excluidos_sin_grupo", 0))
            else:
                console.print(f"  [{C['warning']}]Sin métricas. Usa /refresh.[/{C['warning']}]\n")

        elif cmd == "/estado":
            cmd_estado(engine, config)

        elif cmd == "/guardar":
            cmd_guardar(historial)

        elif cmd == "/dashboard":
            if metricas is not None:
                cmd_dashboard(metricas, CONFIG_DEFAULT)
            else:
                console.print(f"  [{C['warning']}]Sin datos.[/{C['warning']}]\n")

       # ── Comandos exploración ───────────────────────────────
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

        elif cmd == "/columnas":
            cmd_columnas(df_ghl)

        elif cmd == "/nulos":
            cmd_nulos(df_ghl)

        elif cmd.startswith("/outliers"):
            partes = entrada.split()
            col = partes[1] if len(partes) > 1 else None
            cmd_outliers(df_ghl, col)

        elif cmd == "/correlacion":
            cmd_correlacion(df_ghl)

        elif cmd.startswith("/unicos"):
            partes = entrada.split()
            col = partes[1] if len(partes) > 1 else None
            cmd_unicos(df_ghl, col)

        elif cmd.startswith("/rango"):
            partes = entrada.split()
            col = partes[1] if len(partes) > 1 else None
            cmd_rango(df_ghl, col)

        elif cmd.startswith("/top"):
            partes = entrada.split()
            col = partes[1] if len(partes) > 1 else None
            n = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else 10
            cmd_top(df_ghl, col, n)

        elif cmd == "/exportar":
            cmd_exportar_df(df_ghl)

        # ── Modelos estadísticos ───────────────────────────────
        elif cmd == "/cohorts":
            ctx = cmd_cohorts(df_ghl)
            if ctx and engine:
                engine.agregar_contexto_comando("/cohorts", ctx)

        elif cmd == "/rentabilidad":
            cmd_rentabilidad(df_ghl)

        elif cmd == "/rfm":
            ctx = cmd_rfm(df_ghl)
            if ctx and engine:
                engine.agregar_contexto_comando("/rfm", ctx)

        elif cmd.startswith("/embudo"):
            partes = entrada.split()
            col_campana = " ".join(partes[1:]) if len(partes) > 1 else ""
            ctx = cmd_embudo(df_ghl, col_campana)
            if ctx and engine:
                engine.agregar_contexto_comando("/embudo", ctx)

        elif cmd == "/velocidad":
            cmd_velocidad(df_ghl)

        # ── Comando /config — reconfigurar sin reiniciar ──────
        elif cmd == "/config":
            config = reconfigurar(config, engine=engine)
            try:
                df_ghl, _, metricas, resumen_llm, schema_llm, resultado, manager, validator, calc, reporte_carga = cargar_datos(
                    config["fuente"], config.get("mock_csv", "")
                )
                if engine:
                    if schema_llm:
                        engine.set_contexto_completo(resumen_llm, schema_llm, fuente=config["fuente"])
                    else:
                        engine.set_contexto(resumen_llm, fuente=config["fuente"])
                    engine.limpiar_memoria()
                console.print(f"  [{C['success']}]{ICON['ok']} Datos recargados con nueva configuración.[/{C['success']}]\n")
            except Exception as e:
                console.print(f"  [{C['warning']}]{ICON['warn']} Config guardada. Usa /refresh para recargar datos: {e}[/{C['warning']}]\n")

        # ── Comandos refresh y limpieza ────────────────────────
        elif cmd == "/refresh":
            try:
                df_ghl, _, metricas, resumen_llm, schema_llm, resultado, manager, validator, calc, reporte_carga = cargar_datos(
                    config["fuente"], config.get("mock_csv", "")
                )
                if engine:
                    if schema_llm:
                        engine.set_contexto_completo(resumen_llm, schema_llm, fuente=config["fuente"])
                    else:
                        engine.set_contexto(resumen_llm, fuente=config["fuente"])
                    engine.limpiar_memoria()
                console.print(f"  [{C['success']}]{ICON['ok']} Datos actualizados.[/{C['success']}]\n")
                mostrar_reporte_carga(reporte_carga)
                console.print()
            except Exception as e:
                console.print(f"  [{C['error']}]{ICON['crit']} {e}[/{C['error']}]\n")

        elif cmd == "/limpiar":
            if engine:
                engine.limpiar_memoria()
            historial = []
            console.print(f"  [{C['success']}]{ICON['ok']} Conversación reiniciada.[/{C['success']}]\n")

        # ── Comandos cleanup ───────────────────────────────────
        elif cmd == "/limpiar_duplicados":
            if validator and calc:
                df_ghl = cmd_limpiar_duplicados(df_ghl, engine, validator, calc)
                if df_ghl is not None and calc:
                    try:
                        metricas = calc.calcular(df_ghl, nivel="campana")
                    except Exception:
                        pass
            else:
                console.print(f"  [{C['warning']}]Validator no disponible. Usa /refresh primero.[/{C['warning']}]\n")

        elif cmd.startswith("/rellenar"):
            if validator and calc:
                partes = entrada.split()
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
                partes = entrada.split()
                df_ghl = cmd_eliminar_por(df_ghl, engine, validator, calc, partes)
                if df_ghl is not None and calc:
                    try:
                        metricas = calc.calcular(df_ghl, nivel="campana")
                    except Exception:
                        pass
            else:
                console.print(f"  [{C['warning']}]Validator no disponible. Usa /refresh primero.[/{C['warning']}]\n")

        # ── Comando desconocido — no cae al chat ──────────────
        elif cmd.startswith("/"):
            console.print(
                f"  [{C['warning']}]{ICON['warn']} "
                f"Comando '{cmd}' no reconocido. "
                f"Escribe /ayuda para ver los disponibles.[/{C['warning']}]\n"
            )

        # ── Chat (fallback) ────────────────────────────────────
        else:
            if not engine:
                console.print(
                    f"  [{C['error']}]{ICON['crit']} Engine no disponible. Verifica con /estado[/{C['error']}]\n"
                )
                continue

            historial.append({
                "ts": datetime.now().isoformat(),
                "rol": "user",
                "mensaje": entrada,
                "severidad": "",
                "confianza": "",
            })

            with console.status(
                f"  [{C['primary']}]Analizando...[/{C['primary']}]",
                spinner="arc",
            ):
                # ── Interceptor pandas — antes del LLM ──────────
                if df_ghl is not None:
                    from src.processing.query_engine import ejecutar_query_analitica
                    resultado_pandas = ejecutar_query_analitica(entrada, df_ghl)
                    if resultado_pandas:
                        engine.agregar_contexto_comando("query_analitica", resultado_pandas)
                # ────────────────────────────────────────────────
                respuesta = engine.chat(entrada)

            console.print(
                f"\n  [{C['primary']}]{ICON['adly']} Adly[/{C['primary']}]"
            )
            renderizar_respuesta(respuesta)

            historial.append({
                "ts":        datetime.now().isoformat(),
                "rol":       "adly",
                "mensaje":   respuesta.respuesta,
                "severidad": respuesta.severidad,
                "confianza": respuesta.confianza,
            })

    # ── Despedida ──────────────────────────────────────────────
    console.print()
    console.rule(style=C["dim"])
    console.print(Align.center(Text(
        f"  ADLY {VERSION}  ·  hasta pronto, {config['nombre']}  ",
        style=C["dim"],
    )))
    console.print()


if __name__ == "__main__":
    main()
