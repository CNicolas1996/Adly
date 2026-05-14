# sheets.py — Adly · Data-Buddy
# Arquitectura OOP con BaseConnector
# Escalable a múltiples fuentes de datos

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from abc import ABC, abstractmethod
from dotenv import load_dotenv
from src.ingestion.ingestion_normalizer import normalizar
import os

load_dotenv()


# ─────────────────────────────────────────
# CONTRATO BASE — todas las fuentes lo implementan
# ─────────────────────────────────────────

class BaseConnector(ABC):
    """
    Contrato que deben cumplir todos los conectores de Adly.
    SheetsConnector, GHLConnector, MockConnector — todos heredan de aquí.
    Si mañana agregas Notion, HubSpot o cualquier otra fuente,
    solo implementas estos métodos y el resto del sistema no cambia.
    """

    @abstractmethod
    def conectar(self) -> None:
        """Establece la conexión con la fuente de datos."""
        pass

    @abstractmethod
    def leer(self) -> pd.DataFrame:
        """Lee los datos y retorna un DataFrame."""
        pass

    @abstractmethod
    def detectar_schema(self, df: pd.DataFrame) -> dict:
        """Detecta y mapea las columnas disponibles."""
        pass

    def info(self) -> str:
        """Retorna información básica del conector."""
        return f"[{self.__class__.__name__}] conectado"


# ─────────────────────────────────────────
# SHEETS CONNECTOR
# ─────────────────────────────────────────

class SheetsConnector(BaseConnector):
    """
    Conector para Google Sheets.
    Schema dinámico — se adapta a cualquier estructura de columnas.
    Un mismo conector sirve para Camí y para cualquier otro cliente.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    def __init__(self, sheet_id: str = None, creds_path: str = None, hoja: int = 0):
        self.creds_path = creds_path or os.getenv("GOOGLE_SHEETS_CREDENTIALS", "./credentials.json")
        self.sheet_id   = sheet_id or os.getenv("GOOGLE_SHEET_ID", "").strip()
        self.hoja       = hoja
        self.client     = None
        self.schema     = {}

        if not self.sheet_id:
            self.sheet_id = input("Sheet ID (pega el ID de tu Google Sheet): ").strip()

    def conectar(self) -> None:
        if not os.path.exists(self.creds_path):
            raise FileNotFoundError(
                f"No se encontró credentials.json en: {self.creds_path}\n"
                f"Asegúrate de que el archivo esté en la raíz del proyecto."
            )
        creds       = Credentials.from_service_account_file(self.creds_path, scopes=self.SCOPES)
        self.client = gspread.authorize(creds)
        print(f"[SheetsConnector] Conexión establecida")

    def leer(self) -> pd.DataFrame:
        if not self.client:
            self.conectar()

        spreadsheet = self.client.open_by_key(self.sheet_id)
        worksheet   = spreadsheet.get_worksheet(self.hoja)
        datos       = worksheet.get_all_records()

        if not datos:
            print(f"[SheetsConnector] La hoja está vacía.")
            return pd.DataFrame()

        df          = pd.DataFrame(datos)
        self.schema = self.detectar_schema(df)

        print(f"[SheetsConnector] {len(df)} filas · {len(df.columns)} columnas leídas")
        return df

    def detectar_schema(self, df: pd.DataFrame) -> dict:
        """
        Infiere el mapeo de columnas usando LLM (via ColumnMapper).
        Devuelve un dict compatible con MetricsCalculator(config=...).
        """
        from src.processing.column_mapper import ColumnMapper
        mapper = ColumnMapper()
        return mapper.mapear(df, cache_key=self.sheet_id)

    def _buscar_columna(self, df: pd.DataFrame, palabras_clave: list) -> str | None:
        for col in df.columns:
            if any(kw in col.lower() for kw in palabras_clave):
                return col
        return None

    def preview(self, df: pd.DataFrame, n: int = 3) -> None:
        print(f"\n[SheetsConnector] Preview ({n} filas):")
        print(df.head(n).to_string())


# ─────────────────────────────────────────
# MOCK CONNECTOR — desarrollo sin Sheets real
# ─────────────────────────────────────────

class MockConnector(BaseConnector):
    """
    Conector de datos de prueba.
    Mismo contrato que SheetsConnector — el resto del sistema
    no sabe si está hablando con datos reales o de prueba.
    """

    def __init__(self, csv_path: str = "data/raw/mock_sheet.csv"):
        self.csv_path = csv_path
        self.schema   = {}

    def conectar(self) -> None:
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(
                f"No se encontró: {self.csv_path}\n"
                f"Corre primero: python src/ingestion/mock_data.py"
            )
        print(f"[MockConnector] Usando datos de prueba: {self.csv_path}")

    def leer(self) -> pd.DataFrame:
        self.conectar()
        df          = pd.read_csv(self.csv_path)
        self.schema = self.detectar_schema(df)
        print(f"[MockConnector] {len(df)} filas · {len(df.columns)} columnas")
        return df

    def detectar_schema(self, df: pd.DataFrame) -> dict:
        """
        Infiere el mapeo de columnas usando LLM (via ColumnMapper).
        Devuelve un dict compatible con MetricsCalculator(config=...).
        """
        from src.processing.column_mapper import ColumnMapper
        mapper = ColumnMapper()
        return mapper.mapear(df, cache_key=self.csv_path)

    def preview(self, df: pd.DataFrame, n: int = 3) -> None:
        print(f"\n[MockConnector] Preview ({n} filas):")
        print(df.head(n).to_string())


# ─────────────────────────────────────────
# MAIN — probar ambos conectores
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys

    modo = sys.argv[1] if len(sys.argv) > 1 else "mock"

    print(f">> Probando conector en modo: {modo}\n")

    if modo == "mock":
        conector = MockConnector()
    else:
        conector = SheetsConnector()

    df = conector.leer()

    if not df.empty:
        conector.preview(df)
        print(f"\n>> {conector.info()}")
