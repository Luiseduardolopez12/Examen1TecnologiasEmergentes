-- 05_cargas_dw.sql
-- Procedimientos que mueven datos de stg.clean_* hacia el Data Warehouse.
-- Todos son idempotentes: correrlos dos veces seguidas no duplica nada.

USE DW_Ventas;
GO

-- ---------- Vendedores (Tipo 1: se sobrescribe) ----------
CREATE OR ALTER PROCEDURE dw.usp_load_dim_salesperson AS
BEGIN
    SET NOCOUNT ON;
    MERGE dw.DimSalesperson AS t
    USING stg.clean_people AS s ON t.PersonID = s.PersonID
    WHEN MATCHED AND t.FullName <> s.FullName THEN
        UPDATE SET t.FullName = s.FullName
    WHEN NOT MATCHED THEN
        INSERT (PersonID, FullName) VALUES (s.PersonID, s.FullName);
END
GO

-- ---------- Productos (Tipo 1) ----------
CREATE OR ALTER PROCEDURE dw.usp_load_dim_product AS
BEGIN
    SET NOCOUNT ON;
    MERGE dw.DimProduct AS t
    USING stg.clean_products AS s ON t.StockItemID = s.StockItemID
    WHEN MATCHED AND EXISTS (
            SELECT s.StockItemName, s.Brand, s.Size, s.GroupName
            EXCEPT
            SELECT t.StockItemName, t.Brand, t.Size, t.GroupName) THEN
        UPDATE SET t.StockItemName = s.StockItemName, t.Brand = s.Brand,
                   t.Size = s.Size, t.GroupName = s.GroupName
    WHEN NOT MATCHED THEN
        INSERT (StockItemID, StockItemName, Brand, Size, GroupName)
        VALUES (s.StockItemID, s.StockItemName, s.Brand, s.Size, s.GroupName);
END
GO

-- ---------- Clientes (Tipo 2 para categoría, grupo de compra y ubicación) ----------
-- El nombre se trata como Tipo 1 (corregir un nombre no cambia la historia).
-- La fecha del cambio sale de ValidFrom de la tabla temporal de la fuente.
CREATE OR ALTER PROCEDURE dw.usp_load_dim_customer AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    BEGIN TRAN;

    -- 1) Nombre: sobrescribir en todas las versiones
    UPDATE d SET d.CustomerName = s.CustomerName
    FROM dw.DimCustomer d
    JOIN stg.clean_customers s ON s.CustomerID = d.CustomerID
    WHERE d.CustomerKey <> -1 AND d.CustomerName <> s.CustomerName;

    -- 2) Detectar clientes cuya versión vigente cambió en atributos históricos
    SELECT s.CustomerID, CAST(s.LastEditedWhen AS DATE) AS FechaCambio
    INTO #cambios
    FROM stg.clean_customers s
    JOIN dw.DimCustomer d ON d.CustomerID = s.CustomerID AND d.IsCurrent = 1
    WHERE EXISTS (
        SELECT s.CategoryName, s.BuyingGroupName, s.CityName, s.StateProvinceName, s.CountryName, s.SalesTerritory
        EXCEPT
        SELECT d.CategoryName, d.BuyingGroupName, d.CityName, d.StateProvinceName, d.CountryName, d.SalesTerritory);

    -- 3) Cerrar la versión anterior
    UPDATE d SET d.ValidTo = DATEADD(DAY, -1, c.FechaCambio), d.IsCurrent = 0
    FROM dw.DimCustomer d
    JOIN #cambios c ON c.CustomerID = d.CustomerID
    WHERE d.IsCurrent = 1;

    -- 4) Insertar versión nueva (clientes nuevos y clientes que acaban de cambiar)
    INSERT dw.DimCustomer (CustomerID, CustomerName, CategoryName, BuyingGroupName, CityName,
                           StateProvinceName, CountryName, SalesTerritory, ValidFrom, ValidTo, IsCurrent)
    SELECT s.CustomerID, s.CustomerName, s.CategoryName, s.BuyingGroupName, s.CityName,
           s.StateProvinceName, s.CountryName, s.SalesTerritory,
           CASE WHEN EXISTS (SELECT 1 FROM dw.DimCustomer x WHERE x.CustomerID = s.CustomerID)
                THEN CAST(s.LastEditedWhen AS DATE)    -- cambio: vigente desde la fecha del cambio
                ELSE CAST('1900-01-01' AS DATE)        -- cliente nuevo: cubre todo el historial
           END,
           '9999-12-31', 1
    FROM stg.clean_customers s
    WHERE NOT EXISTS (SELECT 1 FROM dw.DimCustomer d WHERE d.CustomerID = s.CustomerID AND d.IsCurrent = 1);

    DROP TABLE #cambios;
    COMMIT;
END
GO

-- ---------- Hechos de ventas ----------
-- Primero se resuelven las claves sustitutas; si no hay match se usa -1 (Desconocido).
-- El cliente se busca por la versión vigente en la fecha de la factura.
-- Devuelve (insertadas, actualizadas) para la auditoría.
CREATE OR ALTER PROCEDURE dw.usp_load_fact_sales @execution_id INT AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @acc TABLE (accion NVARCHAR(10));

    MERGE dw.FactSales AS t
    USING (
        SELECT  r.InvoiceLineID, r.InvoiceID,
                YEAR(r.InvoiceDate) * 10000 + MONTH(r.InvoiceDate) * 100 + DAY(r.InvoiceDate) AS DateKey,
                ISNULL(c.CustomerKey, -1)    AS CustomerKey,
                ISNULL(p.ProductKey, -1)     AS ProductKey,
                ISNULL(v.SalespersonKey, -1) AS SalespersonKey,
                r.Quantity, r.UnitPrice, r.TaxAmount, r.LineProfit, r.ExtendedPrice, r.NetSales
        FROM stg.v_ready_sales_lines r
        LEFT JOIN dw.DimCustomer    c ON c.CustomerID = r.CustomerID
                                      AND r.InvoiceDate BETWEEN c.ValidFrom AND c.ValidTo
        LEFT JOIN dw.DimProduct     p ON p.StockItemID = r.StockItemID
        LEFT JOIN dw.DimSalesperson v ON v.PersonID = r.SalespersonPersonID
    ) AS s ON t.InvoiceLineID = s.InvoiceLineID
    WHEN MATCHED AND (   t.Quantity <> s.Quantity OR t.UnitPrice <> s.UnitPrice
                      OR t.TaxAmount <> s.TaxAmount OR t.LineProfit <> s.LineProfit
                      OR t.ExtendedPrice <> s.ExtendedPrice OR t.NetSales <> s.NetSales
                      OR t.CustomerKey <> s.CustomerKey OR t.ProductKey <> s.ProductKey
                      OR t.SalespersonKey <> s.SalespersonKey OR t.DateKey <> s.DateKey) THEN
        UPDATE SET t.DateKey = s.DateKey, t.CustomerKey = s.CustomerKey, t.ProductKey = s.ProductKey,
                   t.SalespersonKey = s.SalespersonKey, t.Quantity = s.Quantity, t.UnitPrice = s.UnitPrice,
                   t.TaxAmount = s.TaxAmount, t.LineProfit = s.LineProfit,
                   t.ExtendedPrice = s.ExtendedPrice, t.NetSales = s.NetSales,
                   t.LoadExecutionId = @execution_id
    WHEN NOT MATCHED THEN
        INSERT (InvoiceLineID, InvoiceID, DateKey, CustomerKey, ProductKey, SalespersonKey,
                Quantity, UnitPrice, TaxAmount, LineProfit, ExtendedPrice, NetSales, LoadExecutionId)
        VALUES (s.InvoiceLineID, s.InvoiceID, s.DateKey, s.CustomerKey, s.ProductKey, s.SalespersonKey,
                s.Quantity, s.UnitPrice, s.TaxAmount, s.LineProfit, s.ExtendedPrice, s.NetSales, @execution_id)
    OUTPUT $action INTO @acc;

    SELECT  ISNULL(SUM(CASE WHEN accion = 'INSERT' THEN 1 ELSE 0 END), 0) AS insertadas,
            ISNULL(SUM(CASE WHEN accion = 'UPDATE' THEN 1 ELSE 0 END), 0) AS actualizadas
    FROM @acc;
END
GO
