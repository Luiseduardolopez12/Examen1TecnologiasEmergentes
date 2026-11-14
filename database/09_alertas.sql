-- Alertas de negocio: una fila por regla + periodo + ámbito. La restricción UNIQUE evita duplicados
-- aunque la evaluación se corra varias veces. Ejecutar en SSMS con DW_Ventas seleccionada.
USE DW_Ventas;
GO

IF OBJECT_ID('audit.alertas') IS NULL
CREATE TABLE audit.alertas (
    alerta_id        INT IDENTITY(1,1) PRIMARY KEY,
    regla            NVARCHAR(40)  NOT NULL,   -- caida_mensual | caida_interanual
    periodo          CHAR(7)       NOT NULL,   -- mes evaluado, AAAA-MM
    ambito           NVARCHAR(60)  NOT NULL DEFAULT 'Global',
    valor_actual     DECIMAL(18,2) NOT NULL,   -- ventas netas del periodo
    valor_referencia DECIMAL(18,2) NOT NULL,   -- ventas netas con las que se comparó
    variacion_pct    DECIMAL(9,2)  NOT NULL,   -- negativo = caída
    umbral_pct       DECIMAL(9,2)  NOT NULL,   -- umbral vigente cuando se disparó
    severidad        NVARCHAR(10)  NOT NULL,   -- MEDIA | ALTA
    mensaje          NVARCHAR(400) NOT NULL,
    estado           NVARCHAR(10)  NOT NULL DEFAULT 'NUEVA'
                     CONSTRAINT CK_alertas_estado CHECK (estado IN ('NUEVA', 'REVISADA')),
    execution_id     INT           NULL,       -- corrida de audit.etl_runs que la generó
    creado_en        DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    revisada_en      DATETIME2     NULL,
    CONSTRAINT UQ_alertas_regla_periodo UNIQUE (regla, periodo, ambito)
);
GO
