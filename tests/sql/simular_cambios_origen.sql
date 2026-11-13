-- simular_cambios_origen.sql
-- ATENCIÓN: esto modifica la base WideWorldImporters (es solo para probar la carga incremental
-- y el SCD Tipo 2). Después corre:   python -m etl.run_pipeline --modo incremental
-- Y luego revisa 06_reconciliacion.sql (punto 5 muestra el cliente con 2 versiones).

USE WideWorldImporters;
GO

-- 1) El cliente 2 cambia de categoría -> debe crear una versión nueva en DimCustomer (SCD2)
UPDATE Sales.Customers
SET CustomerCategoryID = (SELECT CustomerCategoryID FROM Sales.CustomerCategories
                          WHERE CustomerCategoryName = N'Supermarket')
WHERE CustomerID = 2;

-- 2) Cinco líneas "tocadas" sin cambiar valores -> en staging cuentan como actualizadas (cambió LastEditedWhen), pero en el DW no cambia nada
UPDATE TOP (5) Sales.InvoiceLines SET LastEditedWhen = SYSDATETIME();

-- 3) Una línea con cambio real de valor -> debe contar como 1 actualizada en el DW
UPDATE TOP (1) Sales.InvoiceLines
SET LineProfit = LineProfit + 10, LastEditedWhen = SYSDATETIME()
WHERE InvoiceLineID = (SELECT MAX(InvoiceLineID) FROM Sales.InvoiceLines);
GO

/* Para deshacer el cambio de categoría (si quieres repetir la prueba):
UPDATE Sales.Customers
SET CustomerCategoryID = (SELECT CustomerCategoryID FROM Sales.CustomerCategories
                          WHERE CustomerCategoryName = N'Novelty Shop')
WHERE CustomerID = 2;
-- (confirma antes la categoría original del cliente 2 con un SELECT previo)
*/
