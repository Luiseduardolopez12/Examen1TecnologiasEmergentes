# Requerimientos

## Funcionales

| # | Requerimiento | Dónde se cumple |
|---|---------------|-----------------|
| RF1 | Extraer las ventas de WideWorldImporters en carga completa e incremental | `etl/extract.py`, `etl/run_pipeline.py` |
| RF2 | Conservar lo que llega de la fuente (raw) separado de los datos preparados (clean) | `stg.raw_*`, `stg.clean_*` |
| RF3 | Rechazar filas inválidas sin detener la carga y dejarlas registradas | `etl/transform.py`, `audit.rejected_rows` |
| RF4 | Cargar un Data Warehouse dimensional con historia en clientes (SCD tipo 2) | `database/04` y `05`, esquema `dw` |
| RF5 | Registrar cada ejecución: conteos, estado, error y watermark | `audit.etl_runs`, `audit.watermarks` |
| RF6 | Comparar conteos y totales entre origen, staging y DW | `database/06_reconciliacion.sql` |
| RF7 | Exponer los datos del DW por una API con login, filtros y paginación | `api/` |
| RF8 | Mostrar un dashboard con KPIs, filtros, gráficos, detalle y monitoreo del ETL | `dashboard/` |
| RF9 | Pronosticar las ventas de los próximos 6 meses frente a un baseline, con métricas y marcado como predicción | `ml/`, `dw.PronosticoVentas` |
| RF10 | Responder preguntas en lenguaje natural solo con datos del DW y reconocer lo que no sabe | `ia/` |
| RF11 | Generar alertas cuando las ventas caen más del umbral, registrarlas, mostrarlas y no duplicarlas | `alertas/`, `audit.alertas` |

## No funcionales

| Tema | Requerimiento | Cómo se resuelve |
|------|---------------|------------------|
| Reproducibilidad | Otra persona debe poder ejecutarlo con el README | Scripts SQL numerados, `requirements.txt`, `.env.example`, [manual](12_manuales.md) |
| Idempotencia | Reejecutar una carga no duplica ni cuenta cambios falsos | `MERGE` con comparación `EXCEPT`, `UNIQUE (InvoiceLineID)`, alertas únicas por regla y periodo |
| Trazabilidad | Poder rastrear un dato hasta la corrida que lo cargó | `execution_id` en raw, hechos, pronósticos y alertas |
| Seguridad | El navegador nunca habla con SQL Server; la API solo lee; sin secretos en el repositorio | API con token firmado, consultas con parámetros, `.env` fuera de Git |
| Honestidad de los datos | Lo predicho y lo generado por IA debe distinguirse de lo real | Etiqueta "PREDICCIÓN", respuestas con la consulta usada como fuente |
| Calidad | Reglas de limpieza y de negocio probadas automáticamente | 64 pruebas con `pytest` ([resultados](11_pruebas.md)) |
| Usabilidad | Legible en pantalla grande y en celular, en tema claro y oscuro | Dashboard Angular con variables de color |
| Costo | Sin licencias de pago | SQL Server Express, Python, Angular y la capa gratis de Gemini |

## Fuera de alcance

- Datos en tiempo real: la carga es por lotes y se ejecuta bajo demanda.
- Orquestación con Airflow y despliegue con Docker: no hacen falta para este tamaño; el ETL se puede programar con el Programador de tareas de Windows.
- Correo electrónico (SMTP): las alertas se entregan en el dashboard.
- Propagar eliminaciones de la fuente: WideWorldImporters no borra facturas.
