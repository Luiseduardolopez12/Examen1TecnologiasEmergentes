-- Bitácora del asistente de IA: qué se preguntó, qué consultas controladas se usaron y qué se respondió.
-- Ejecutar en SSMS con la base DW_Ventas seleccionada.
USE DW_Ventas;
GO

IF OBJECT_ID('audit.asistente_consultas') IS NULL
CREATE TABLE audit.asistente_consultas (
    consulta_id   INT IDENTITY(1,1) PRIMARY KEY,
    pregunta      NVARCHAR(500)  NOT NULL,
    herramientas  NVARCHAR(1000) NULL,      -- consultas controladas que se ejecutaron (JSON)
    respuesta     NVARCHAR(MAX)  NULL,
    respondida    BIT            NOT NULL,  -- 0 = el asistente dijo que no tenía el dato
    modelo        NVARCHAR(60)   NULL,
    duracion_ms   INT            NULL,
    error         NVARCHAR(500)  NULL,
    creado_en     DATETIME2      NOT NULL DEFAULT SYSDATETIME()
);
GO
