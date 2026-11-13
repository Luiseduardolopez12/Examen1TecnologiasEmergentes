"""Perfilado de las tablas raw: nulos, distintos, mínimos, máximos y atípicos (IQR).

    python -m etl.profiling
Deja un CSV por tabla en documentation/perfilado/ (sirve como evidencia 'antes de limpiar').
"""
from pathlib import Path

import pandas as pd

from etl.config import dw_engine

TABLAS = ["raw_people", "raw_products", "raw_customers", "raw_invoices", "raw_invoice_lines"]
SALIDA = Path("documentation/perfilado")


def perfilar(tabla):
    df = pd.read_sql(f"SELECT * FROM stg.{tabla}", dw_engine())
    filas = []
    for col in df.columns:
        if col.startswith("_"):
            continue
        s = df[col]
        fila = {"columna": col, "tipo": str(s.dtype), "filas": len(s),
                "nulos_pct": round(s.isna().mean() * 100, 2), "distintos": s.nunique(dropna=True),
                "minimo": None, "maximo": None, "atipicos_iqr": None}
        try:
            fila["minimo"], fila["maximo"] = s.min(), s.max()
        except TypeError:
            pass
        if pd.api.types.is_numeric_dtype(s) and s.notna().any():
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            fila["atipicos_iqr"] = int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())
        filas.append(fila)
    return pd.DataFrame(filas)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    for tabla in TABLAS:
        try:
            perfil = perfilar(tabla)
        except Exception as e:
            print(f"{tabla}: no se pudo perfilar ({e}). ¿Ya corriste el ETL?")
            continue
        perfil.to_csv(SALIDA / f"perfil_{tabla}.csv", index=False)
        print(f"{tabla}: {len(perfil)} columnas perfiladas")


if __name__ == "__main__":
    main()
