"""Extracción desde WideWorldImporters.

Las consultas de dimensiones hacen joins con catálogos (relación uno-a-uno por clave),
así que no multiplican filas. En WWI las tablas de catálogo son temporales: no tienen
LastEditedWhen sino ValidFrom (inicio de la versión actual), por eso se renombra.
"""
import pandas as pd
from sqlalchemy import text

from etl.config import source_engine

CONSULTAS = {
    "people": """
        SELECT PersonID, FullName, ValidFrom AS LastEditedWhen
        FROM Application.People
        WHERE IsSalesperson = 1""",

    "products": """
        SELECT s.StockItemID, s.StockItemName, s.Brand, s.Size, s.UnitPrice,
               g.StockGroupName AS GroupName, s.ValidFrom AS LastEditedWhen
        FROM Warehouse.StockItems s
        -- un producto puede estar en varios grupos: tomamos el de menor ID para no duplicar filas
        LEFT JOIN (SELECT StockItemID, MIN(StockGroupID) AS StockGroupID
                   FROM Warehouse.StockItemStockGroups GROUP BY StockItemID) m
               ON m.StockItemID = s.StockItemID
        LEFT JOIN Warehouse.StockGroups g ON g.StockGroupID = m.StockGroupID""",

    "customers": """
        SELECT c.CustomerID, c.CustomerName, cc.CustomerCategoryName AS CategoryName,
               bg.BuyingGroupName, ci.CityName, sp.StateProvinceName, co.CountryName,
               sp.SalesTerritory, c.ValidFrom AS LastEditedWhen
        FROM Sales.Customers c
        JOIN Sales.CustomerCategories cc ON cc.CustomerCategoryID = c.CustomerCategoryID
        LEFT JOIN Sales.BuyingGroups bg  ON bg.BuyingGroupID = c.BuyingGroupID
        JOIN Application.Cities ci          ON ci.CityID = c.DeliveryCityID
        JOIN Application.StateProvinces sp  ON sp.StateProvinceID = ci.StateProvinceID
        JOIN Application.Countries co       ON co.CountryID = sp.CountryID""",

    # Estas dos son incrementales: se les agrega WHERE LastEditedWhen > :desde
    "invoices": """
        SELECT InvoiceID, CustomerID, SalespersonPersonID, OrderID,
               CAST(InvoiceDate AS DATETIME2) AS InvoiceDate, LastEditedWhen
        FROM Sales.Invoices""",

    "invoice_lines": """
        SELECT InvoiceLineID, InvoiceID, StockItemID, Quantity, UnitPrice,
               TaxAmount, LineProfit, ExtendedPrice, LastEditedWhen
        FROM Sales.InvoiceLines""",
}

# objetos que se cargan de forma incremental y su columna de control
INCREMENTALES = {"invoices": "LastEditedWhen", "invoice_lines": "LastEditedWhen"}


def extraer(nombre, desde=None):
    sql = CONSULTAS[nombre]
    params = {}
    if desde is not None:
        sql += f" WHERE {INCREMENTALES[nombre]} > :desde"
        params["desde"] = desde
    return pd.read_sql(text(sql), source_engine(), params=params)
