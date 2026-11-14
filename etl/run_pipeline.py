"""Orquesta el ETL completo: fuente -> staging -> Data Warehouse.

    python -m etl.run_pipeline --modo full           # primera carga (reconstruye raw)
    python -m etl.run_pipeline --modo incremental    # solo lo cambiado desde el último watermark
"""
import argparse
from datetime import timedelta

from sqlalchemy import text

from etl import transform as t
from etl.auditoria import (ejecucion, guardar_rechazos, guardar_watermark,
                           leer_watermark)
from etl.config import OVERLAP_HOURS, SOURCE_DB, dw_engine
from etl.extract import INCREMENTALES, extraer
from etl.load_stg import cargar_raw, upsert_clean

# El orden importa: las líneas se validan contra las facturas ya cargadas
ENTIDADES = [
    # nombre, función de transformación, clave de negocio, tabla clean
    ("people", t.transformar_people, "PersonID", "clean_people"),
    ("products", t.transformar_products, "StockItemID", "clean_products"),
    ("customers", t.transformar_customers, "CustomerID", "clean_customers"),
    ("invoices", t.transformar_invoices, "InvoiceID", "clean_invoices"),
    ("invoice_lines", t.transformar_invoice_lines, "InvoiceLineID", "clean_invoice_lines"),
]


def cargar_staging(modo):
    for nombre, transformar, clave, clean in ENTIDADES:
        with ejecucion(f"stg_{nombre}", f"{SOURCE_DB}.{nombre}", f"stg.{clean}") as run:
            desde = None
            if modo == "incremental" and nombre in INCREMENTALES:
                ultimo = leer_watermark(nombre)
                if ultimo is not None:
                    # ventana de solapamiento por si llegan registros tardíos
                    desde = ultimo - timedelta(hours=OVERLAP_HOURS)
                    run.watermark_start = desde

            df = extraer(nombre, desde)
            run.rows_read = len(df)

            cargar_raw(df, nombre, run.id, reiniciar=(modo == "full"))
            limpio, rechazos = transformar(df)
            run.rows_rejected = len(rechazos)
            guardar_rechazos(rechazos, run.id)
            run.rows_inserted, run.rows_updated = upsert_clean(limpio, clean, clave)

            # el watermark solo avanza si todo lo anterior salió bien
            if nombre in INCREMENTALES and not df.empty:
                run.watermark_end = df["LastEditedWhen"].max().to_pydatetime()
                guardar_watermark(nombre, run.watermark_end)


def cargar_dw():
    with ejecucion("dw_load", "stg.*", "dw.*") as run:
        with dw_engine().begin() as cn:
            cn.execute(text("EXEC dw.usp_load_dim_salesperson"))
            cn.execute(text("EXEC dw.usp_load_dim_product"))
            cn.execute(text("EXEC dw.usp_load_dim_customer"))
            fila = cn.execute(text("EXEC dw.usp_load_fact_sales :id"), {"id": run.id}).fetchone()
        run.rows_inserted, run.rows_updated = int(fila[0]), int(fila[1])


def evaluar_alertas():
    """Después de cada carga se revisan las reglas de negocio. Si falla, la carga ya quedó bien hecha."""
    try:
        from alertas.evaluar import ejecutar
        print("\nEvaluando alertas de ventas...")
        ejecutar()
    except Exception as e:
        print(f"Aviso: no se pudieron evaluar las alertas ({e}). La carga de datos sí terminó bien.")


def main():
    ap = argparse.ArgumentParser(description="ETL ventas WideWorldImporters -> DW_Ventas")
    ap.add_argument("--modo", choices=["full", "incremental"], default="incremental")
    ap.add_argument("--saltar-dw", action="store_true", help="solo llegar hasta staging")
    args = ap.parse_args()

    cargar_staging(args.modo)
    if not args.saltar_dw:
        cargar_dw()
        evaluar_alertas()
    print("Listo. Revisa database/06_reconciliacion.sql para validar los totales.")


if __name__ == "__main__":
    main()
