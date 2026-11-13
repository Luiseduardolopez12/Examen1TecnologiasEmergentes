# Plataforma de Ingeniería de Datos y Analítica Inteligente

Proyecto de Tecnologías Emergentes. Toma las ventas de **WideWorldImporters** (SQL Server),
las limpia en un área de staging, las carga en un Data Warehouse dimensional y encima de eso
construye un dashboard, un modelo de predicción, un asistente con IA y alertas.

## Flujo

```
WideWorldImporters -> ETL (Python) -> stg.raw -> stg.clean -> DW_Ventas (estrella)
                                                                 |-> API (FastAPI) -> Dashboard (Angular)
                                                                 |-> Modelo ML (scikit-learn)
                                                                 |-> Asistente IA
                                                                 '-> Alertas
```

Todo vive en la base `DW_Ventas` con tres esquemas: `stg` (staging), `dw` (modelo dimensional)
y `audit` (ejecuciones, watermarks y filas rechazadas).

## Estado

| Fase | Estado |
|------|--------|
| 1-2 Descubrimiento y diseño | listo (ver `documentation/`) |
| 3 ETL y calidad | listo |
| 4 Data Warehouse | listo |
| 5 Dashboard + API | pendiente |
| 6 ML + IA generativa | pendiente |
| 7 Alertas y monitoreo | pendiente |
| 8 Integración, docs y video | pendiente |

## Requisitos

- SQL Server (Express o Developer) + SSMS
- Base `WideWorldImporters` restaurada
- Python 3.11+
- ODBC Driver 18 for SQL Server
- Git / GitHub Desktop

## Cómo ejecutarlo

1. Clona el repo y crea el entorno de Python:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copia `.env.example` a `.env` y pon el nombre de tu instancia en `SQL_SERVER`.
3. En SSMS, ejecuta en orden los scripts de `database/` (01 al 05).
4. Primera carga completa:
   ```
   python -m etl.run_pipeline --modo full
   ```
5. Valida con `database/06_reconciliacion.sql`.
6. Pruebas de las reglas de calidad:
   ```
   python -m pytest
   ```

## Carga incremental

```
python -m etl.run_pipeline --modo incremental
```

Usa un watermark por tabla (`audit.watermarks`) con 24 horas de solapamiento. Para probarla,
corre `tests/sql/simular_cambios_origen.sql` (modifica WideWorldImporters) y vuelve a ejecutar.

## Perfilado de datos

```
python -m etl.profiling
```

## Estructura

```
database/        scripts SQL en orden de ejecución
etl/             extracción, transformación, carga y orquestación
tests/           pruebas automáticas y scripts de simulación
documentation/   alcance, decisiones, perfilado
```

## Reiniciar el ambiente

Borra la base `DW_Ventas` en SSMS y repite desde el paso 3. La fuente no se toca
(salvo que hayas corrido el script de simulación).
