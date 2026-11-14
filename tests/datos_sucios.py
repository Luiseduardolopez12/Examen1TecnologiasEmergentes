"""Prueba con datos sucios.

WideWorldImporters viene muy limpia, así que este script fabrica filas malas a propósito (IDs desde 9000000 para distinguirlas),
las pasa por las mismas reglas del ETL y guarda lo rechazado en audit.rejected_rows.

    python -m tests.datos_sucios

No modifica la fuente ni las tablas clean/dw: solo escribe en audit.
"""
import pandas as pd
from sqlalchemy import text

from etl import transform as t

F = pd.Timestamp("2016-05-01")


def construir():
    """Devuelve los DataFrames sucios y cuántos rechazos esperamos por tabla."""
    people = pd.DataFrame({
        "PersonID": [9000001, 9000002],
        "FullName": ["Ana Prueba", None],            # nombre vacío
        "LastEditedWhen": [F, F]})

    products = pd.DataFrame({
        "StockItemID": [9000001, 9000002, 9000003],
        "StockItemName": ["Producto bueno", "   ", "Producto con precio malo"],   # nombre en blanco
        "Brand": ["Marca X", "Marca X", None],
        "Size": ["M", "M", None],
        "UnitPrice": [10.0, 5.0, -3.0],              # precio negativo
        "GroupName": ["Novelty Items", "Novelty Items", None],
        "LastEditedWhen": [F, F, F]})

    customers = pd.DataFrame({
        "CustomerID": [9000001, 9000002],
        "CustomerName": ["Cliente bueno", ""],       # nombre vacío
        "CategoryName": ["Novelty Shop"] * 2,
        "BuyingGroupName": [None, None],
        "CityName": ["Lisco"] * 2,
        "StateProvinceName": ["Nebraska"] * 2,
        "CountryName": ["United States"] * 2,
        "SalesTerritory": ["Plains"] * 2,
        "LastEditedWhen": [F, F]})

    invoices = pd.DataFrame({
        "InvoiceID": [9000001, 9000002, 9000003, 9000004, 9000005, 9000005],
        "CustomerID": [1, 1, 1, None, 1, 1],         # 9000004 sin cliente
        "SalespersonPersonID": [2] * 6,
        "OrderID": [1] * 6,
        "InvoiceDate": [F, pd.NaT,                   # 9000002 sin fecha
                        pd.Timestamp("2999-01-01"),  # 9000003 fecha futura
                        F, F, F],
        "LastEditedWhen": [F, F, F, F, F, F + pd.Timedelta(days=1)]})   # 9000005 duplicada

    lines = pd.DataFrame({
        "InvoiceLineID": [9000101, 9000102, 9000103, 9000104, 9000105, 9000106, 9000107, 9000107],
        "InvoiceID": [9000001, 9000005, 9000001, 9000001, 9000001, 9999999, 9000001, 9000001],
        "StockItemID": [1] * 8,
        "Quantity": [3, 2, 0, 5, 4, 1, 1, 9],        # 9000103 con cantidad 0
        "UnitPrice": [10.0, 10.0, 10.0, -7.0, 10.0, 10.0, 10.0, 10.0],   # 9000104 precio negativo
        "TaxAmount": [4.5, 3.0, 1.0, 1.0, None, 1.0, 1.0, 1.0],          # 9000105 sin impuesto
        "LineProfit": [8.0] * 8,
        "ExtendedPrice": [34.5, 23.0, 1.0, 1.0, 40.0, 11.5, 11.5, 11.5],
        "LastEditedWhen": [F] * 7 + [F + pd.Timedelta(days=1)]})         # 9000106 sin factura, 9000107 duplicada

    # tabla -> (rechazos esperados, filas limpias esperadas)
    esperado = {"people": (1, 1), "products": (2, 1), "customers": (1, 1),
                "invoices": (4, 2), "invoice_lines": (5, 3)}
    return {"people": people, "products": products, "customers": customers,
            "invoices": invoices, "invoice_lines": lines}, esperado


def correr_reglas():
    """Aplica las reglas del ETL a los datos sucios. No toca la base."""
    datos, esperado = construir()
    resultados = {}
    resultados["people"] = t.transformar_people(datos["people"])
    resultados["products"] = t.transformar_products(datos["products"])
    resultados["customers"] = t.transformar_customers(datos["customers"])
    resultados["invoices"] = t.transformar_invoices(datos["invoices"])
    validas = set(resultados["invoices"][0]["InvoiceID"])
    resultados["invoice_lines"] = t.transformar_invoice_lines(datos["invoice_lines"], validas)
    return resultados, esperado


def main():
    # estos imports necesitan conexión, por eso van aquí y no arriba
    from etl.auditoria import ejecucion, guardar_rechazos
    from etl.config import dw_engine

    resultados, esperado = correr_reglas()

    # si se corre dos veces, se borran los rechazos de la corrida de prueba anterior
    with dw_engine().begin() as cn:
        cn.execute(text("""
            DELETE r FROM audit.rejected_rows r
            JOIN audit.etl_runs e ON e.execution_id = r.execution_id
            WHERE e.pipeline_name = 'prueba_datos_sucios'"""))

    todos = []
    with ejecucion("prueba_datos_sucios", "datos sintéticos", "audit.rejected_rows") as run:
        for nombre, (limpio, rechazos) in resultados.items():
            run.rows_read += len(limpio) + len(rechazos)
            run.rows_rejected += len(rechazos)
            todos.append(rechazos)
        guardar_rechazos(pd.concat(todos, ignore_index=True), run.id)

    print("\nResultado por tabla (esperado -> obtenido):")
    ok = True
    for nombre, (limpio, rechazos) in resultados.items():
        rech_esp, limp_esp = esperado[nombre]
        bien = len(rechazos) == rech_esp and len(limpio) == limp_esp
        ok = ok and bien
        print(f"  {nombre:14} rechazadas {rech_esp}->{len(rechazos)}  limpias {limp_esp}->{len(limpio)}  "
              f"{'OK' if bien else 'REVISAR'}")

    print("\nDetalle de lo rechazado:")
    detalle = pd.concat(todos, ignore_index=True)
    print(detalle[["source_object", "business_key", "rule_name"]].to_string(index=False))
    print("\nTodo coincide con lo esperado." if ok else "\nHay diferencias, revisa arriba.")


if __name__ == "__main__":
    main()
