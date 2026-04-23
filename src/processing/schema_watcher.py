# schema_watcher.py — Adly · Data-Buddy
# Vigila el schema del dataset entre cargas y genera reporte de carga.
# Detecta: columnas desaparecidas, cambios de tipo, caída de filas.
# Se integra con AlertManager y se llama en cada /refresh.

import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# ─────────────────────────────────────────
# FINGERPRINT — snapshot del schema
# ─────────────────────────────────────────

@dataclass
class SchemaFingerprint:
    """
    Snapshot del schema en un momento dado.
    Se serializa a JSON para persistir entre sesiones.
    """
    timestamp:   str
    n_filas:     int
    n_columnas:  int
    columnas:    dict  # {nombre: dtype_str}

    def to_dict(self) -> dict:
        return {
            "timestamp":  self.timestamp,
            "n_filas":    self.n_filas,
            "n_columnas": self.n_columnas,
            "columnas":   self.columnas,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SchemaFingerprint":
        return cls(
            timestamp=  d["timestamp"],
            n_filas=    d["n_filas"],
            n_columnas= d["n_columnas"],
            columnas=   d["columnas"],
        )

    @classmethod
    def desde_df(cls, df: pd.DataFrame) -> "SchemaFingerprint":
        return cls(
            timestamp=  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            n_filas=    len(df),
            n_columnas= len(df.columns),
            columnas=   {col: str(df[col].dtype) for col in df.columns},
        )


# ─────────────────────────────────────────
# REPORTE DE CARGA
# ─────────────────────────────────────────

@dataclass
class ReporteCarga:
    """
    Resultado de comparar el schema actual contra el anterior.
    Incluye errores detectados, cambios y resumen de la carga.
    """
    timestamp:          str
    n_filas_actual:     int
    n_filas_anterior:   Optional[int]
    es_primera_carga:   bool

    # Cambios de schema
    columnas_nuevas:     list = field(default_factory=list)
    columnas_perdidas:   list = field(default_factory=list)
    tipos_cambiados:     list = field(default_factory=list)  # [(col, tipo_antes, tipo_ahora)]

    # Anomalías de datos
    caida_filas:         bool  = False
    pct_caida:           float = 0.0

    # Niveles: "ok" | "advertencia" | "critica"
    nivel:               str   = "ok"
    mensajes:            list  = field(default_factory=list)

    def tiene_problemas(self) -> bool:
        return self.nivel in ("advertencia", "critica")

    def resumen_para_llm(self) -> str:
        """Versión compacta para inyectar al engine."""
        if self.es_primera_carga:
            return (
                f"Primera carga: {self.n_filas_actual} filas, "
                f"{len(self.columnas)} columnas detectadas."
                if hasattr(self, "columnas") else
                f"Primera carga: {self.n_filas_actual} filas."
            )
        lineas = [f"Carga {self.timestamp}: {self.n_filas_actual} filas."]
        for m in self.mensajes:
            lineas.append(f"  - {m}")
        return " ".join(lineas)


# ─────────────────────────────────────────
# SCHEMA WATCHER
# ─────────────────────────────────────────

COLUMNAS_CRITICAS_DEFAULT = [
    "campana", "adset", "estado", "costo_lead", "valor_venta", "ghl_id"
]

UMBRAL_CAIDA_ADVERTENCIA = 0.20   # >20% menos filas = advertencia
UMBRAL_CAIDA_CRITICA     = 0.50   # >50% menos filas = crítica


class SchemaWatcher:
    """
    Vigila el schema del dataset entre cargas.

    Flujo:
        1. Al cargar datos → watcher.registrar(df)
        2. Compara contra fingerprint anterior (si existe)
        3. Genera ReporteCarga con nivel y mensajes
        4. Persiste el nuevo fingerprint para la próxima carga

    Uso en cli.py (dentro de cargar_datos):
        watcher = SchemaWatcher()
        reporte = watcher.registrar(df_ghl)
        # reporte.nivel, reporte.mensajes disponibles
    """

    FINGERPRINT_PATH = Path(".adly_schema.json")

    def __init__(
        self,
        columnas_criticas: list = None,
        fingerprint_path: Path = None,
    ):
        self.columnas_criticas = columnas_criticas or COLUMNAS_CRITICAS_DEFAULT
        self.fingerprint_path  = fingerprint_path or self.FINGERPRINT_PATH
        self._anterior: Optional[SchemaFingerprint] = self._cargar_fingerprint()

    # ── API pública ───────────────────────

    def registrar(self, df: pd.DataFrame) -> ReporteCarga:
        """
        Registra el schema actual y retorna un ReporteCarga.
        Llama esto en cada carga/refresh.
        """
        actual   = SchemaFingerprint.desde_df(df)
        reporte  = self._comparar(actual, self._anterior)
        self._guardar_fingerprint(actual)
        self._anterior = actual
        return reporte

    def tiene_fingerprint(self) -> bool:
        """True si ya existe un fingerprint guardado (no es primera carga)."""
        return self._anterior is not None

    # ── comparación ───────────────────────

    def _comparar(
        self,
        actual: SchemaFingerprint,
        anterior: Optional[SchemaFingerprint],
    ) -> ReporteCarga:

        reporte = ReporteCarga(
            timestamp=        actual.timestamp,
            n_filas_actual=   actual.n_filas,
            n_filas_anterior= anterior.n_filas if anterior else None,
            es_primera_carga= anterior is None,
        )

        if anterior is None:
            reporte.nivel = "ok"
            reporte.mensajes.append(
                f"Primera carga registrada — {actual.n_filas} filas, "
                f"{actual.n_columnas} columnas."
            )
            return reporte

        cols_antes  = set(anterior.columnas.keys())
        cols_ahora  = set(actual.columnas.keys())

        # Columnas perdidas
        reporte.columnas_perdidas = sorted(cols_antes - cols_ahora)
        # Columnas nuevas
        reporte.columnas_nuevas   = sorted(cols_ahora - cols_antes)
        # Tipos cambiados — solo en columnas que existen en ambos
        for col in cols_antes & cols_ahora:
            if anterior.columnas[col] != actual.columnas[col]:
                reporte.tipos_cambiados.append(
                    (col, anterior.columnas[col], actual.columnas[col])
                )

        # Caída de filas
        if anterior.n_filas > 0:
            delta = anterior.n_filas - actual.n_filas
            if delta > 0:
                reporte.pct_caida = delta / anterior.n_filas
                reporte.caida_filas = True

        # Construir mensajes y nivel
        self._evaluar_nivel(reporte)

        return reporte

    def _evaluar_nivel(self, reporte: ReporteCarga) -> None:
        """Asigna nivel y mensajes al reporte según lo detectado."""
        nivel = "ok"

        # Columnas críticas perdidas → crítica
        criticas_perdidas = [
            c for c in reporte.columnas_perdidas
            if c in self.columnas_criticas
        ]
        if criticas_perdidas:
            nivel = "critica"
            reporte.mensajes.append(
                f"Columnas críticas desaparecidas: {', '.join(criticas_perdidas)}. "
                f"Los análisis pueden fallar."
            )

        # Columnas no críticas perdidas → advertencia
        no_criticas_perdidas = [
            c for c in reporte.columnas_perdidas
            if c not in self.columnas_criticas
        ]
        if no_criticas_perdidas:
            if nivel == "ok":
                nivel = "advertencia"
            reporte.mensajes.append(
                f"Columnas eliminadas: {', '.join(no_criticas_perdidas)}."
            )

        # Columnas nuevas → info (no sube nivel)
        if reporte.columnas_nuevas:
            reporte.mensajes.append(
                f"Columnas nuevas detectadas: {', '.join(reporte.columnas_nuevas)}."
            )

        # Tipos cambiados → advertencia
        if reporte.tipos_cambiados:
            if nivel == "ok":
                nivel = "advertencia"
            for col, antes, ahora in reporte.tipos_cambiados:
                reporte.mensajes.append(
                    f"Columna '{col}' cambió de tipo {antes} → {ahora}. "
                    f"Puede afectar cálculos numéricos."
                )

        # Caída de filas
        if reporte.caida_filas:
            pct = reporte.pct_caida
            delta = reporte.n_filas_anterior - reporte.n_filas_actual
            if pct >= UMBRAL_CAIDA_CRITICA:
                nivel = "critica"
                reporte.mensajes.append(
                    f"Caída crítica de datos: -{delta} filas ({pct*100:.0f}% menos). "
                    f"Posible falla en la fuente o pipeline."
                )
            elif pct >= UMBRAL_CAIDA_ADVERTENCIA:
                if nivel == "ok":
                    nivel = "advertencia"
                reporte.mensajes.append(
                    f"Menos filas que antes: -{delta} ({pct*100:.0f}% menos). "
                    f"Verificar si el Sheet fue modificado."
                )

        # Sin problemas
        if not reporte.mensajes:
            reporte.mensajes.append(
                f"Schema estable — {reporte.n_filas_actual} filas, "
                f"sin cambios desde la última carga."
            )

        reporte.nivel = nivel

    # ── persistencia ──────────────────────

    def _cargar_fingerprint(self) -> Optional[SchemaFingerprint]:
        if not self.fingerprint_path.exists():
            return None
        try:
            with open(self.fingerprint_path, "r", encoding="utf-8") as f:
                return SchemaFingerprint.from_dict(json.load(f))
        except Exception:
            return None

    def _guardar_fingerprint(self, fp: SchemaFingerprint) -> None:
        try:
            with open(self.fingerprint_path, "w", encoding="utf-8") as f:
                json.dump(fp.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception:
            pass  # silencioso — no debe romper el flujo principal
