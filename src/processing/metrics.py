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
        nivel: str = "campana",
        _muestra_pequena: bool = False
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
            lineas.append(f"  Tasa MQL  : {fila.get('tasa_mql', 0):.1%}{' ⚠️ muestra pequeña — tasa no confiable' if _muestra_pequena else ''}")
            lineas.append(f"  Tasa SQL  : {fila.get('tasa_sql', 0):.1%}{' ⚠️ muestra pequeña — tasa no confiable' if _muestra_pequena else ''}")
            lineas.append(f"  Tasa Venta: {fila.get('tasa_venta', 0):.1%}{' ⚠️ muestra pequeña — tasa no confiable' if _muestra_pequena else ''}")
            lineas.append(f"  ICL       : {fila.get('icl', 0):.4f}")

        lineas.append("\n" + "─" * 50)
        return "\n".join(lineas)

    def resumen_schema(self, df: pd.DataFrame) -> str:
        """
        Retorna string con información de cada columna del DataFrame raw.
        Se inyecta junto con resumen_para_llm() en el engine para que
        el LLM sepa qué columnas existen más allá de las métricas derivadas.

        Formato por columna:
          - Nombre, tipo, % nulos
          - Numérica: rango min/max + 1 ejemplo
          - Categórica: top valores con % + 1 ejemplo
          - Datetime: rango fechas + 1 ejemplo
        """
        moneda = self.config.get("moneda", "COP")
        cols_monetarias = {
            self.config.get("col_inversion", "costo_lead"),
            self.config.get("col_valor",     "valor_venta"),
        }

        lineas = ["COLUMNAS DISPONIBLES:", "─" * 50]

        for col in df.columns:
            serie = df[col]
            total = len(serie)
            n_nulos = serie.isna().sum()
            pct_nulos = n_nulos / total * 100 if total > 0 else 0

            # Detectar tipo semántico
            dtype = serie.dtype

            # Intentar detectar datetime si es object
            es_datetime = False
            if dtype == object:
                muestra = serie.dropna().head(20)
                try:
                    pd.to_datetime(muestra, errors="raise")
                    es_datetime = True
                except Exception:
                    pass
            elif pd.api.types.is_datetime64_any_dtype(serie):
                es_datetime = True

            nulos_str = f"{pct_nulos:.1f}% nulos" if pct_nulos > 0 else "0% nulos"

            if es_datetime:
                try:
                    serie_dt = pd.to_datetime(serie, errors="coerce").dropna()
                    min_f = serie_dt.min().strftime("%Y-%m-%d")
                    max_f = serie_dt.max().strftime("%Y-%m-%d")
                    ej    = serie_dt.sample(1).iloc[0].strftime("%Y-%m-%d") if len(serie_dt) > 0 else "—"
                    lineas.append(f"─ {col}: datetime, {nulos_str}, rango {min_f} a {max_f}, ej: {ej}")
                except Exception:
                    lineas.append(f"─ {col}: datetime, {nulos_str}")

            elif pd.api.types.is_numeric_dtype(dtype):
                serie_num = serie.dropna()
                if len(serie_num) == 0:
                    lineas.append(f"─ {col}: numérico, {nulos_str}, sin valores")
                    continue
                tipo_str = "float" if dtype in [float, "float64", "float32"] else "int"
                min_v = serie_num.min()
                max_v = serie_num.max()
                ej    = serie_num.sample(1).iloc[0]
                if col in cols_monetarias:
                    lineas.append(
                        f"─ {col}: {tipo_str}, {nulos_str}, "
                        f"rango ${min_v:,.2f}-${max_v:,.2f} {moneda}, "
                        f"ej: ${ej:,.2f}"
                    )
                else:
                    lineas.append(
                        f"─ {col}: {tipo_str}, {nulos_str}, "
                        f"rango {min_v:g}-{max_v:g}, "
                        f"ej: {ej:g}"
                    )

            else:
                # String / categórica
                serie_str = serie.dropna().astype(str)
                n_unicos  = serie_str.nunique()
                ej        = serie_str.sample(1).iloc[0] if len(serie_str) > 0 else "—"

                # Si hay pocos valores únicos → mostrar distribución
                if n_unicos <= 8:
                    conteos  = serie_str.value_counts(normalize=True).head(5)
                    top_vals = ", ".join(
                        f"{v} ({p:.0%})" for v, p in conteos.items()
                    )
                    lineas.append(
                        f"─ {col}: string, {nulos_str}, "
                        f"valores: {top_vals}, ej: {ej}"
                    )
                else:
                    lineas.append(
                        f"─ {col}: string, {nulos_str}, "
                        f"{n_unicos} valores únicos, ej: {ej}"
                    )

        lineas.append("─" * 50)
        return "\n".join(lineas)


    def resumen_ejecutivo_llm(self, df_raw: pd.DataFrame, _muestra_pequena: bool = False) -> str:
        """
        Resumen ejecutivo comprimido para el LLM — máximo ~1500 chars / ~375 tokens.

        A diferencia de resumen_para_llm() que genera una fila por grupo
        (puede ser cientos con datos sucios), este método calcula directamente
        desde el df raw con pandas y retorna solo lo que el LLM necesita para
        responder preguntas de marketing.

        Reemplaza resumen_para_llm() como contexto del system prompt.
        resumen_para_llm() sigue disponible para uso interno y comandos CLI.

        Fase 3 (Queryn/RAG): este método se convierte en el índice del RAG —
        cada sección se vectoriza por separado para recuperación selectiva.
        """
        moneda = self.config.get("moneda", "COP")
        col_camp   = self.config.get("col_campana",  "campana")
        col_estado = self.config.get("col_estado",   "estado")
        col_inver  = self.config.get("col_inversion","costo_lead")
        col_valor  = self.config.get("col_valor",    "valor_venta")

        lineas = [f"RESUMEN EJECUTIVO ({moneda}) — {len(df_raw)} registros totales"]
        lineas.append("─" * 50)

        # ── Embudo global ──────────────────────────────────────
        if col_estado in df_raw.columns:
            estados = df_raw[col_estado].dropna().str.lower().str.strip()
            # Normalizar variantes sucias
            # Base canonical mapping (always applies)
            NORM_BASE = {
                "lead": "lead", "leads": "lead",
                "mql": "mql",
                "sql": "sql",
                "venta": "venta", "ventas": "venta", "sold": "venta",
                "perdido": "perdido", "perdidos": "perdido",
            }
            # Dynamic extension from config — maps the real client value
            estado_venta_config = self.config.get("estado_venta", "venta").lower().strip()
            estado_mql_config   = self.config.get("estado_mql",   "mql").lower().strip()
            estado_sql_config   = self.config.get("estado_sql",   "sql").lower().strip()

            NORM = {
                **NORM_BASE,
                estado_venta_config: "venta",
                estado_mql_config:   "mql",
                estado_sql_config:   "sql",
            }
            estados_norm = estados.map(lambda x: NORM.get(x, x))
            conteo = estados_norm.value_counts()
            n_nulos = df_raw[col_estado].isna().sum()
            lineas.append(f"EMBUDO GLOBAL:")
            for est in ["lead", "mql", "sql", "venta", "perdido"]:
                n = conteo.get(est, 0)
                if n > 0:
                    lineas.append(f"  {est.upper()}: {n}")
            otros = {k: v for k, v in conteo.items()
                     if k not in ["lead","mql","sql","venta","perdido"]}
            if otros:
                lineas.append(f"  Otros/sucios: {sum(otros.values())} ({list(otros.keys())})")
            if n_nulos > 0:
                lineas.append(f"  Sin estado: {n_nulos}")
            total_leads = conteo.get("lead", 0)
            total_ventas = conteo.get("venta", 0)
            if total_leads > 0:
                tasa_global = f"{total_ventas/total_leads:.1%}"
                warning = f" ⚠️ muestra pequeña (n={total_leads}) — tasa no confiable" if _muestra_pequena else ""
                lineas.append(f"  Tasa conversión global: {tasa_global}{warning}")

        # ── Por campaña ───────────────────────────────────────
        if col_camp in df_raw.columns and col_estado in df_raw.columns:
            lineas.append(f"POR CAMPAÑA:")
            campanas = df_raw[col_camp].dropna().unique()
            for camp in campanas[:5]:  # máx 5 campañas
                sub = df_raw[df_raw[col_camp] == camp]
                n_total = len(sub)
                if col_estado in sub.columns:
                    estados_sub = sub[col_estado].dropna().str.lower().str.strip()
                    estados_sub = estados_sub.map(lambda x: NORM.get(x, x))
                    n_leads  = (estados_sub == "lead").sum()
                    n_ventas = (estados_sub == "venta").sum()
                    tasa = f"{n_ventas/n_total:.1%}" if n_total > 0 else "0%"
                    warning = f" ⚠️ muestra pequeña (n={n_total}) — tasa no confiable" if _muestra_pequena else ""
                    lineas.append(f"  {camp}: {n_total} reg | leads:{n_leads} ventas:{n_ventas} tasa:{tasa}{warning}")
                else:
                    lineas.append(f"  {camp}: {n_total} registros")
            n_sin_camp = df_raw[col_camp].isna().sum()
            if n_sin_camp > 0:
                lineas.append(f"  Sin campaña: {n_sin_camp} registros")

        # ── Costo ─────────────────────────────────────────────
        if col_inver in df_raw.columns:
            serie = df_raw[col_inver].dropna()
            n_neg = (serie < 0).sum()
            lineas.append(f"COSTO ({col_inver}):")
            lineas.append(f"  Total: ${serie[serie >= 0].sum():,.0f} | Promedio: ${serie[serie >= 0].mean():,.0f}")
            if n_neg > 0:
                lineas.append(f"  ALERTA: {n_neg} valores negativos — excluidos del cálculo")

        # ── Fechas ────────────────────────────────────────────
        col_fecha = None
        for c in df_raw.columns:
            if "fecha" in c.lower() or "date" in c.lower():
                col_fecha = c
                break
        if col_fecha:
            try:
                fechas = pd.to_datetime(df_raw[col_fecha], errors="coerce").dropna()
                lineas.append(f"PERÍODO: {fechas.min().strftime('%Y-%m-%d')} a {fechas.max().strftime('%Y-%m-%d')}")
            except Exception:
                pass

        lineas.append("─" * 50)
        resultado = "\n".join(lineas)
        return resultado

    # ── métodos internos ──────────────────

    def _col(self, nivel: str) -> str:
        """Retorna el nombre de columna según el nivel de análisis."""
        mapa = {
            "campana": self.config.get("col_campana") or "campana",
            "adset":   self.config.get("col_adset") or "adset",
            "ad":      self.config.get("col_ad") or "ad",
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
        for col in [self.config.get("col_inversion"), self.config.get("col_valor")]:
            if col and col in df.columns:
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
        col_estado   = self.config.get("col_estado")
        col_inversion = self.config.get("col_inversion")
        col_valor    = self.config.get("col_valor")
        col_id       = self.config.get("col_leads")

        estado_mql   = self.config.get("estado_mql", "mql")
        estado_sql   = self.config.get("estado_sql", "sql")
        estado_venta = self.config.get("estado_venta", "venta")

        grupos = []
        n_antes = len(df)
        
        # Si col_grupo no existe, agrupar todo en una sola fila "Global"
        if not col_grupo or col_grupo not in df.columns:
            df["_global_group"] = "Global"
            col_grupo = "_global_group"
            
        df = df[df[col_grupo].notna()].copy()
        self._excluidos_sin_grupo = n_antes - len(df)

        for nombre, grupo in df.groupby(col_grupo):
            # Fallbacks seguros si col_estado es None o no existe
            mql_count = 0
            sql_count = 0
            venta_count = 0
            if col_estado and col_estado in grupo.columns:
                mql_count = (grupo[col_estado] == estado_mql).sum()
                sql_count = (grupo[col_estado] == estado_sql).sum()
                venta_count = (grupo[col_estado] == estado_venta).sum()

            inversion_sum = 0
            if col_inversion and col_inversion in grupo.columns:
                inversion_sum = grupo[col_inversion].sum()

            ingreso_sum = 0
            if col_valor and col_valor in grupo.columns:
                ingreso_sum = grupo[col_valor].sum()

            grupos.append({
                col_grupo:         nombre,
                "total_leads":     len(grupo),
                "total_mql":       mql_count + sql_count + venta_count,
                "total_sql":       sql_count + venta_count,
                "total_ventas":    venta_count,
                "total_inversion": inversion_sum,
                "total_ingreso":   ingreso_sum,
            })

        # Si usamos el grupo global, renombrar para que devuelva algo con sentido
        df_grupos = pd.DataFrame(grupos)
        if col_grupo == "_global_group":
            df_grupos = df_grupos.rename(columns={"_global_group": "campana"})
            
        return df_grupos

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

    # Schema
    print("\n── SCHEMA RAW ──")
    print(calc.resumen_schema(df))

    # Por adset
    print("\n── POR ADSET ──")
    metricas_adset = calc.calcular(df, nivel="adset")
    print(metricas_adset[["adset", "total_leads", "cpl", "roas"]].to_string(index=False))
