"""Test rápido para validar fix de cmd_cohorts"""
import pandas as pd
from interfaces.cli import commands

# Crear dataset de prueba con closed_won
df = pd.DataFrame({
    "fecha_entrada": ["2026-01-15", "2026-02-10", "2026-03-05", "2026-01-20", "2026-02-25"],
    "estado": ["closed_won", "lead", "closed_won", "mql", "closed_won"],
    "costo_lead": [50000, 30000, 45000, 25000, 55000],
    "valor_venta": [150000, 0, 120000, 0, 180000],
    "campana": ["A", "B", "A", "C", "A"]
})

print("=== Test cmd_cohorts con closed_won ===")
print(f"Estados originales: {df['estado'].unique().tolist()}")

# Ejecutar el comando
try:
    result = commands.cmd_cohorts(df)
    print(f"Resultado: {result}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()