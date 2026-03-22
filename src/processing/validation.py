
# validation.py — Adly · Data-Buddy
# Pipeline de validación de integridad de datos
# Compara GHL (fuente de verdad) vs Sheet (espejo)

import pandas as pd
from dataclasses import dataclass, field
from typing import List
import os


# ─────────────────────────────────────────
# RESULTADO DE VALIDACIÓN — estructura de datos
# ─────────────────────────────────────────

@dataclass
class ResultadoValidacion:
    """
    Encapsula el resultado completo de una validación.
    Dataclass — como una clase normal pero más limpia para
    objetos que solo almacenan datos.
    """
    total_ghl:       int = 0
    total_sheet:     int = 0
    faltantes:       List[str] = field(default_factory=list)  # en GHL pero no en Sheet
    duplicados:      List[str] = field(default_factory=list)  # repetidos en Sheet
    campos_vacios:   dict = field(default_factory=dict)       # columna → lista de IDs
    estados_diff:    List[str] = field(default_factory=list)  # estado distinto entre fuentes
    score:           float = 0.0                              # % de integridad (0-100)

    def resumen(self) -> str:
        lineas = [
            f"\n{'='*50}",
            f"  REPORTE DE INTEGRIDAD DE DATOS",
            f"{'='*50}",
            f"  GHL (fuente de verdad) : {self.total_ghl} registros",
            f"  Sheet (espejo)         : {self.total_sheet} registros",
            f"{'─'*50}",
            f"  Faltantes en Sheet     : {len(self.faltantes)}",
            f"  Duplicados en Sheet    : {len(self.duplicados)}",
            f"  Estados desactualizados: {len(self.estados_diff)}",
        ]

        for col, ids in self.campos_vacios.items():
            lineas.append(f"  Vacíos en '{col}'       : {len(ids)}")

        lineas += [
            f"{'─'*50}",
            f"  Score de integridad    : {self.score:.1f}%",
            f"{'='*50}",
        ]

        if self.score == 100:
            lineas.append("  ✓ Datos limpios — sin inconsistencias")
        elif self.score >= 90:
            lineas.append("  ⚠ Integridad aceptable — revisar faltantes")
        else:
            lineas.append("  ✗ Integridad baja — se requiere corrección")

        lineas.append(f"{'='*50}\n")
        return "\n".join(lineas)


# ─────────────────────────────────────────
# VALIDADOR PRINCIPAL
# ─────────────────────────────────────────

class DataValidator:
    """
    Compara dos fuentes de datos y detecta inconsistencias.
    GHL es siempre la fuente de verdad.
    Sheet es el espejo que debe ser idéntico.

    Detecta:
    - Registros faltantes (en GHL pero no en Sheet)
    - Registros duplicados (repetidos en Sheet)
    - Campos vacíos en columnas clave
    - Estados desactualizados entre fuentes
    """

    COLUMNAS_CLAVE = ["campana", "adset", "costo_lead"]

    def __init__(self, col_id: str = "ghl_id", col_estado: str = "estado"):
        """
        Args:
            col_id:     nombre de la columna ID único (ancla de comparación)
            col_estado: nombre de la columna de estado del lead
        """
        self.col_id     = col_id
        self.col_estado = col_estado

    def validar(self, df_ghl: pd.DataFrame, df_sheet: pd.DataFrame) -> ResultadoValidacion:
        """
        Ejecuta la validación completa y retorna un ResultadoValidacion.
        Este es el método principal — orquesta todos los checks.
        """
        resultado = ResultadoValidacion(
            total_ghl   = len(df_ghl),
            total_sheet = len(df_sheet),
        )

        resultado.faltantes     = self._detectar_faltantes(df_ghl, df_sheet)
        resultado.duplicados    = self._detectar_duplicados(df_sheet)
        resultado.campos_vacios = self._detectar_campos_vacios(df_sheet)
        resultado.estados_diff  = self._detectar_estados_distintos(df_ghl, df_sheet)
        resultado.score         = self._calcular_score(resultado)

        return resultado

    # ── checks individuales ───────────────

    def _detectar_faltantes(self, df_ghl: pd.DataFrame, df_sheet: pd.DataFrame) -> List[str]:
        """IDs que están en GHL pero no llegaron al Sheet."""
        ids_ghl   = set(df_ghl[self.col_id].astype(str))
        ids_sheet = set(df_sheet[self.col_id].astype(str))
        return list(ids_ghl - ids_sheet)

    def _detectar_duplicados(self, df_sheet: pd.DataFrame) -> List[str]:
        """IDs que aparecen más de una vez en el Sheet."""
        duplicados = df_sheet[df_sheet[self.col_id].duplicated(keep=False)]
        return list(duplicados[self.col_id].astype(str).unique())

    def _detectar_campos_vacios(self, df_sheet: pd.DataFrame) -> dict:
        """
        Detecta campos vacíos en columnas clave.
        Retorna dict: columna → lista de IDs afectados.
        Solo analiza columnas que existen en el DataFrame.
        """
        resultado = {}
        cols_existentes = [c for c in self.COLUMNAS_CLAVE if c in df_sheet.columns]

        for col in cols_existentes:
            vacios = df_sheet[df_sheet[col].isnull() | (df_sheet[col] == "")]
            if not vacios.empty:
                resultado[col] = list(vacios[self.col_id].astype(str))

        return resultado

    def _detectar_estados_distintos(self, df_ghl: pd.DataFrame, df_sheet: pd.DataFrame) -> List[str]:
        """
        Detecta leads donde el estado en Sheet difiere del estado en GHL.
        Indica sincronización tardía o errores de n8n.
        """
        if self.col_estado not in df_ghl.columns or self.col_estado not in df_sheet.columns:
            return []

        # Merge por ID — solo los que existen en ambos
        merged = df_ghl[[self.col_id, self.col_estado]].merge(
            df_sheet[[self.col_id, self.col_estado]],
            on=self.col_id,
            suffixes=("_ghl", "_sheet")
        )

        distintos = merged[merged[f"{self.col_estado}_ghl"] != merged[f"{self.col_estado}_sheet"]]
        return list(distintos[self.col_id].astype(str))

    def _calcular_score(self, r: ResultadoValidacion) -> float:
        """
        Calcula el score de integridad de 0 a 100.
        100 = datos perfectamente sincronizados.
        Penaliza más los faltantes que los campos vacíos.
        """
        if r.total_ghl == 0:
            return 0.0

        total_errores = (
            len(r.faltantes)   * 2 +   # peso alto — dato perdido
            len(r.duplicados)  * 1 +   # peso medio — dato duplicado
            len(r.estados_diff) * 1    # peso medio — dato desactualizado
        )

        # Campos vacíos — suma todos los afectados
        for ids in r.campos_vacios.values():
            total_errores += len(ids) * 0.5

        score = max(0.0, 100.0 - (total_errores / r.total_ghl * 100))
        return round(score, 2)


# ─────────────────────────────────────────
# MAIN — probar validación con mock data
# ─────────────────────────────────────────

if __name__ == "__main__":
    print(">> Ejecutando validación de integridad...\n")

    # Cargar ambas fuentes
    ruta_ghl   = "data/raw/mock_ghl.csv"
    ruta_sheet = "data/raw/mock_sheet.csv"

    if not os.path.exists(ruta_ghl) or not os.path.exists(ruta_sheet):
        print("[ERROR] No se encontraron los datos de prueba.")
        print("Corre primero: python src/ingestion/mock_data.py")
        exit(1)

    df_ghl   = pd.read_csv(ruta_ghl)
    df_sheet = pd.read_csv(ruta_sheet)

    # Validar
    validador  = DataValidator()
    resultado  = validador.validar(df_ghl, df_sheet)

    # Mostrar reporte
    print(resultado.resumen())

    # Detalle de faltantes
    if resultado.faltantes:
        print(f"IDs faltantes (primeros 5): {resultado.faltantes[:5]}")

    # Detalle de duplicados
    if resultado.duplicados:
        print(f"IDs duplicados: {resultado.duplicados[:5]}")