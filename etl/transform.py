"""Limpieza y validación (raw -> clean). Cada función devuelve (datos_limpios, rechazos)."""
import pandas as pd

from etl.config import dw_engine

COLUMNAS_RECHAZO = ["source_object", "business_key", "rule_name", "detail"]


class Resultado:
    """Va juntando las filas rechazadas de una tabla para mandarlas a cuarentena."""

    def __init__(self, tabla, clave):
        self.tabla = tabla
        self.clave = clave
        self._partes = []

    def rechazar(self, df, mascara, regla, detalle):
        mascara = mascara.fillna(False).astype(bool)
        if mascara.any():
            self._partes.append(pd.DataFrame({
                "source_object": self.tabla,
                "business_key": df.loc[mascara, self.clave].astype(str).values,
                "rule_name": regla,
                "detail": detalle,
            }))
        return df[~mascara]

    def sin_duplicados(self, df):
        # regla de supervivencia: gana la versión con LastEditedWhen más reciente
        df = df.sort_values("LastEditedWhen")
        repetida = df.duplicated(self.clave, keep="last")
        return self.rechazar(df, repetida, "duplicado",
                             "Existe otra versión más reciente con la misma clave")

    def rechazos(self):
        if not self._partes:
            return pd.DataFrame(columns=COLUMNAS_RECHAZO)
        return pd.concat(self._partes, ignore_index=True)


def _texto(serie):
    """Quita espacios sobrantes; los textos vacíos pasan a nulo."""
    return serie.astype(object).map(
        lambda v: (" ".join(v.split()) or None) if isinstance(v, str) else v)


def transformar_people(df):
    res = Resultado("Application.People", "PersonID")
    df = df.copy()
    df["FullName"] = _texto(df["FullName"])
    df = res.rechazar(df, df["FullName"].isna(), "nombre_vacio", "FullName nulo o vacío")
    df = res.sin_duplicados(df)
    return df, res.rechazos()


def transformar_products(df):
    res = Resultado("Warehouse.StockItems", "StockItemID")
    df = df.copy()
    for c in ["StockItemName", "Brand", "Size", "GroupName"]:
        df[c] = _texto(df[c])
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")

    # Nulo = "no aplica": se deja un valor explícito, no un cero ni un texto vacío
    df["Brand"] = df["Brand"].fillna("Sin marca")
    df["Size"] = df["Size"].fillna("N/A")
    df["GroupName"] = df["GroupName"].fillna("Sin grupo")

    df = res.rechazar(df, df["StockItemName"].isna(), "nombre_vacio", "StockItemName nulo o vacío")
    df = res.rechazar(df, df["UnitPrice"].isna() | (df["UnitPrice"] < 0),
                      "precio_invalido", "UnitPrice nulo o negativo")
    df = res.sin_duplicados(df)
    return df, res.rechazos()


def transformar_customers(df):
    res = Resultado("Sales.Customers", "CustomerID")
    df = df.copy()
    for c in ["CustomerName", "CategoryName", "BuyingGroupName", "CityName",
              "StateProvinceName", "CountryName", "SalesTerritory"]:
        df[c] = _texto(df[c])

    # Un cliente sin grupo de compra no es un error: simplemente no aplica
    df["BuyingGroupName"] = df["BuyingGroupName"].fillna("No aplica")

    df = res.rechazar(df, df["CustomerName"].isna(), "nombre_vacio", "CustomerName nulo o vacío")
    df = res.sin_duplicados(df)
    return df, res.rechazos()


def transformar_invoices(df):
    res = Resultado("Sales.Invoices", "InvoiceID")
    df = df.copy()
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")

    df = res.rechazar(df, df["InvoiceDate"].isna(), "fecha_nula", "InvoiceDate nula o inválida")
    df = res.rechazar(df, df["InvoiceDate"] > pd.Timestamp.today().normalize(),
                      "fecha_futura", "InvoiceDate posterior a hoy")
    df = res.rechazar(df, df["CustomerID"].isna() | df["SalespersonPersonID"].isna(),
                      "llave_nula", "Factura sin cliente o sin vendedor")
    df = res.sin_duplicados(df)

    df["CustomerID"] = df["CustomerID"].astype("int64")
    df["SalespersonPersonID"] = df["SalespersonPersonID"].astype("int64")
    df["OrderID"] = df["OrderID"].astype("Int64")
    return df, res.rechazos()


def transformar_invoice_lines(df, facturas_validas=None):
    """facturas_validas: set de InvoiceID. Si no se pasa, se consulta stg.clean_invoices."""
    res = Resultado("Sales.InvoiceLines", "InvoiceLineID")
    df = df.copy()

    numericas = ["InvoiceID", "StockItemID", "Quantity", "UnitPrice",
                 "TaxAmount", "LineProfit", "ExtendedPrice"]
    for c in numericas:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = res.rechazar(df, df[numericas].isna().any(axis=1),
                      "campo_obligatorio_nulo", "Algún campo numérico obligatorio es nulo")
    df = res.rechazar(df, df["Quantity"] <= 0, "cantidad_no_positiva", "Quantity <= 0")
    df = res.rechazar(df, df["UnitPrice"] < 0, "precio_negativo", "UnitPrice < 0")

    # Integridad referencial: la línea debe tener su factura ya validada
    if facturas_validas is None:
        facturas_validas = set(pd.read_sql(
            "SELECT InvoiceID FROM stg.clean_invoices", dw_engine())["InvoiceID"])
    df = res.rechazar(df, ~df["InvoiceID"].isin(facturas_validas),
                      "factura_inexistente", "La factura de esta línea no está en staging clean")

    df = res.sin_duplicados(df)
    for c in ["InvoiceID", "StockItemID", "Quantity"]:
        df[c] = df[c].astype("int64")
    return df, res.rechazos()
