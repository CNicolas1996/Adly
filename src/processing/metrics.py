# metrics.py — Adly · Data-Buddy
# Calcula métricas de pauta publicitaria por campaña / adset / ad
# Agnóstico — se adapta a cualquier estructura de columnas via config
# MVP: 9 métricas core + resumen para inyectar al LLM

import pandas as pd
import numpy as np
from typing import Optional


# ─────────────────────────────────────────
# CONFIG POR DEFECTO
# Cada cliente puede pasar su propia config al instanciar MetricsCalculator
# ─────────────────────────────────────────

CONFIG_DEFAULT = {
    "col_campana":   "campana",
    "col_adset":     "adset",
    "col_ad":        "ad",
    "col_leads":     "ghl_id",       # conteo de IDs únicos = leads
    "col_estado":    "estado",
    "col_inversion": "costo_lead",   # costo acumulado por lead
    "col_valor":     "valor_venta",  # ingreso generado
    "estado_mql":    "mql",
    "estado_sql":    "sql",
    "estado_venta":  "venta",
    "moneda":        "COP",
}


# ─────────────────────────────────────────
# CALCULADORA DE MÉTRICAS
# ─────────────────────────────────────────

class MetricsCalculator:
    """
    Calcula las 9 métricas core de Adly MVP por nivel de agrupación.
    Agnóstico — usa config para saber qué columna es qué.

    Métricas:
        1. CPL   — Costo por Lead
        2. CPMQL — Costo por MQL
        3. CPSQL — Costo por SQL
        4. CPA   — Costo por Adquisición (venta)
        5. ROAS  — Retorno sobre inversión
        6. tasa_mql   — % leads que califican como MQL
        7. tasa_sql   — % MQL que califican como SQL
        8. tasa_venta — % SQL que cierran como venta
        9. icl   — Índice de Calidad del Lead (tasa_mql × tasa_sql × tasa_venta)
    """

    def __init__(self, config: dict = None):
        self.config = config or CONFIG_DEFAULT

    def calcular(
        self,
        df: pd.DataFrame,
        nivel: str = "campana"  # campana | adset | ad
    ) -> pd.DataFrame:
        """
        Agrupa los datos por nivel y calcula las 9 métricas.

        Args:
            df:    DataFrame limpio (ya validado por DataValidator)
            nivel: granularidad del análisis

        Returns:
            DataFrame con una fila por grupo y todas las métricas calculadas
        """
        col_grupo = self._col(nivel)
        if col_grupo not in df.columns:
            raise ValueError(f"Columna '{col_grupo}' no encontrada. Revisa la config.")

        # Limpiar tipos antes de calcular
        df = self._limpiar_tipos(df)

        # Agrupar y agregar
        agrupado = self._agrupar(df, col_grupo)

        # Calcular las 9 métricas
        agrupado = self._calcular_metricas(agrupado)

        # Ordenar por CPL ascendente (más eficiente primero)
        if "cpl" in agrupado.columns:
            agrupado = agrupado.sort_values("cpl", ascending=True)

        return agrupado.reset_index(drop=True)

    def resumen_para_llm(
        self,
        df_metricas: pd.DataFrame,
        nivel: str = "campana"
    ) -> str:
        """
        Convierte el DataFrame de métricas en texto estructurado
        para inyectar como contexto al LLM.
        Barato en tokens — solo los números que importan.
        """
        moneda = self.config.get("moneda", "COP")
        col_grupo = self._col(nivel)
        lineas = [
            f"MÉTRICAS POR {nivel.upper()} ({moneda}):",
            "─" * 50,
        ]

        for _, fila in df_metricas.iterrows():
            nombre = fila.get(col_grupo, "Sin nombre")
            lineas.append(f"\n{nombre}:")
            lineas.append(f"  Leads     : {int(fila.get('total_leads', 0))}")
            lineas.append(f"  MQL       : {int(fila.get('total_mql', 0))}")
            lineas.append(f"  SQL       : {int(fila.get('total_sql', 0))}")
            lineas.append(f"  Ventas    : {int(fila.get('total_ventas', 0))}")
            lineas.append(f"  Inversión : ${fila.get('total_inversion', 0):,.0f}")
            lineas.append(f"  Ingreso   : ${fila.get('total_ingreso', 0):,.0f}")
            lineas.append(f"  CPL       : ${fila.get('cpl', 0):,.0f}")
            lineas.append(f"  CPMQL     : ${fila.get('cpmql', 0):,.0f}")
            lineas.append(f"  CPSQL     : ${fila.get('cpsql', 0):,.0f}")
            lineas.append(f"  CPA       : ${fila.get('cpa', 0):,.0f}")
            lineas.append(f"  ROAS      : {fila.get('roas', 0):.2f}")
            lineas.append(f"  Tasa MQL  : {fila.get('tasa_mql', 0):.1%}")
            lineas.append(f"  Tasa SQL  : {fila.get('tasa_sql', 0):.1%}")
            lineas.append(f"  Tasa Venta: {fila.get('tasa_venta', 0):.1%}")
            lineas.append(f"  ICL       : {fila.get('icl', 0):.4f}")

        lineas.append("\n" + "─" * 50)
        return "\n".join(lineas)

    # ── métodos internos ──────────────────

    def _col(self, nivel: str) -> str:
        """Retorna el nombre de columna según el nivel de análisis."""
        mapa = {
            "campana": self.config.get("col_campana", "campana"),
            "adset":   self.config.get("col_adset",   "adset"),
            "ad":      self.config.get("col_ad",      "ad"),
        }
        if nivel not in mapa:
            raise ValueError(f"Nivel inválido: '{nivel}'. Usa: campana | adset | ad")
        return mapa[nivel]

    def _limpiar_tipos(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convierte columnas numéricas que pueden venir como string.
        Ej: "$520,666" → 520666.0
        """
        df = df.copy()
        for col in [self.config["col_inversion"], self.config["col_valor"]]:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(r"[$,\s]", "", regex=True)
                    .replace("None", "0")
                    .replace("nan", "0")
                    .astype(float)
                )
        return df

    def _agrupar(self, df: pd.DataFrame, col_grupo: str) -> pd.DataFrame:
        """
        Agrega datos crudos por grupo.
        Cuenta leads, MQL, SQL, ventas, suma inversión e ingreso.
        """
        col_estado   = self.config["col_estado"]
        col_inversion = self.config["col_inversion"]
        col_valor    = self.config["col_valor"]
        col_id       = self.config["col_leads"]

        estado_mql   = self.config["estado_mql"]
        estado_sql   = self.config["estado_sql"]
        estado_venta = self.config["estado_venta"]

        grupos = []
        for nombre, grupo in df.groupby(col_grupo, dropna=False):
            grupos.append({
                col_grupo:         nombre,
                "total_leads":     len(grupo),
                "total_mql":       (grupo[col_estado] == estado_mql).sum() +
                                   (grupo[col_estado] == estado_sql).sum() +
                                   (grupo[col_estado] == estado_venta).sum(),
                "total_sql":       (grupo[col_estado] == estado_sql).sum() +
                                   (grupo[col_estado] == estado_venta).sum(),
                "total_ventas":    (grupo[col_estado] == estado_venta).sum(),
                "total_inversion": grupo[col_inversion].sum(),
                "total_ingreso":   grupo[col_valor].sum(),
            })

        return pd.DataFrame(grupos)

    def _calcular_metricas(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula las 9 métricas sobre el DataFrame agrupado.
        Maneja división por cero con np.where.
        """
        df = df.copy()

        inv    = df["total_inversion"]
        leads  = df["total_leads"]
        mql    = df["total_mql"]
        sql    = df["total_sql"]
        ventas = df["total_ventas"]
        ingreso = df["total_ingreso"]

        # ── 4 métricas de costo ──
        df["cpl"]   = np.where(leads  > 0, inv / leads,  0)  # Costo por Lead
        df["cpmql"] = np.where(mql    > 0, inv / mql,    0)  # Costo por MQL
        df["cpsql"] = np.where(sql    > 0, inv / sql,    0)  # Costo por SQL
        df["cpa"]   = np.where(ventas > 0, inv / ventas, 0)  # Costo por Adquisición

        # ── 1 métrica de retorno ──
        df["roas"]  = np.where(inv > 0, ingreso / inv, 0)    # Retorno sobre inversión

        # ── 3 tasas de conversión ──
        df["tasa_mql"]   = np.where(leads > 0, mql    / leads, 0)  # Lead → MQL
        df["tasa_sql"]   = np.where(mql   > 0, sql    / mql,   0)  # MQL  → SQL
        df["tasa_venta"] = np.where(sql   > 0, ventas / sql,   0)  # SQL  → Venta

        # ── 1 índice compuesto ──
        # ICL — Índice de Calidad del Lead
        # Producto de las 3 tasas — penaliza fuerte si cualquiera es 0
        df["icl"] = df["tasa_mql"] * df["tasa_sql"] * df["tasa_venta"]

        # Redondear para presentación limpia
        cols_pesos = ["cpl", "cpmql", "cpsql", "cpa", "roas"]
        df[cols_pesos] = df[cols_pesos].round(2)

        cols_tasas = ["tasa_mql", "tasa_sql", "tasa_venta", "icl"]
        df[cols_tasas] = df[cols_tasas].round(4)

        return df


# ─────────────────────────────────────────
# MAIN — probar con mock data
# ─────────────────────────────────────────

if __name__ == "__main__":
    import pandas as pd
    from src.ingestion.mock_data import generar_datos_ghl

    print(">> Calculando métricas con mock data...\n")

    df = generar_datos_ghl(n_leads=100)
    calc = MetricsCalculator(config=CONFIG_DEFAULT)

    # Por campaña
    print("── POR CAMPAÑA ──")
    metricas = calc.calcular(df, nivel="campana")
    print(metricas[["campana", "total_leads", "total_mql", "cpl", "cpmql", "roas", "icl"]].to_string(index=False))

    # Resumen para LLM
    print("\n── RESUMEN PARA LLM ──")
    print(calc.resumen_para_llm(metricas, nivel="campana"))

    # Por adset
    print("\n── POR ADSET ──")
    metricas_adset = calc.calcular(df, nivel="adset")
    print(metricas_adset[["adset", "total_leads", "cpl", "roas"]].to_string(index=False))