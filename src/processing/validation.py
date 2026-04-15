
# validation.py — Adly · Data-Buddy
# Pipeline de validación de integridad de datos
# Compara GHL (fuente de verdad) vs Sheet (espejo)

import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional
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

    Limpia:
    - limpiar_duplicados()      → elimina filas duplicadas por col_id
    - rellenar_nulos()          → rellena NaN en columna específica
    - eliminar_por_criterio()   → filtra filas por condición
    """

    # Default — se puede sobreescribir en __init__
    _COLUMNAS_CLAVE_DEFAULT = ["campana", "adset", "costo_lead"]

    def __init__(
        self,
        col_id: str = "ghl_id",
        col_estado: str = "estado",
        columnas_clave: Optional[List[str]] = None,
    ):
        """
        Args:
            col_id:         nombre de la columna ID único (ancla de comparación)
            col_estado:     nombre de la columna de estado del lead
            columnas_clave: columnas a revisar por campos vacíos.
                            Si es None usa ["campana", "adset", "costo_lead"].
                            Pasar lista explícita si el CSV tiene otras columnas.
        """
        self.col_id        = col_id
        self.col_estado    = col_estado
        self.columnas_clave = columnas_clave if columnas_clave is not None \
                              else list(self._COLUMNAS_CLAVE_DEFAULT)

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

    # ── cleanup methods ───────────────────

    def limpiar_duplicados(
        self,
        df: pd.DataFrame,
        keep: str = "first",
    ) -> tuple:
        """
        Elimina filas duplicadas por col_id.

        Args:
            df:   DataFrame a limpiar
            keep: 'first' (conserva primera ocurrencia) |
                  'last'  (conserva última) |
                  False   (elimina todas las ocurrencias duplicadas)

        Returns:
            (df_limpio, reporte)
            reporte = {"eliminados": N, "ejemplos_ids": [...]}
        """
        if self.col_id not in df.columns:
            return df, {"eliminados": 0, "ejemplos_ids": [], "error": f"Columna '{self.col_id}' no existe"}

        # Filas que son duplicadas (no la que se conserva)
        mascara_duplicadas = df[self.col_id].duplicated(keep=keep)
        ids_eliminados     = list(df.loc[mascara_duplicadas, self.col_id].astype(str).unique())
        n_eliminados       = mascara_duplicadas.sum()

        df_limpio = df[~mascara_duplicadas].reset_index(drop=True)

        reporte = {
            "eliminados":   int(n_eliminados),
            "ejemplos_ids": ids_eliminados[:5],  # máx 5 ejemplos
        }
        return df_limpio, reporte

    def rellenar_nulos(
        self,
        df: pd.DataFrame,
        columna: str,
        estrategia: str = "media",
        valor_custom=None,
    ) -> tuple:
        """
        Rellena valores nulos en una columna específica.

        Args:
            df:           DataFrame
            columna:      nombre de columna a rellenar
            estrategia:   "media"       — promedio (solo numéricas)
                          "mediana"     — mediana (solo numéricas)
                          "moda"        — valor más frecuente (cualquier tipo)
                          "valor_custom"— usa valor_custom
            valor_custom: valor a usar cuando estrategia="valor_custom"

        Returns:
            (df_rellenado, reporte)
            reporte = {"rellenados": N, "estrategia": ..., "valor_usado": ...}
        """
        if columna not in df.columns:
            return df, {"rellenados": 0, "error": f"Columna '{columna}' no existe"}

        df = df.copy()
        n_nulos_antes = df[columna].isna().sum()

        if n_nulos_antes == 0:
            return df, {"rellenados": 0, "estrategia": estrategia, "valor_usado": None}

        serie = df[columna]
        es_numerica = pd.api.types.is_numeric_dtype(serie)

        if estrategia == "media":
            if not es_numerica:
                return df, {"rellenados": 0, "error": f"'media' solo aplica a columnas numéricas. '{columna}' es {serie.dtype}"}
            valor = serie.mean()
        elif estrategia == "mediana":
            if not es_numerica:
                return df, {"rellenados": 0, "error": f"'mediana' solo aplica a columnas numéricas. '{columna}' es {serie.dtype}"}
            valor = serie.median()
        elif estrategia == "moda":
            moda = serie.mode()
            valor = moda.iloc[0] if len(moda) > 0 else None
        elif estrategia == "valor_custom":
            valor = valor_custom
        else:
            return df, {"rellenados": 0, "error": f"Estrategia '{estrategia}' no reconocida. Usa: media|mediana|moda|valor_custom"}

        if valor is None:
            return df, {"rellenados": 0, "error": "No se pudo calcular el valor de relleno"}

        df[columna] = df[columna].fillna(valor)
        n_rellenados = n_nulos_antes - df[columna].isna().sum()

        reporte = {
            "rellenados":   int(n_rellenados),
            "estrategia":   estrategia,
            "valor_usado":  valor,
        }
        return df, reporte

    def eliminar_por_criterio(
        self,
        df: pd.DataFrame,
        columna: str,
        operador: str,
        valor=None,
    ) -> tuple:
        """
        Elimina filas que NO cumplen un criterio (o que sí cumplen, según contexto).
        Semántica: "elimina filas donde columna operador valor es True".

        Args:
            df:       DataFrame
            columna:  nombre de columna
            operador: "==" | "!=" | ">" | "<" | ">=" | "<=" | "isnull" | "notnull"
            valor:    valor de comparación (ignorado si operador es isnull/notnull)

        Returns:
            (df_filtrado, reporte)
            reporte = {"eliminados": N, "criterio": "columna op valor"}

        Ejemplo:
            # Elimina filas donde costo_lead <= 0
            df_limpio, r = validator.eliminar_por_criterio(df, "costo_lead", "<=", 0)
        """
        if columna not in df.columns:
            return df, {"eliminados": 0, "error": f"Columna '{columna}' no existe"}

        OPERADORES = {"==", "!=", ">", "<", ">=", "<=", "isnull", "notnull"}
        if operador not in OPERADORES:
            return df, {"eliminados": 0, "error": f"Operador '{operador}' no válido. Usa: {sorted(OPERADORES)}"}

        serie = df[columna]

        try:
            if operador == "==":
                mascara = serie == valor
            elif operador == "!=":
                mascara = serie != valor
            elif operador == ">":
                mascara = serie > valor
            elif operador == "<":
                mascara = serie < valor
            elif operador == ">=":
                mascara = serie >= valor
            elif operador == "<=":
                mascara = serie <= valor
            elif operador == "isnull":
                mascara = serie.isna()
            elif operador == "notnull":
                mascara = serie.notna()
        except Exception as e:
            return df, {"eliminados": 0, "error": f"Error aplicando criterio: {e}"}

        n_eliminados = int(mascara.sum())
        df_filtrado  = df[~mascara].reset_index(drop=True)

        criterio = f"{columna} {operador}" + (f" {valor}" if operador not in ("isnull", "notnull") else "")
        reporte  = {
            "eliminados": n_eliminados,
            "criterio":   criterio,
        }
        return df_filtrado, reporte

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
        cols_existentes = [c for c in self.columnas_clave if c in df_sheet.columns]

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

    # Validar — columnas_clave dinámico
    validador  = DataValidator(columnas_clave=["campana", "adset", "costo_lead"])
    resultado  = validador.validar(df_ghl, df_sheet)
    print(resultado.resumen())

    # Probar limpiar_duplicados
    if resultado.duplicados:
        print(f"IDs duplicados detectados: {resultado.duplicados[:5]}")
        df_limpio, reporte = validador.limpiar_duplicados(df_sheet)
        print(f"[limpiar_duplicados] Eliminados: {reporte['eliminados']} | Ejemplos: {reporte['ejemplos_ids']}")
    else:
        print("Sin duplicados.")

    # Probar rellenar_nulos en costo_lead
    df_rel, rep_rel = validador.rellenar_nulos(df_sheet, "costo_lead", estrategia="media")
    print(f"[rellenar_nulos] Rellenados: {rep_rel.get('rellenados',0)} con media={rep_rel.get('valor_usado','—'):.2f}" if rep_rel.get("rellenados") else "[rellenar_nulos] Sin nulos en costo_lead")

    # Probar eliminar_por_criterio
    df_filt, rep_filt = validador.eliminar_por_criterio(df_sheet, "costo_lead", "<=", 0)
    print(f"[eliminar_por_criterio] Criterio: '{rep_filt['criterio']}' | Eliminados: {rep_filt['eliminados']}")
