"""Pruebas de las reglas de calidad. Se corren con:  python -m pytest"""
import pandas as pd

from etl import transform as t


def _lineas(**cambios):
    base = {"InvoiceLineID": [1], "InvoiceID": [10], "StockItemID": [5], "Quantity": [3],
            "UnitPrice": [10.0], "TaxAmount": [4.5], "LineProfit": [8.0], "ExtendedPrice": [34.5],
            "LastEditedWhen": pd.to_datetime(["2016-01-01"])}
    base.update(cambios)
    return pd.DataFrame(base)


def test_linea_valida_pasa():
    limpio, rechazos = t.transformar_invoice_lines(_lineas(), facturas_validas={10})
    assert len(limpio) == 1
    assert rechazos.empty


def test_cantidad_cero_se_rechaza():
    limpio, rechazos = t.transformar_invoice_lines(_lineas(Quantity=[0]), facturas_validas={10})
    assert limpio.empty
    assert rechazos.iloc[0]["rule_name"] == "cantidad_no_positiva"


def test_linea_sin_factura_va_a_cuarentena():
    limpio, rechazos = t.transformar_invoice_lines(_lineas(), facturas_validas={999})
    assert limpio.empty
    assert rechazos.iloc[0]["rule_name"] == "factura_inexistente"


def test_duplicado_conserva_la_version_mas_reciente():
    df = pd.concat([_lineas(), _lineas(Quantity=[7],
                    LastEditedWhen=pd.to_datetime(["2016-02-01"]))], ignore_index=True)
    limpio, rechazos = t.transformar_invoice_lines(df, facturas_validas={10})
    assert list(limpio["Quantity"]) == [7]
    assert rechazos.iloc[0]["rule_name"] == "duplicado"


def test_marca_nula_se_vuelve_sin_marca_y_no_cero():
    df = pd.DataFrame({"StockItemID": [1], "StockItemName": ["  USB   missile launcher "],
                       "Brand": [None], "Size": [None], "UnitPrice": [25.0], "GroupName": [None],
                       "LastEditedWhen": pd.to_datetime(["2013-01-01"])})
    limpio, _ = t.transformar_products(df)
    assert limpio.iloc[0]["Brand"] == "Sin marca"
    assert limpio.iloc[0]["StockItemName"] == "USB missile launcher"


def test_factura_con_fecha_futura_se_rechaza():
    df = pd.DataFrame({"InvoiceID": [1], "CustomerID": [2], "SalespersonPersonID": [3],
                       "OrderID": [4], "InvoiceDate": [pd.Timestamp("2999-01-01")],
                       "LastEditedWhen": pd.to_datetime(["2016-01-01"])})
    limpio, rechazos = t.transformar_invoices(df)
    assert limpio.empty
    assert rechazos.iloc[0]["rule_name"] == "fecha_futura"


def test_cliente_sin_grupo_de_compra_queda_como_no_aplica():
    df = pd.DataFrame({"CustomerID": [1], "CustomerName": ["Tailspin Toys"], "CategoryName": ["Novelty Shop"],
                       "BuyingGroupName": [None], "CityName": ["Lisco"], "StateProvinceName": ["Nebraska"],
                       "CountryName": ["United States"], "SalesTerritory": ["Plains"],
                       "LastEditedWhen": pd.to_datetime(["2013-01-01"])})
    limpio, _ = t.transformar_customers(df)
    assert limpio.iloc[0]["BuyingGroupName"] == "No aplica"
