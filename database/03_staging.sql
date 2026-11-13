-- 03_staging.sql
-- Capas de staging:
--   stg.raw_*    -> las crea el ETL (pandas) tal cual llegan de la fuente. Solo se agregan filas.
--   stg.clean_*  -> datos validados, una fila por clave de negocio (se actualizan con MERGE).
--   stg.v_ready_sales_lines -> vista lista para cargar el hecho de ventas.

USE DW_Ventas;
GO

IF OBJECT_ID('stg.clean_people') IS NULL
CREATE TABLE stg.clean_people (
    PersonID       INT           NOT NULL PRIMARY KEY,
    FullName       NVARCHAR(50)  NOT NULL,
    LastEditedWhen DATETIME2     NOT NULL
);
GO

IF OBJECT_ID('stg.clean_products') IS NULL
CREATE TABLE stg.clean_products (
    StockItemID    INT            NOT NULL PRIMARY KEY,
    StockItemName  NVARCHAR(100)  NOT NULL,
    Brand          NVARCHAR(50)   NOT NULL,
    Size           NVARCHAR(20)   NOT NULL,
    GroupName      NVARCHAR(50)   NOT NULL,
    UnitPrice      DECIMAL(18,2)  NOT NULL,
    LastEditedWhen DATETIME2      NOT NULL
);
GO

IF OBJECT_ID('stg.clean_customers') IS NULL
CREATE TABLE stg.clean_customers (
    CustomerID        INT           NOT NULL PRIMARY KEY,
    CustomerName      NVARCHAR(100) NOT NULL,
    CategoryName      NVARCHAR(50)  NOT NULL,
    BuyingGroupName   NVARCHAR(50)  NOT NULL,
    CityName          NVARCHAR(50)  NOT NULL,
    StateProvinceName NVARCHAR(50)  NOT NULL,
    CountryName       NVARCHAR(60)  NOT NULL,
    SalesTerritory    NVARCHAR(50)  NOT NULL,
    LastEditedWhen    DATETIME2     NOT NULL
);
GO

IF OBJECT_ID('stg.clean_invoices') IS NULL
CREATE TABLE stg.clean_invoices (
    InvoiceID           INT       NOT NULL PRIMARY KEY,
    CustomerID          INT       NOT NULL,
    SalespersonPersonID INT       NOT NULL,
    OrderID             INT       NULL,
    InvoiceDate         DATE      NOT NULL,
    LastEditedWhen      DATETIME2 NOT NULL
);
GO

IF OBJECT_ID('stg.clean_invoice_lines') IS NULL
CREATE TABLE stg.clean_invoice_lines (
    InvoiceLineID  INT           NOT NULL PRIMARY KEY,
    InvoiceID      INT           NOT NULL,
    StockItemID    INT           NOT NULL,
    Quantity       INT           NOT NULL,
    UnitPrice      DECIMAL(18,2) NOT NULL,
    TaxAmount      DECIMAL(18,2) NOT NULL,
    LineProfit     DECIMAL(18,2) NOT NULL,
    ExtendedPrice  DECIMAL(18,2) NOT NULL,   -- total de la línea con impuesto
    LastEditedWhen DATETIME2     NOT NULL
);
GO

CREATE OR ALTER VIEW stg.v_ready_sales_lines AS
-- Una fila por línea de factura. El join factura -> línea es uno-a-muchos,
-- pero las medidas salen de la línea, así que no se multiplica nada.
SELECT  l.InvoiceLineID,
        l.InvoiceID,
        i.InvoiceDate,
        i.CustomerID,
        i.SalespersonPersonID,
        l.StockItemID,
        l.Quantity,
        l.UnitPrice,
        l.TaxAmount,
        l.LineProfit,
        l.ExtendedPrice,
        l.ExtendedPrice - l.TaxAmount AS NetSales,   -- venta neta = sin impuesto
        l.LastEditedWhen
FROM    stg.clean_invoice_lines l
JOIN    stg.clean_invoices i ON i.InvoiceID = l.InvoiceID;
GO
