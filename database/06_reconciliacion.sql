-- 06_reconciliacion.sql
-- Compara conteos y totales entre origen, staging y Data Warehouse.
-- Las diferencias deben explicarse con las filas de audit.rejected_rows.

USE DW_Ventas;
GO

-- 1) Línea de factura: origen vs staging vs DW
SELECT 'Origen (WideWorldImporters)' AS capa,
       COUNT(*) AS filas, SUM(CAST(Quantity AS BIGINT)) AS cantidad,
       SUM(ExtendedPrice) AS total_con_impuesto, SUM(LineProfit) AS ganancia
FROM WideWorldImporters.Sales.InvoiceLines
UNION ALL
SELECT 'Staging clean', COUNT(*), SUM(CAST(Quantity AS BIGINT)), SUM(ExtendedPrice), SUM(LineProfit)
FROM stg.clean_invoice_lines
UNION ALL
SELECT 'DW FactSales', COUNT(*), SUM(CAST(Quantity AS BIGINT)), SUM(ExtendedPrice), SUM(LineProfit)
FROM dw.FactSales;

-- 2) Rechazos por regla (explican diferencias entre capas)
SELECT source_object, rule_name, COUNT(*) AS filas
FROM audit.rejected_rows
GROUP BY source_object, rule_name
ORDER BY filas DESC;

-- 3) Venta neta: DW vs cálculo independiente desde el origen (cantidad x precio)
SELECT (SELECT SUM(NetSales) FROM dw.FactSales) AS neta_dw,
       (SELECT SUM(Quantity * UnitPrice) FROM WideWorldImporters.Sales.InvoiceLines) AS neta_origen;

-- 4) Hechos que cayeron en el miembro "Desconocido"
SELECT SUM(CASE WHEN CustomerKey = -1 THEN 1 ELSE 0 END)    AS sin_cliente,
       SUM(CASE WHEN ProductKey = -1 THEN 1 ELSE 0 END)     AS sin_producto,
       SUM(CASE WHEN SalespersonKey = -1 THEN 1 ELSE 0 END) AS sin_vendedor
FROM dw.FactSales;

-- 5) Versiones SCD2: clientes con más de una versión
SELECT CustomerID, COUNT(*) AS versiones
FROM dw.DimCustomer
WHERE CustomerKey <> -1
GROUP BY CustomerID
HAVING COUNT(*) > 1;

-- 6) Última ejecución de cada paso
SELECT TOP 20 execution_id, pipeline_name, status, rows_read, rows_inserted, rows_updated,
       rows_rejected, start_time, end_time
FROM audit.etl_runs
ORDER BY execution_id DESC;
