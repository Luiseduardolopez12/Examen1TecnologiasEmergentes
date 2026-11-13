-- 04_data_warehouse.sql
-- Modelo dimensional (esquema estrella) del proceso de VENTAS.
-- GRANO de FactSales: una fila por línea de factura (Sales.InvoiceLines).

USE DW_Ventas;
GO

-- ---------- DimDate ----------
IF OBJECT_ID('dw.DimDate') IS NULL
CREATE TABLE dw.DimDate (
    DateKey    INT         NOT NULL PRIMARY KEY,      -- yyyymmdd
    FullDate   DATE        NOT NULL,
    [Day]      TINYINT     NOT NULL,
    [Month]    TINYINT     NOT NULL,
    MonthName  VARCHAR(20) NOT NULL,
    [Quarter]  TINYINT     NOT NULL,
    [Year]     SMALLINT    NOT NULL,
    DayOfWeek  TINYINT     NOT NULL,                  -- 1 = lunes ... 7 = domingo
    DayName    VARCHAR(20) NOT NULL,
    IsWeekend  BIT         NOT NULL,
    YearMonth  CHAR(7)     NOT NULL                   -- 2016-05
);
GO

IF NOT EXISTS (SELECT 1 FROM dw.DimDate)
BEGIN
    ;WITH n AS (
        SELECT TOP (DATEDIFF(DAY, '2012-01-01', '2030-12-31') + 1)
               ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS i
        FROM sys.all_objects a CROSS JOIN sys.all_objects b
    ), f AS (
        SELECT DATEADD(DAY, i, CAST('2012-01-01' AS DATE)) AS d FROM n
    )
    INSERT dw.DimDate (DateKey, FullDate, [Day], [Month], MonthName, [Quarter], [Year],
                       DayOfWeek, DayName, IsWeekend, YearMonth)
    SELECT  YEAR(d) * 10000 + MONTH(d) * 100 + DAY(d),
            d, DAY(d), MONTH(d),
            FORMAT(d, 'MMMM', 'es-ES'),
            DATEPART(QUARTER, d), YEAR(d),
            (DATEDIFF(DAY, '2012-01-02', d) % 7) + 1,           -- 2012-01-02 fue lunes
            FORMAT(d, 'dddd', 'es-ES'),
            CASE WHEN (DATEDIFF(DAY, '2012-01-02', d) % 7) + 1 >= 6 THEN 1 ELSE 0 END,
            FORMAT(d, 'yyyy-MM')
    FROM f;
END
GO

-- ---------- DimCustomer (SCD Tipo 2) ----------
IF OBJECT_ID('dw.DimCustomer') IS NULL
CREATE TABLE dw.DimCustomer (
    CustomerKey       INT IDENTITY(1,1) PRIMARY KEY,   -- clave sustituta
    CustomerID        INT           NOT NULL,          -- clave de negocio
    CustomerName      NVARCHAR(100) NOT NULL,
    CategoryName      NVARCHAR(50)  NOT NULL,
    BuyingGroupName   NVARCHAR(50)  NOT NULL,
    CityName          NVARCHAR(50)  NOT NULL,
    StateProvinceName NVARCHAR(50)  NOT NULL,
    CountryName       NVARCHAR(60)  NOT NULL,
    SalesTerritory    NVARCHAR(50)  NOT NULL,
    ValidFrom         DATE          NOT NULL,
    ValidTo           DATE          NOT NULL,
    IsCurrent         BIT           NOT NULL
);
GO
-- Solo puede haber una versión vigente por cliente
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_DimCustomer_Current')
    CREATE UNIQUE INDEX UX_DimCustomer_Current ON dw.DimCustomer (CustomerID) WHERE IsCurrent = 1;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_DimCustomer_BK')
    CREATE INDEX IX_DimCustomer_BK ON dw.DimCustomer (CustomerID, ValidFrom, ValidTo);
GO

-- ---------- DimProduct (SCD Tipo 1) ----------
IF OBJECT_ID('dw.DimProduct') IS NULL
CREATE TABLE dw.DimProduct (
    ProductKey    INT IDENTITY(1,1) PRIMARY KEY,
    StockItemID   INT           NOT NULL UNIQUE,
    StockItemName NVARCHAR(100) NOT NULL,
    Brand         NVARCHAR(50)  NOT NULL,
    Size          NVARCHAR(20)  NOT NULL,
    GroupName     NVARCHAR(50)  NOT NULL
);
GO

-- ---------- DimSalesperson (SCD Tipo 1) ----------
IF OBJECT_ID('dw.DimSalesperson') IS NULL
CREATE TABLE dw.DimSalesperson (
    SalespersonKey INT IDENTITY(1,1) PRIMARY KEY,
    PersonID       INT          NOT NULL UNIQUE,
    FullName       NVARCHAR(50) NOT NULL
);
GO

-- ---------- Miembros "Desconocido" (clave -1) ----------
IF NOT EXISTS (SELECT 1 FROM dw.DimCustomer WHERE CustomerKey = -1)
BEGIN
    SET IDENTITY_INSERT dw.DimCustomer ON;
    INSERT dw.DimCustomer (CustomerKey, CustomerID, CustomerName, CategoryName, BuyingGroupName,
                           CityName, StateProvinceName, CountryName, SalesTerritory,
                           ValidFrom, ValidTo, IsCurrent)
    VALUES (-1, -1, N'Desconocido', N'Desconocido', N'Desconocido', N'Desconocido',
            N'Desconocido', N'Desconocido', N'Desconocido', '1900-01-01', '9999-12-31', 1);
    SET IDENTITY_INSERT dw.DimCustomer OFF;
END
IF NOT EXISTS (SELECT 1 FROM dw.DimProduct WHERE ProductKey = -1)
BEGIN
    SET IDENTITY_INSERT dw.DimProduct ON;
    INSERT dw.DimProduct (ProductKey, StockItemID, StockItemName, Brand, Size, GroupName)
    VALUES (-1, -1, N'Desconocido', N'Desconocido', N'Desconocido', N'Desconocido');
    SET IDENTITY_INSERT dw.DimProduct OFF;
END
IF NOT EXISTS (SELECT 1 FROM dw.DimSalesperson WHERE SalespersonKey = -1)
BEGIN
    SET IDENTITY_INSERT dw.DimSalesperson ON;
    INSERT dw.DimSalesperson (SalespersonKey, PersonID, FullName) VALUES (-1, -1, N'Desconocido');
    SET IDENTITY_INSERT dw.DimSalesperson OFF;
END
GO

-- ---------- FactSales ----------
IF OBJECT_ID('dw.FactSales') IS NULL
CREATE TABLE dw.FactSales (
    SalesKey        BIGINT IDENTITY(1,1) PRIMARY KEY,
    InvoiceLineID   INT           NOT NULL UNIQUE,     -- dimensión degenerada, evita duplicados
    InvoiceID       INT           NOT NULL,
    DateKey         INT           NOT NULL REFERENCES dw.DimDate (DateKey),
    CustomerKey     INT           NOT NULL REFERENCES dw.DimCustomer (CustomerKey),
    ProductKey      INT           NOT NULL REFERENCES dw.DimProduct (ProductKey),
    SalespersonKey  INT           NOT NULL REFERENCES dw.DimSalesperson (SalespersonKey),
    Quantity        INT           NOT NULL,            -- aditiva
    UnitPrice       DECIMAL(18,2) NOT NULL,            -- NO aditiva (se promedia ponderado)
    TaxAmount       DECIMAL(18,2) NOT NULL,            -- aditiva
    LineProfit      DECIMAL(18,2) NOT NULL,            -- aditiva
    ExtendedPrice   DECIMAL(18,2) NOT NULL,            -- aditiva (con impuesto)
    NetSales        DECIMAL(18,2) NOT NULL,            -- aditiva (sin impuesto)
    LoadExecutionId INT           NULL,
    LoadedAt        DATETIME2     NOT NULL DEFAULT SYSDATETIME()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactSales_Date')
    CREATE INDEX IX_FactSales_Date ON dw.FactSales (DateKey) INCLUDE (NetSales, Quantity, LineProfit);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactSales_Customer')
    CREATE INDEX IX_FactSales_Customer ON dw.FactSales (CustomerKey);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_FactSales_Product')
    CREATE INDEX IX_FactSales_Product ON dw.FactSales (ProductKey);
GO
