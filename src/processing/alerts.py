# alerts.py — Adly · Data-Buddy
# Sistema de alertas de integridad de datos
# Convierte resultados técnicos en mensajes accionables

from dataclasses import dataclass, field
from typing import List
from enum import Enum
from src.processing.validation import ResultadoValidacion


# ─────────────────────────────────────────
# NIVEL DE ALERTA
# ─────────────────────────────────────────

class NivelAlerta(Enum):
    """
    Enum — tipo especial de clase para valores constantes.
    Evita usar strings sueltos como "critica" o "ok" que
    son difíciles de mantener y pueden tener errores de tipeo.
    """
    OK          = "ok"
    ADVERTENCIA = "advertencia"
    CRITICA     = "critica"


# ─────────────────────────────────────────
# ALERTA INDIVIDUAL
# ─────────────────────────────────────────

@dataclass
class Alerta:
    """
    Representa una alerta individual del sistema.
    Tiene un nivel, un mensaje para el usuario y
    una recomendación de qué hacer.
    """
    nivel:          NivelAlerta
    mensaje:        str
    recomendacion:  str
    ids_afectados:  List[str] = field(default_factory=list)

    def __str__(self) -> str:
        iconos = {
            NivelAlerta.OK:          "✓",
            NivelAlerta.ADVERTENCIA: "⚠",
            NivelAlerta.CRITICA:     "✗",
        }
        icono = iconos[self.nivel]
        lineas = [
            f"{icono} [{self.nivel.value.upper()}] {self.mensaje}",
            f"  → {self.recomendacion}",
        ]
        if self.ids_afectados:
            muestra = self.ids_afectados[:3]
            extra   = len(self.ids_afectados) - 3
            lineas.append(f"  IDs afectados: {muestra}" + (f" y {extra} más" if extra > 0 else ""))
        return "\n".join(lineas)


# ─────────────────────────────────────────
# GENERADOR DE ALERTAS
# ─────────────────────────────────────────

class AlertManager:
    """
    Analiza un ResultadoValidacion y genera alertas accionables.
    Separa la detección (DataValidator) de la comunicación (AlertManager).
    Cada clase tiene una sola responsabilidad — SRP en acción.
    """

    # Umbrales configurables
    UMBRAL_FALTANTES_CRITICO     = 0.10   # >10% de leads faltantes = crítico
    UMBRAL_FALTANTES_ADVERTENCIA = 0.05   # >5% = advertencia
    UMBRAL_SCORE_CRITICO         = 70.0   # score <70 = crítico
    UMBRAL_SCORE_ADVERTENCIA     = 90.0   # score <90 = advertencia

    def __init__(self):
        self.alertas: List[Alerta] = []

    def evaluar(self, resultado: ResultadoValidacion) -> List[Alerta]:
        """
        Evalúa el resultado de validación y genera todas las alertas.
        Retorna la lista de alertas ordenada por severidad.
        """
        self.alertas = []

        self._evaluar_faltantes(resultado)
        self._evaluar_duplicados(resultado)
        self._evaluar_campos_vacios(resultado)
        self._evaluar_estados(resultado)
        self._evaluar_score_general(resultado)

        # Ordenar por severidad — críticas primero
        orden = {NivelAlerta.CRITICA: 0, NivelAlerta.ADVERTENCIA: 1, NivelAlerta.OK: 2}
        self.alertas.sort(key=lambda a: orden[a.nivel])

        return self.alertas

    def imprimir(self) -> None:
        """Imprime todas las alertas en terminal."""
        if not self.alertas:
            print("Sin alertas generadas.")
            return

        print(f"\n{'='*50}")
        print(f"  ALERTAS DEL SISTEMA ({len(self.alertas)})")
        print(f"{'='*50}")
        for alerta in self.alertas:
            print(alerta)
            print(f"{'─'*50}")

    def tiene_criticas(self) -> bool:
        """Retorna True si hay al menos una alerta crítica."""
        return any(a.nivel == NivelAlerta.CRITICA for a in self.alertas)

    def resumen_para_chat(self) -> str:
        """
        Genera un resumen en lenguaje natural para el chatbot.
        Esto es lo que Adly le dice a Camí cuando pregunta
        por el estado de sus datos.
        """
        if not self.alertas:
            return "Los datos están sincronizados correctamente."

        criticas     = [a for a in self.alertas if a.nivel == NivelAlerta.CRITICA]
        advertencias = [a for a in self.alertas if a.nivel == NivelAlerta.ADVERTENCIA]

        partes = []
        if criticas:
            partes.append(f"🔴 {len(criticas)} problema(s) crítico(s) detectado(s).")
        if advertencias:
            partes.append(f"🟡 {len(advertencias)} advertencia(s).")
        if not criticas and not advertencias:
            partes.append("🟢 Datos en buen estado.")

        partes.append("Usa 'detalle alertas' para ver el reporte completo.")
        return " ".join(partes)

    # ── evaluadores individuales ──────────

    def _evaluar_faltantes(self, r: ResultadoValidacion) -> None:
        if not r.faltantes:
            return

        pct = len(r.faltantes) / r.total_ghl if r.total_ghl > 0 else 0

        if pct > self.UMBRAL_FALTANTES_CRITICO:
            self.alertas.append(Alerta(
                nivel         = NivelAlerta.CRITICA,
                mensaje       = f"{len(r.faltantes)} leads no llegaron al Sheet ({pct*100:.1f}% del total).",
                recomendacion = "Revisar flujo de n8n. Posible falla en la automatización.",
                ids_afectados = r.faltantes,
            ))
        else:
            self.alertas.append(Alerta(
                nivel         = NivelAlerta.ADVERTENCIA,
                mensaje       = f"{len(r.faltantes)} leads faltantes en Sheet ({pct*100:.1f}%).",
                recomendacion = "Monitorear — si aumenta, revisar n8n.",
                ids_afectados = r.faltantes,
            ))

    def _evaluar_duplicados(self, r: ResultadoValidacion) -> None:
        if not r.duplicados:
            return

        self.alertas.append(Alerta(
            nivel         = NivelAlerta.ADVERTENCIA,
            mensaje       = f"{len(r.duplicados)} leads duplicados en Sheet.",
            recomendacion = "n8n ejecutó el flujo dos veces. Revisar triggers de automatización.",
            ids_afectados = r.duplicados,
        ))

    def _evaluar_campos_vacios(self, r: ResultadoValidacion) -> None:
        for col, ids in r.campos_vacios.items():
            self.alertas.append(Alerta(
                nivel         = NivelAlerta.ADVERTENCIA,
                mensaje       = f"{len(ids)} registros con '{col}' vacío.",
                recomendacion = f"Verificar mapeo de campos en n8n para '{col}'.",
                ids_afectados = ids,
            ))

    def _evaluar_estados(self, r: ResultadoValidacion) -> None:
        if not r.estados_diff:
            return

        self.alertas.append(Alerta(
            nivel         = NivelAlerta.ADVERTENCIA,
            mensaje       = f"{len(r.estados_diff)} leads con estado desactualizado en Sheet.",
            recomendacion = "El Sheet no refleja el estado actual del CRM. Forzar resincronización.",
            ids_afectados = r.estados_diff,
        ))

    def _evaluar_score_general(self, r: ResultadoValidacion) -> None:
        if r.score < self.UMBRAL_SCORE_CRITICO:
            self.alertas.append(Alerta(
                nivel         = NivelAlerta.CRITICA,
                mensaje       = f"Score de integridad crítico: {r.score}%.",
                recomendacion = "Los análisis de Adly no son confiables hasta corregir los datos.",
                ids_afectados = [],
            ))
        elif r.score < self.UMBRAL_SCORE_ADVERTENCIA:
            self.alertas.append(Alerta(
                nivel         = NivelAlerta.ADVERTENCIA,
                mensaje       = f"Score de integridad bajo: {r.score}%.",
                recomendacion = "Corregir errores antes de tomar decisiones de pauta.",
                ids_afectados = [],
            ))
        else:
            self.alertas.append(Alerta(
                nivel         = NivelAlerta.OK,
                mensaje       = f"Score de integridad aceptable: {r.score}%.",
                recomendacion = "Continuar monitoreando.",
                ids_afectados = [],
            ))


# ─────────────────────────────────────────
# MAIN — probar con mock data
# ─────────────────────────────────────────

if __name__ == "__main__":
    import pandas as pd
    from src.processing.validation import DataValidator

    print(">> Ejecutando pipeline completo: validación + alertas\n")

    df_ghl   = pd.read_csv("data/raw/mock_ghl.csv")
    df_sheet = pd.read_csv("data/raw/mock_sheet.csv")

    # Validar
    validador  = DataValidator()
    resultado  = validador.validar(df_ghl, df_sheet)
    print(resultado.resumen())

    # Generar alertas
    manager = AlertManager()
    manager.evaluar(resultado)
    manager.imprimir()

    # Lo que Adly le diría a Camí
    print(f"\n>> Lo que Adly le dice a Camí:")
    print(f"   {manager.resumen_para_chat()}")
