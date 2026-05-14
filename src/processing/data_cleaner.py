# data_cleaner.py — Adly · Data-Buddy
# Loop interactivo de limpieza guiada por DataQualityReport.
#
# Principio rector:
#   Opera sobre TIPOS DE PROBLEMA, nunca sobre nombres de columna.
#   Las decisiones son del usuario — Adly ejecuta con transparencia.
#   Nunca destruye datos sin confirmación. Siempre muestra qué cambió.
#
# Flujo:
#   CleaningSession.start(report)
#   → session.next_issue()          # siguiente problema sin resolver
#   → session.options()             # opciones disponibles para ese problema
#   → session.apply(decision)       # ejecutar decisión → CleaningResult
#   → session.next_issue()          # loop hasta done()
#   → session.done()                # True cuando no quedan issues
#   → session.final_df              # df limpio con todas las decisiones aplicadas
#   → session.decisions_log         # log de qué se hizo y por qué
#
# Firma pública — no cambiar sin versionar:
#   CleaningSession.start(report)   → CleaningSession
#   session.next_issue()            → Issue | None
#   session.apply(opcion_id)        → CleaningResult
#   session.skip()                  → None  (salta el issue actual)
#   session.done()                  → bool
#   session.final_df                → pd.DataFrame
#   session.summary()               → str

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

import pandas as pd

logger = logging.getLogger("adly.data_cleaner")


# ─────────────────────────────────────────────────────────────
# ESTRUCTURAS DE DATOS
# ─────────────────────────────────────────────────────────────

@dataclass
class Option:
    """Una opción de limpieza presentable al usuario."""
    id:          str    # "1", "2", "3"... lo que el usuario tipea
    label:       str    # texto corto para el menú
    descripcion: str    # explicación de qué hace exactamente
    es_destructiva: bool = False  # True = elimina filas/columnas


@dataclass
class Issue:
    """Un problema de calidad detectado, listo para presentar al usuario."""
    tipo:        str        # duplicados | email_roto | phone_sin_prefijo |
                            # multivalue_1fn | nulos | forma_normal_2FN
    columna:     str        # columna(s) afectada(s) — puede ser lista serializada
    impacto:     float      # % de registros afectados (0-100)
    descripcion: str        # texto en lenguaje natural para el usuario
    ejemplos:    list       # valores concretos del dataset para contextualizar
    opciones:    list[Option] = field(default_factory=list)
    metadata:    dict       = field(default_factory=dict)  # datos del report original


@dataclass
class CleaningResult:
    """Resultado de aplicar una decisión de limpieza."""
    issue_tipo:      str
    columna:         str
    opcion_aplicada: str
    filas_antes:     int
    filas_despues:   int
    filas_afectadas: int
    descripcion:     str        # qué se hizo en lenguaje natural
    df:              object     # pd.DataFrame resultante
    columnas_nuevas: list = field(default_factory=list)  # cols agregadas


# ─────────────────────────────────────────────────────────────
# CONSTRUCTORES DE OPCIONES — agnósticos por tipo de problema
# Cada función recibe el Issue y el df actual, devuelve lista de Option.
# ─────────────────────────────────────────────────────────────

def _opciones_duplicados(issue: Issue, df: pd.DataFrame) -> list[Option]:
    col = issue.columna
    return [
        Option("1", "Más reciente",
               f"Para cada correo duplicado, conservar el registro con fecha más reciente. "
               f"Se eliminan {issue.metadata.get('filas_afectadas',0) - issue.metadata.get('valores_duplicados',0)} filas.",
               es_destructiva=True),
        Option("2", "Más completo",
               "Conservar el registro con más campos no-nulos por grupo duplicado.",
               es_destructiva=True),
        Option("3", "Marcar sin borrar",
               f"Agregar columna 'es_duplicado' (True/False). No se elimina ninguna fila. "
               f"Recomendado si quieres revisar manualmente.",
               es_destructiva=False),
        Option("4", "Ver ejemplos",
               "Mostrar los primeros 5 grupos duplicados antes de decidir.",
               es_destructiva=False),
        Option("s", "Saltar",
               "Dejar los duplicados como están y pasar al siguiente problema.",
               es_destructiva=False),
    ]


def _opciones_email_roto(issue: Issue, df: pd.DataFrame) -> list[Option]:
    return [
        Option("1", "Marcar inválidos",
               "Agregar columna 'email_valido' (True/False). No se modifica el email original.",
               es_destructiva=False),
        Option("2", "Mover a columna raw",
               "Renombrar columna actual a 'email_raw', crear 'email_limpio' solo con los válidos. "
               "Los inválidos quedan en email_raw para auditoría.",
               es_destructiva=False),
        Option("3", "Eliminar filas con email roto",
               f"Eliminar las {issue.metadata.get('local_invalido',0) + issue.metadata.get('multi_at',0) + issue.metadata.get('dominio_roto',0)} filas con email inválido.",
               es_destructiva=True),
        Option("4", "Ver ejemplos",
               "Mostrar los primeros 10 emails rotos antes de decidir.",
               es_destructiva=False),
        Option("s", "Saltar", "Pasar al siguiente problema.", es_destructiva=False),
    ]


def _opciones_phone(issue: Issue, df: pd.DataFrame) -> list[Option]:
    return [
        Option("1", "Agregar prefijo por defecto",
               "Pedir un prefijo (ej: +1 para USA, +57 para Colombia) y aplicarlo "
               "a todos los teléfonos sin '+'. Reversible.",
               es_destructiva=False),
        Option("2", "Marcar sin prefijo",
               "Agregar columna 'telefono_valido' (True/False). No modifica el número.",
               es_destructiva=False),
        Option("3", "Ver ejemplos",
               "Mostrar los primeros 10 teléfonos sin prefijo.",
               es_destructiva=False),
        Option("s", "Saltar", "Pasar al siguiente problema.", es_destructiva=False),
    ]


def _opciones_multivalue(issue: Issue, df: pd.DataFrame) -> list[Option]:
    sep = issue.metadata.get("separador", "' | '").strip("'")
    return [
        Option("1", "Explotar en filas",
               f"Cada valor separado por '{sep}' se convierte en una fila independiente. "
               f"El dataset crecerá en filas. Ideal para análisis por ad individual.",
               es_destructiva=False),
        Option("2", "Tomar solo el primero",
               f"Conservar solo el primer valor antes del '{sep}'. "
               f"Los demás se pierden — simple pero con pérdida de información.",
               es_destructiva=True),
        Option("3", "Convertir a lista",
               f"Guardar los valores como lista Python en la celda. "
               f"El df queda con listas — útil para procesamiento posterior.",
               es_destructiva=False),
        Option("4", "Dejar como está + documentar",
               "No modificar. Agregar nota en metadata del reporte sobre la violación 1FN.",
               es_destructiva=False),
        Option("5", "Ver ejemplos",
               "Mostrar los primeros 5 valores multi-celda antes de decidir.",
               es_destructiva=False),
        Option("s", "Saltar", "Pasar al siguiente problema.", es_destructiva=False),
    ]


def _opciones_nulos(issue: Issue, df: pd.DataFrame) -> list[Option]:
    col  = issue.columna
    vals = df[col].dropna()
    opciones = [
        Option("1", "Rellenar con 'sin dato'",
               f"Reemplazar los {issue.metadata.get('nulos',0)} nulos con la cadena 'sin dato'.",
               es_destructiva=False),
        Option("2", "Rellenar con moda",
               f"Usar el valor más frecuente: '{vals.mode()[0] if len(vals) > 0 else 'N/A'}'.",
               es_destructiva=False),
        Option("3", "Eliminar filas nulas",
               f"Eliminar las {issue.metadata.get('nulos',0)} filas donde '{col}' es nulo.",
               es_destructiva=True),
        Option("4", "Dejar como está",
               "Mantener los nulos. Adly los reportará en el confidence_note.",
               es_destructiva=False),
        Option("s", "Saltar", "Pasar al siguiente problema.", es_destructiva=False),
    ]
    return opciones


def _opciones_forma_normal(issue: Issue, df: pd.DataFrame) -> list[Option]:
    tipo = issue.tipo
    return [
        Option("1", "Documentar solamente",
               "Registrar la violación en el log de calidad. No modificar el dataset. "
               "Recomendado para Fase 1 — corrección real es migración a DB.",
               es_destructiva=False),
        Option("2", "Ver descripción técnica",
               "Mostrar la descripción completa de la violación y la solución recomendada.",
               es_destructiva=False),
        Option("s", "Saltar", "Pasar al siguiente problema.", es_destructiva=False),
    ]


# Mapa tipo → constructor de opciones
_OPCIONES_POR_TIPO: dict[str, Callable] = {
    "duplicados":        _opciones_duplicados,
    "email_roto":        _opciones_email_roto,
    "phone_sin_prefijo": _opciones_phone,
    "multivalue_1fn":    _opciones_multivalue,
    "nulos":             _opciones_nulos,
    "forma_normal_1FN":  _opciones_forma_normal,
    "forma_normal_2FN":  _opciones_forma_normal,
    "forma_normal_3FN":  _opciones_forma_normal,
}


# ─────────────────────────────────────────────────────────────
# FUNCIONES DE LIMPIEZA — agnósticas por tipo
# Cada función recibe (df, columna, metadata, **kwargs) → CleaningResult
# ─────────────────────────────────────────────────────────────

def _limpiar_duplicados(df: pd.DataFrame, col: str, opcion: str,
                        metadata: dict, **kwargs) -> CleaningResult:
    filas_antes = len(df)
    col_fecha   = _detectar_col_fecha(df)

    if opcion == "1":  # más reciente
        if col_fecha:
            df = df.copy()
            df["_fecha_sort"] = pd.to_datetime(df[col_fecha], errors="coerce")
            df = df.sort_values("_fecha_sort", ascending=False)
            df = df.drop_duplicates(subset=[col], keep="first")
            df = df.drop(columns=["_fecha_sort"])
            desc = f"Duplicados resueltos: conservado el más reciente por '{col_fecha}'."
        else:
            df = df.drop_duplicates(subset=[col], keep="last")
            desc = f"Duplicados resueltos: conservado el último registro (sin columna fecha detectada)."

    elif opcion == "2":  # más completo
        df = df.copy()
        df["_n_llenos"] = df.notna().sum(axis=1)
        df = df.sort_values("_n_llenos", ascending=False)
        df = df.drop_duplicates(subset=[col], keep="first")
        df = df.drop(columns=["_n_llenos"])
        desc = f"Duplicados resueltos: conservado el registro con más campos llenos."

    elif opcion == "3":  # marcar
        df = df.copy()
        df["es_duplicado"] = df.duplicated(subset=[col], keep=False)
        desc = f"Columna 'es_duplicado' agregada. {df['es_duplicado'].sum()} filas marcadas."

    elif opcion == "4":  # ver ejemplos
        grupos = df[df.duplicated(subset=[col], keep=False)].groupby(col)
        ejemplos = []
        for val, grupo in list(grupos)[:5]:
            ejemplos.append(f"\n  {val}:\n" + grupo[[col, "stage"] if "stage" in df.columns else [col]].to_string(index=False))
        desc = "EJEMPLOS DE DUPLICADOS:\n" + "\n".join(ejemplos)
        return CleaningResult("duplicados", col, opcion, filas_antes, filas_antes, 0, desc, df)

    filas_despues    = len(df)
    filas_afectadas  = filas_antes - filas_despues
    cols_nuevas      = [c for c in df.columns if c not in [col]]

    return CleaningResult(
        issue_tipo      = "duplicados",
        columna         = col,
        opcion_aplicada = opcion,
        filas_antes     = filas_antes,
        filas_despues   = filas_despues,
        filas_afectadas = filas_afectadas,
        descripcion     = desc,
        df              = df,
        columnas_nuevas = ["es_duplicado"] if opcion == "3" else [],
    )


def _limpiar_email(df: pd.DataFrame, col: str, opcion: str,
                   metadata: dict, **kwargs) -> CleaningResult:
    filas_antes = len(df)

    def _es_valido(email):
        if pd.isna(email):
            return False
        e = str(email).strip()
        partes = e.split("@")
        if len(partes) != 2:
            return False
        local, dominio = partes
        if bool(re.search(r"[^a-zA-Z0-9._%+\-]", local)):
            return False
        if "." not in dominio or len(dominio.split(".")[-1]) < 2:
            return False
        return True

    mask_valido = df[col].apply(_es_valido)

    if opcion == "1":  # marcar
        df = df.copy()
        df["email_valido"] = mask_valido
        desc = f"Columna 'email_valido' agregada. {mask_valido.sum()} válidos, {(~mask_valido).sum()} inválidos."
        cols_nuevas = ["email_valido"]

    elif opcion == "2":  # mover a raw
        df = df.copy()
        df = df.rename(columns={col: f"{col}_raw"})
        df[col] = df[f"{col}_raw"].where(mask_valido, other=None)
        desc = (f"'{col}' renombrada a '{col}_raw'. "
                f"Nueva columna '{col}' contiene solo los {mask_valido.sum()} emails válidos.")
        cols_nuevas = [f"{col}_raw"]

    elif opcion == "3":  # eliminar rotos
        df = df[mask_valido].copy()
        desc = f"Eliminadas {filas_antes - len(df)} filas con email inválido."
        cols_nuevas = []

    elif opcion == "4":  # ver ejemplos
        rotos = df.loc[~mask_valido, col].dropna().head(10).tolist()
        desc  = "EMAILS ROTOS (primeros 10):\n" + "\n".join(f"  {e}" for e in rotos)
        return CleaningResult("email_roto", col, opcion, filas_antes, filas_antes, 0, desc, df)

    else:
        cols_nuevas = []
        desc = "Sin cambios."

    return CleaningResult(
        issue_tipo      = "email_roto",
        columna         = col,
        opcion_aplicada = opcion,
        filas_antes     = filas_antes,
        filas_despues   = len(df),
        filas_afectadas = filas_antes - len(df) if opcion == "3" else (~mask_valido).sum(),
        descripcion     = desc,
        df              = df,
        columnas_nuevas = cols_nuevas,
    )


def _limpiar_phone(df: pd.DataFrame, col: str, opcion: str,
                   metadata: dict, prefijo: str = None, **kwargs) -> CleaningResult:
    filas_antes = len(df)
    mask_sin    = ~df[col].astype(str).str.strip().str.startswith("+")

    if opcion == "1":  # agregar prefijo
        if not prefijo:
            prefijo = kwargs.get("prefijo_default", "+1")
        df = df.copy()
        df[col] = df[col].apply(
            lambda x: f"{prefijo}{str(x).strip()}"
            if pd.notna(x) and not str(x).strip().startswith("+")
            else x
        )
        desc = f"Prefijo '{prefijo}' agregado a {mask_sin.sum()} teléfonos."

    elif opcion == "2":  # marcar
        df = df.copy()
        df["telefono_valido"] = df[col].astype(str).str.strip().str.startswith("+")
        desc = f"Columna 'telefono_valido' agregada. {(~mask_sin).sum()} válidos, {mask_sin.sum()} sin prefijo."

    elif opcion == "3":  # ver ejemplos
        ejemplos = df.loc[mask_sin, col].head(10).tolist()
        desc = "TELÉFONOS SIN PREFIJO (primeros 10):\n" + "\n".join(f"  {t}" for t in ejemplos)
        return CleaningResult("phone_sin_prefijo", col, opcion, filas_antes, filas_antes, 0, desc, df)

    else:
        desc = "Sin cambios."

    return CleaningResult(
        issue_tipo      = "phone_sin_prefijo",
        columna         = col,
        opcion_aplicada = opcion,
        filas_antes     = filas_antes,
        filas_despues   = len(df),
        filas_afectadas = int(mask_sin.sum()),
        descripcion     = desc,
        df              = df,
        columnas_nuevas = ["telefono_valido"] if opcion == "2" else [],
    )


def _limpiar_multivalue(df: pd.DataFrame, col: str, opcion: str,
                        metadata: dict, **kwargs) -> CleaningResult:
    filas_antes = len(df)
    sep_raw     = metadata.get("separador", "' | '").strip("'")
    # Normalizar separador — puede venir con espacios o sin
    sep = sep_raw if sep_raw in df[col].dropna().astype(str).iloc[0] else "|"

    if opcion == "1":  # explotar en filas
        df = df.copy()
        df[col] = df[col].astype(str).apply(
            lambda x: [v.strip() for v in x.split(sep)] if sep in x and pd.notna(x) else [x]
        )
        df = df.explode(col).reset_index(drop=True)
        # Limpiar nulos que se colaron como string
        df[col] = df[col].replace({"nan": None, "None": None})
        desc = (f"Columna '{col}' explotada por '{sep}'. "
                f"{filas_antes} → {len(df)} filas (+{len(df)-filas_antes} filas nuevas).")

    elif opcion == "2":  # solo el primero
        df = df.copy()
        df[col] = df[col].astype(str).apply(
            lambda x: x.split(sep)[0].strip() if sep in x else x
        )
        df[col] = df[col].replace({"nan": None, "None": None})
        desc = f"'{col}': conservado solo el primer valor antes de '{sep}'."

    elif opcion == "3":  # convertir a lista Python
        df = df.copy()
        df[col] = df[col].astype(str).apply(
            lambda x: [v.strip() for v in x.split(sep)] if sep in x else x
        )
        desc = f"'{col}' convertida a listas Python. Celdas simples sin cambio."

    elif opcion == "4":  # documentar
        desc = (f"Violación 1FN documentada en log. '{col}' contiene múltiples valores "
                f"separados por '{sep}' en {metadata.get('celdas_afectadas',0)} celdas. "
                f"Sin modificaciones al dataset.")

    elif opcion == "5":  # ver ejemplos
        ejemplos = metadata.get("ejemplos", [])[:5]
        desc = f"EJEMPLOS MULTI-VALOR en '{col}':\n" + "\n".join(f"  {e}" for e in ejemplos)
        return CleaningResult("multivalue_1fn", col, opcion, filas_antes, filas_antes, 0, desc, df)

    else:
        desc = "Sin cambios."

    return CleaningResult(
        issue_tipo      = "multivalue_1fn",
        columna         = col,
        opcion_aplicada = opcion,
        filas_antes     = filas_antes,
        filas_despues   = len(df),
        filas_afectadas = metadata.get("celdas_afectadas", 0),
        descripcion     = desc,
        df              = df,
    )


def _limpiar_nulos(df: pd.DataFrame, col: str, opcion: str,
                   metadata: dict, valor_fill: str = None, **kwargs) -> CleaningResult:
    filas_antes = len(df)
    n_nulos     = int(df[col].isna().sum())

    if opcion == "1":  # rellenar con 'sin dato'
        df = df.copy()
        df[col] = df[col].fillna("sin dato")
        desc = f"'{col}': {n_nulos} nulos reemplazados por 'sin dato'."

    elif opcion == "2":  # moda
        moda = df[col].mode()
        fill = moda[0] if len(moda) > 0 else "sin dato"
        df   = df.copy()
        df[col] = df[col].fillna(fill)
        desc = f"'{col}': {n_nulos} nulos reemplazados por moda '{fill}'."

    elif opcion == "3":  # eliminar
        df   = df[df[col].notna()].copy()
        desc = f"Eliminadas {n_nulos} filas donde '{col}' era nulo."

    elif opcion == "4":  # dejar
        desc = f"'{col}': {n_nulos} nulos conservados. Se reflejarán en confidence_note."

    else:
        desc = "Sin cambios."

    return CleaningResult(
        issue_tipo      = "nulos",
        columna         = col,
        opcion_aplicada = opcion,
        filas_antes     = filas_antes,
        filas_despues   = len(df),
        filas_afectadas = n_nulos,
        descripcion     = desc,
        df              = df,
    )


def _limpiar_forma_normal(df: pd.DataFrame, col: str, opcion: str,
                          metadata: dict, **kwargs) -> CleaningResult:
    filas_antes = len(df)

    if opcion == "1":  # documentar
        desc = f"Violación {metadata.get('tipo_fn','FN')} documentada: {metadata.get('descripcion','')}"
    elif opcion == "2":  # ver descripción
        desc = f"DESCRIPCIÓN TÉCNICA:\n{metadata.get('descripcion','Sin descripción disponible.')}"
    else:
        desc = "Sin cambios."

    return CleaningResult(
        issue_tipo      = col,  # aquí col es el tipo_fn
        columna         = str(metadata.get("columnas", col)),
        opcion_aplicada = opcion,
        filas_antes     = filas_antes,
        filas_despues   = filas_antes,
        filas_afectadas = 0,
        descripcion     = desc,
        df              = df,
    )


# Mapa tipo → función de limpieza
_LIMPIEZA_POR_TIPO: dict[str, Callable] = {
    "duplicados":        _limpiar_duplicados,
    "email_roto":        _limpiar_email,
    "phone_sin_prefijo": _limpiar_phone,
    "multivalue_1fn":    _limpiar_multivalue,
    "nulos":             _limpiar_nulos,
    "forma_normal_1FN":  _limpiar_forma_normal,
    "forma_normal_2FN":  _limpiar_forma_normal,
    "forma_normal_3FN":  _limpiar_forma_normal,
}


# ─────────────────────────────────────────────────────────────
# CLEANING SESSION — el loop interactivo
# ─────────────────────────────────────────────────────────────

class CleaningSession:
    """
    Sesión de limpieza guiada. Itera los issues de un DataQualityReport
    en orden de impacto, presenta opciones al usuario, y aplica decisiones.

    Estado:
        _issues_pendientes  : cola de Issue ordenada por impacto desc
        _issues_resueltos   : lista de (Issue, CleaningResult)
        _df                 : DataFrame actual (se actualiza con cada decisión)
        decisions_log       : registro de qué se hizo

    Uso:
        session = CleaningSession.start(report)
        issue   = session.next_issue()
        print(session.render_issue(issue))  # texto para el usuario
        result  = session.apply("1")
        print(result.descripcion)
    """

    def __init__(self):
        self._issues_pendientes: list[Issue] = []
        self._issues_resueltos:  list[tuple]  = []
        self._issue_actual:      Optional[Issue] = None
        self._df:                pd.DataFrame = None
        self.decisions_log:      list[dict]   = []

    @classmethod
    def start(cls, report) -> "CleaningSession":
        """
        Construye la sesión desde un DataQualityReport.
        Convierte los hallazgos en Issues ordenados por impacto.
        """
        session = cls()
        session._df = report.normalized_df.copy()
        session._issues_pendientes = _construir_issues(report, session._df)
        return session

    # Opción más segura por tipo — nunca destructiva
    # Agnóstico: basado en el tipo de problema, no en el nombre de columna
    _OPCION_SEGURA = {
        "duplicados":        "3",  # marcar sin borrar
        "email_roto":        "1",  # marcar inválidos
        "phone_sin_prefijo": "2",  # marcar sin prefijo
        "multivalue_1fn":    "4",  # documentar, no explotar
        "nulos":             "4",  # dejar como está
        "forma_normal_1FN":  "1",  # documentar
        "forma_normal_2FN":  "1",  # documentar
        "forma_normal_3FN":  "1",  # documentar
    }

    def apply_auto(self) -> list["CleaningResult"]:
        """
        Modo automático — aplica la opción más segura en todos los issues.
        Nunca destructivo: no elimina filas, no modifica valores originales.
        Retorna lista de resultados para mostrar el resumen al usuario.
        """
        resultados = []
        while not self.done():
            issue = self.next_issue()
            if issue is None:
                break
            opcion = self._OPCION_SEGURA.get(issue.tipo, "s")
            result = self.apply(opcion)
            if result:
                resultados.append(result)
        return resultados

    def next_issue(self) -> Optional[Issue]:
        """
        Retorna el siguiente Issue sin resolver.
        None si no quedan issues — sesión terminada.
        """
        if not self._issues_pendientes:
            self._issue_actual = None
            return None
        self._issue_actual = self._issues_pendientes[0]
        # Regenerar opciones con el df actual (puede haber cambiado)
        constructor = _OPCIONES_POR_TIPO.get(self._issue_actual.tipo)
        if constructor:
            self._issue_actual.opciones = constructor(self._issue_actual, self._df)
        return self._issue_actual

    def apply(self, opcion_id: str, **kwargs) -> Optional[CleaningResult]:
        """
        Aplica la opción elegida al issue actual.
        Si la opción es 's' (saltar), mueve al siguiente sin modificar el df.
        Retorna CleaningResult con el df actualizado.
        """
        if self._issue_actual is None:
            return None

        issue = self._issue_actual

        # Saltar
        if opcion_id.lower() == "s":
            self._issues_pendientes.pop(0)
            self.decisions_log.append({
                "tipo": issue.tipo, "columna": issue.columna,
                "decision": "saltar", "descripcion": "Issue saltado por el usuario.",
            })
            return CleaningResult(
                issue_tipo=issue.tipo, columna=issue.columna,
                opcion_aplicada="s", filas_antes=len(self._df),
                filas_despues=len(self._df), filas_afectadas=0,
                descripcion="Issue saltado. Sin cambios.", df=self._df,
            )

        # Validar opción
        ids_validos = [o.id for o in issue.opciones]
        if opcion_id not in ids_validos:
            return CleaningResult(
                issue_tipo=issue.tipo, columna=issue.columna,
                opcion_aplicada=opcion_id, filas_antes=len(self._df),
                filas_despues=len(self._df), filas_afectadas=0,
                descripcion=f"Opción '{opcion_id}' no válida. Opciones: {ids_validos}",
                df=self._df,
            )

        # Ejecutar limpieza
        fn = _LIMPIEZA_POR_TIPO.get(issue.tipo)
        if not fn:
            return None

        try:
            result = fn(
                df       = self._df,
                col      = issue.columna,
                opcion   = opcion_id,
                metadata = issue.metadata,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Error aplicando limpieza [{issue.tipo}][{issue.columna}]: {e}")
            return CleaningResult(
                issue_tipo=issue.tipo, columna=issue.columna,
                opcion_aplicada=opcion_id, filas_antes=len(self._df),
                filas_despues=len(self._df), filas_afectadas=0,
                descripcion=f"Error al aplicar: {e}", df=self._df,
            )

        # Solo-vista: únicamente opciones que muestran ejemplos del df
        # "Ver descripción técnica" avanza — es info estática, no datos
        label_elegida = next((o.label for o in issue.opciones if o.id == opcion_id), "")
        es_solo_vista = "ejemplo" in label_elegida.lower()

        if not es_solo_vista:
            self._df = result.df
            self._issues_resueltos.append((issue, result))
            self._issues_pendientes.pop(0)
            self.decisions_log.append({
                "tipo":        issue.tipo,
                "columna":     issue.columna,
                "decision":    opcion_id,
                "descripcion": result.descripcion,
                "filas_antes": result.filas_antes,
                "filas_despues": result.filas_despues,
            })

        return result

    def skip(self) -> None:
        """Salta el issue actual sin modificar nada."""
        self.apply("s")

    def done(self) -> bool:
        """True cuando no quedan issues pendientes."""
        return len(self._issues_pendientes) == 0

    def progress(self) -> tuple[int, int]:
        """(resueltos, total) — para mostrar progreso al usuario."""
        total    = len(self._issues_resueltos) + len(self._issues_pendientes)
        resueltos = len(self._issues_resueltos)
        return resueltos, total

    @property
    def final_df(self) -> pd.DataFrame:
        """DataFrame con todas las decisiones aplicadas."""
        return self._df

    def render_issue(self, issue: Issue) -> str:
        """
        Renderiza un Issue en texto para el usuario.
        Formato: descripción + impacto + ejemplos + menú de opciones.
        """
        resueltos, total = self.progress()
        lineas = [
            f"{'─'*50}",
            f"PROBLEMA {resueltos+1}/{total} — {issue.tipo.upper().replace('_',' ')}",
            f"{'─'*50}",
            f"{issue.descripcion}",
        ]
        if issue.ejemplos:
            lineas.append(f"\nEjemplos:")
            for ej in issue.ejemplos[:3]:
                lineas.append(f"  → {ej}")
        lineas.append(f"\n¿Qué hago?")
        for opt in issue.opciones:
            destructiva = " ⚠️ destructiva" if opt.es_destructiva else ""
            lineas.append(f"  [{opt.id}] {opt.label}{destructiva}")
            lineas.append(f"      {opt.descripcion}")
        return "\n".join(lineas)

    def render_result(self, result: CleaningResult) -> str:
        """Renderiza un CleaningResult para mostrar al usuario."""
        lineas = [f"\n✓ {result.descripcion}"]
        if result.filas_afectadas > 0:
            lineas.append(f"  Filas afectadas: {result.filas_afectadas}")
        if result.filas_antes != result.filas_despues:
            lineas.append(f"  Dataset: {result.filas_antes} → {result.filas_despues} filas")
        if result.columnas_nuevas:
            lineas.append(f"  Columnas nuevas: {result.columnas_nuevas}")
        return "\n".join(lineas)

    def summary(self) -> str:
        """Resumen final de la sesión de limpieza."""
        if not self.decisions_log:
            return "Sesión sin cambios — todos los issues fueron saltados."

        lineas = [f"RESUMEN DE LIMPIEZA ({len(self.decisions_log)} decisiones):"]
        for log in self.decisions_log:
            if log["decision"] == "saltar":
                lineas.append(f"  ○ [{log['tipo']}] {log['columna']} — saltado")
            else:
                diff = log.get('filas_despues', 0) - log.get('filas_antes', 0)
                diff_str = f" ({diff:+d} filas)" if diff != 0 else ""
                lineas.append(f"  ✓ [{log['tipo']}] {log['columna']}{diff_str}")
                lineas.append(f"    {log['descripcion'][:80]}...")

        filas_final = len(self._df)
        lineas.append(f"\nDataset final: {filas_final} filas x {len(self._df.columns)} columnas")
        return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────
# CONSTRUCTOR DE ISSUES — convierte el reporte en cola ordenada
# ─────────────────────────────────────────────────────────────

def _construir_issues(report, df: pd.DataFrame) -> list[Issue]:
    """
    Convierte DataQualityReport en lista de Issue ordenada por impacto desc.
    Agnóstico — itera los hallazgos del reporte, no asume columnas.
    """
    issues = []

    # Duplicados
    for col, info in report.duplicates.get("por_clave", {}).items():
        issues.append(Issue(
            tipo        = "duplicados",
            columna     = col,
            impacto     = info["pct"],
            descripcion = (
                f"{info['filas_afectadas']} filas tienen '{col}' duplicado ({info['pct']}% del total). "
                f"{info['valores_duplicados']} valores únicos aparecen más de una vez."
            ),
            ejemplos    = df[df.duplicated(subset=[col], keep=False)][col].head(5).tolist(),
            metadata    = info,
        ))

    # Emails rotos
    for col, info in report.emails.items():
        rotos = info["multi_at"] + info["dominio_roto"] + info["local_invalido"]
        if rotos > 0:
            pct = round(rotos / info["total_revisados"] * 100, 1)
            issues.append(Issue(
                tipo        = "email_roto",
                columna     = col,
                impacto     = pct,
                descripcion = (
                    f"'{col}' tiene {rotos} emails inválidos ({pct}%): "
                    f"{info['multi_at']} con doble '@', "
                    f"{info['dominio_roto']} con dominio roto, "
                    f"{info['local_invalido']} con caracteres inválidos (tildes, espacios)."
                ),
                ejemplos    = info.get("ejemplos_rotos", []),
                metadata    = info,
            ))

    # Teléfonos
    for col, info in report.phones.items():
        if info["sin_prefijo_internacional"] > 0:
            issues.append(Issue(
                tipo        = "phone_sin_prefijo",
                columna     = col,
                impacto     = info["pct_sin_prefijo"],
                descripcion = (
                    f"'{col}': {info['sin_prefijo_internacional']} teléfonos ({info['pct_sin_prefijo']}%) "
                    f"sin prefijo internacional '+'. Imposible saber el país."
                ),
                ejemplos    = df[~df[col].astype(str).str.strip().str.startswith("+")][col].head(5).tolist(),
                metadata    = info,
            ))

    # Multi-valor 1FN
    for col, info in report.multivalue.items():
        issues.append(Issue(
            tipo        = "multivalue_1fn",
            columna     = col,
            impacto     = info["pct"],
            descripcion = (
                f"'{col}': {info['celdas_afectadas']} celdas ({info['pct']}%) contienen "
                f"múltiples valores separados por {info['separador']}. "
                f"Promedio: {info['valores_promedio_por_celda']} valores por celda. "
                f"Violación Primera Forma Normal — análisis de atribución incorrectos."
            ),
            ejemplos    = info.get("ejemplos", []),
            metadata    = info,
        ))

    # Nulos (solo warning/critical)
    for col, info in report.nulls.items():
        if info["severidad"] in ("critical", "warning"):
            issues.append(Issue(
                tipo        = "nulos",
                columna     = col,
                impacto     = info["pct"],
                descripcion = (
                    f"'{col}': {info['nulos']} valores nulos ({info['pct']}%). "
                    f"Severidad: {info['severidad'].upper()}."
                ),
                ejemplos    = [],
                metadata    = info,
            ))

    # Formas normales (solo 2FN y 3FN — 1FN ya está en multivalue)
    for tipo_fn in ("2FN", "3FN"):
        for item in report.normal_forms.get(tipo_fn, []):
            issues.append(Issue(
                tipo        = f"forma_normal_{tipo_fn}",
                columna     = str(item.get("columnas", "")),
                impacto     = 0,
                descripcion = item.get("descripcion", ""),
                ejemplos    = [],
                metadata    = {**item, "tipo_fn": tipo_fn},
            ))

    # Ordenar por impacto descendente
    issues.sort(key=lambda x: x.impacto, reverse=True)
    return issues


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _detectar_col_fecha(df: pd.DataFrame) -> Optional[str]:
    """Detecta la primera columna de fecha disponible."""
    patrones = ["fecha", "date", "ts", "timestamp", "created", "creacion"]
    for col in df.columns:
        if any(p in col.lower() for p in patrones):
            return col
    return None
