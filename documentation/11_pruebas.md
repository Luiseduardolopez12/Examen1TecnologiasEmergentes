# Plan y resultados de pruebas

## Pruebas automáticas

`python -m pytest` → **64 pruebas, todas pasan**. Ninguna necesita SQL Server ni Gemini (usan datos y servicios falsos), así que se pueden correr en cualquier equipo.

| Archivo | Pruebas | Qué cubre |
|---|---:|---|
| `tests/test_transform.py` | 7 | Reglas de calidad del ETL con datos sintéticos |
| `tests/test_datos_sucios.py` | 2 | Filas sucias fabricadas: cuántas se rechazan y cuántas pasan |
| `tests/test_api.py` | 12 | Login, token, filtros como parámetros, rangos, paginación, pronóstico |
| `tests/test_ml.py` | 11 | Serie mensual, división temporal sin fuga, baseline, modelos y errores |
| `tests/test_asistente.py` | 17 | Catálogo, validaciones, plan inválido, reintentos y respaldo de Gemini |
| `tests/test_alertas.py` | 15 | Reglas de disparo y no disparo, duplicados, endpoints |

## Pruebas de la guía

| Prueba | Qué debe demostrarse | Cómo se hizo | Estado |
|---|---|---|---|
| Carga inicial | Se carga el conjunto y se registran conteos | `etl.run_pipeline --modo full`: 10 personas, 227 productos, 663 clientes, 70,510 facturas y 228,265 líneas; ejecuciones 1 a 6 en `audit.etl_runs` | ✅ |
| Carga incremental | Se detectan cambios sin duplicar | `tests/sql/simular_cambios_origen.sql` + `--modo incremental`: el cliente cambiado queda con 2 versiones (SCD2), las líneas tocadas se actualizan sin duplicar | ✅ |
| Idempotencia | Reejecutar no duplica ni altera | Incremental sin cambios: se leyeron 162 facturas y 284 líneas por el solapamiento y se insertó y actualizó 0. La evaluación de alertas repetida da 0 nuevas | ✅ |
| Nulos y duplicados | Reglas aplicadas y casos documentados | Catálogo en [ETL y calidad](07_etl_y_calidad.md); `tests.datos_sucios` produce 13 rechazos en `audit.rejected_rows` | ✅ |
| Integridad | Huérfanos y política definida | Regla `factura_inexistente`; hechos sin dimensión van a `-1 Desconocido`; consulta 4 de `06_reconciliacion.sql` | ✅ |
| Recuperación | Una falla controlada se reintenta sin inconsistencias | Procedimiento abajo | ⬜ por registrar |
| Reconciliación | Conteos y medidas entre capas | `06_reconciliacion.sql`: 228,265 líneas en origen, `stg.clean_invoice_lines` y `dw.FactSales`; venta neta del DW contra `Quantity × UnitPrice` del origen | ✅ |
| Dashboard | KPI iguales a SQL independiente | Procedimiento abajo | ⬜ por registrar |
| ML | Baseline, evaluación independiente, límites | [Modelo de predicción](02_modelo_prediccion.md): 5 modelos contra el baseline, 6 meses de prueba usados una sola vez | ✅ |
| GenAI | Respuestas contra métricas reales; rechaza lo no respaldado | 10 preguntas con datos reales ([asistente](09_asistente_ia.md), `evidencias/preguntas_asistente.md`) | ✅ |
| Alertas | Disparo, no disparo, registro y entrega | 2016-05 no dispara; 2013-02 dispara (−26.4 %); repetirla no duplica; aviso en el dashboard ([alertas](10_alertas.md)) | ✅ |
| End-to-end | Flujo completo hasta lo visible | Procedimiento abajo | ⬜ por registrar |

## Procedimientos pendientes

### Recuperación tras una falla

1. Anota el estado actual en SSMS (`DW_Ventas`):
   ```sql
   SELECT (SELECT COUNT(*) FROM dw.FactSales) AS hechos,
          (SELECT COUNT(*) FROM stg.clean_invoice_lines) AS lineas,
          (SELECT MAX(watermark_value) FROM audit.watermarks WHERE source_object = 'invoice_lines') AS watermark;
   ```
2. Provoca una falla controlada apuntando a una base de origen que no existe:
   ```powershell
   $env:SOURCE_DB = "NoExiste"
   python -m etl.run_pipeline --modo incremental
   Remove-Item Env:SOURCE_DB
   ```
3. Revisa que quedó una corrida `FAILED` con el error y que los números del paso 1 **no cambiaron**:
   ```sql
   SELECT TOP 3 execution_id, pipeline_name, status, error_detail FROM audit.etl_runs ORDER BY execution_id DESC;
   ```
4. Reintenta normal: `python -m etl.run_pipeline --modo incremental` y vuelve a correr la consulta del paso 1.

**Resultado esperado:** la corrida fallida queda registrada, el watermark no avanzó, y tras el reintento no hay duplicados (mismos hechos y líneas).
**Resultado obtenido:** _anota aquí lo que viste._

### KPI del dashboard contra SQL independiente

Corre esto en SSMS, directo contra el origen (sin pasar por el DW), y compara con las tarjetas del dashboard sin filtros:

```sql
SELECT SUM(il.Quantity * il.UnitPrice)        AS ventas_netas,
       SUM(il.LineProfit)                     AS ganancia,
       SUM(il.Quantity)                       AS unidades,
       COUNT(DISTINCT il.InvoiceID)           AS facturas,
       COUNT(DISTINCT i.CustomerID)           AS clientes
FROM WideWorldImporters.Sales.InvoiceLines il
JOIN WideWorldImporters.Sales.Invoices i ON i.InvoiceID = il.InvoiceID;
```

**En el dashboard:** ventas netas $172,261,341 · ganancia $85,729,191 · 8,950,628 unidades · 70,510 facturas · 663 clientes.
**En SQL:** _anota aquí los valores._

### Flujo de punta a punta

1. `tests/sql/simular_cambios_origen.sql` en SSMS (cambia datos del origen).
2. `python -m etl.run_pipeline --modo incremental`: staging → DW → evaluación de alertas.
3. `python -m ml.entrenar`: reentrena y escribe el pronóstico.
4. En el dashboard: *Actualizar* / recargar y ver los cambios; la fecha de "Última carga" cambia.
5. Preguntar al asistente por el dato que cambió y comparar con el dashboard.

Este es el recorrido que se muestra en el video.

## Evidencias

Capturas, logs y salidas en `documentation/evidencias/`: carga y reconciliación, rechazos, API (Swagger), dashboard, monitoreo del ETL, pronóstico, bitácora y chat del asistente (`preguntas_asistente.md`), y alertas (consola y dashboard). Cada corrida del ETL, del modelo y de las alertas se identifica por su `execution_id` en `audit.etl_runs`.
