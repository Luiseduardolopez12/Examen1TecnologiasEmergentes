-- 07_ml.sql
-- Resultados del modelo de pronóstico: qué predijo, con qué versión y qué tan bien lo hizo.
-- Los llena ml/entrenar.py. Se puede ejecutar varias veces sin problema.

USE DW_Ventas;
GO

-- Una fila por modelo comparado en cada entrenamiento
IF OBJECT_ID('audit.ml_metricas') IS NULL
CREATE TABLE audit.ml_metricas (
    ml_metrica_id  INT IDENTITY(1,1) PRIMARY KEY,
    ml_run_id      INT           NOT NULL,       -- = audit.etl_runs.execution_id
    version        VARCHAR(30)   NOT NULL,
    modelo         VARCHAR(50)   NOT NULL,
    es_baseline    BIT           NOT NULL,
    ganador        BIT           NOT NULL,
    mae_validacion FLOAT         NOT NULL,       -- validación cruzada hacia adelante (sin tocar la prueba)
    rmse_validacion FLOAT        NOT NULL,
    mape_validacion FLOAT        NOT NULL,
    mae_prueba     FLOAT         NOT NULL,       -- últimos meses, usados una sola vez al final
    rmse_prueba    FLOAT         NOT NULL,
    mape_prueba    FLOAT         NOT NULL,
    parametros     NVARCHAR(500) NULL,
    entrenado_en   DATETIME2     NOT NULL DEFAULT SYSDATETIME()
);
GO

-- Pronóstico de ventas netas mensuales (esto es PREDICCIÓN, no dato histórico)
IF OBJECT_ID('dw.PronosticoVentas') IS NULL
CREATE TABLE dw.PronosticoVentas (
    pronostico_id   INT IDENTITY(1,1) PRIMARY KEY,
    ml_run_id       INT           NOT NULL,
    version         VARCHAR(30)   NOT NULL,
    modelo          VARCHAR(50)   NOT NULL,
    mes             CHAR(7)       NOT NULL,      -- 2016-06
    horizonte_mes   TINYINT       NOT NULL,      -- 1 = el mes siguiente al último dato
    valor           DECIMAL(18,2) NOT NULL,
    inferior        DECIMAL(18,2) NOT NULL,      -- límite inferior (80%)
    superior        DECIMAL(18,2) NOT NULL,      -- límite superior (80%)
    base_hasta      CHAR(7)       NOT NULL,      -- último mes con datos reales usado
    generado_en     DATETIME2     NOT NULL DEFAULT SYSDATETIME()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Pronostico_Run')
    CREATE INDEX IX_Pronostico_Run ON dw.PronosticoVentas (ml_run_id);
GO
