-- 02_auditoria.sql
-- Tablas de control del ETL. Cada corrida de cada paso deja una fila en etl_runs.

USE DW_Ventas;
GO

IF OBJECT_ID('audit.etl_runs') IS NULL
CREATE TABLE audit.etl_runs (
    execution_id    INT IDENTITY(1,1) PRIMARY KEY,
    pipeline_name   VARCHAR(100)  NOT NULL,
    source_object   VARCHAR(200)  NULL,
    target_object   VARCHAR(200)  NULL,
    start_time      DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    end_time        DATETIME2     NULL,
    rows_read       INT           NULL,
    rows_inserted   INT           NULL,
    rows_updated    INT           NULL,
    rows_rejected   INT           NULL,
    status          VARCHAR(20)   NOT NULL DEFAULT 'RUNNING',   -- RUNNING / SUCCESS / FAILED
    error_detail    NVARCHAR(MAX) NULL,
    watermark_start DATETIME2     NULL,
    watermark_end   DATETIME2     NULL
);
GO

-- Último valor procesado por cada objeto incremental
IF OBJECT_ID('audit.watermarks') IS NULL
CREATE TABLE audit.watermarks (
    source_object    VARCHAR(100) PRIMARY KEY,
    watermark_value  DATETIME2    NOT NULL,
    updated_at       DATETIME2    NOT NULL DEFAULT SYSDATETIME()
);
GO

-- Cuarentena: filas que no pasaron una regla de calidad
IF OBJECT_ID('audit.rejected_rows') IS NULL
CREATE TABLE audit.rejected_rows (
    rejected_id   INT IDENTITY(1,1) PRIMARY KEY,
    execution_id  INT           NOT NULL,
    source_object VARCHAR(100)  NOT NULL,
    business_key  VARCHAR(100)  NULL,
    rule_name     VARCHAR(100)  NOT NULL,
    detail        NVARCHAR(500) NULL,
    rejected_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME()
);
GO
