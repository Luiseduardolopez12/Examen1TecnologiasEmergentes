-- 01_crear_base_y_esquemas.sql
-- Crea la base del Data Warehouse y los tres esquemas que usamos:
--   stg   -> staging (raw + clean)
--   dw    -> modelo dimensional
--   audit -> control de ejecuciones, watermarks y rechazos
-- Se puede ejecutar varias veces sin problema.

IF DB_ID('DW_Ventas') IS NULL
    CREATE DATABASE DW_Ventas;
GO

USE DW_Ventas;
GO

IF SCHEMA_ID('stg')   IS NULL EXEC('CREATE SCHEMA stg');
IF SCHEMA_ID('dw')    IS NULL EXEC('CREATE SCHEMA dw');
IF SCHEMA_ID('audit') IS NULL EXEC('CREATE SCHEMA audit');
GO
