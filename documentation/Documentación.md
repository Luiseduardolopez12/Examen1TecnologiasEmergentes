# Alcance y decisiones de diseño

Este documento explica qué proceso elegí, qué preguntas quiero responder con los datos y por qué tomé cada decisión de diseño.

## Proceso elegido

Elegí las **ventas** de WideWorldImporters. Es el proceso con más historia (de 2013 a mayo de 2016), tiene varias dimensiones para analizar (fecha, cliente, producto y vendedor) y un volumen suficiente, unas 228 mil líneas de factura, para que el dashboard y el modelo de pronóstico tengan sentido.

## Preguntas analíticas

1. ¿Cómo han evolucionado las ventas netas y la ganancia mes a mes?
2. ¿Qué categorías de producto y qué productos concentran las ventas?
3. ¿Qué clientes y qué regiones (territorio de ventas) generan más ingresos?
4. ¿Qué vendedores tienen mejor desempeño?
5. ¿Cuánto venderemos en los próximos meses? (modelo predictivo)
6. ¿Qué meses o categorías caen de forma anormal frente al período anterior? (alertas)

## Grano

Una fila de `FactSales` es **una línea de factura** (`Sales.InvoiceLines`). Elegí el grano más fino porque desde ahí se puede sumar hacia arriba (por mes, cliente, producto o vendedor), pero no se puede bajar a un detalle que no guardé.

## Medidas

| Medida | Tipo | Definición |
|--------|------|-----------|
| Quantity | aditiva | unidades vendidas |
| NetSales | aditiva | `ExtendedPrice - TaxAmount` (venta sin impuesto) |
| ExtendedPrice | aditiva | total de la línea con impuesto |
| TaxAmount | aditiva | impuesto |
| LineProfit | aditiva | ganancia de la línea |
| UnitPrice | no aditiva | precio unitario; se promedia ponderado por cantidad y nunca se suma |

## Dimensiones

`DimDate`, `DimCustomer` (SCD tipo 2), `DimProduct` (tipo 1) y `DimSalesperson` (tipo 1). Todas tienen un miembro `-1 Desconocido` para no perder ventas que no encuentren su dimensión.

## Decisiones

| Decisión | Lo que elegí | Por qué |
|----------|--------------|---------|
| Extracción | Por lotes (batch), incremental por `LastEditedWhen` | La fuente no emite eventos, y las facturas casi no cambian salvo correcciones. |
| Esquema | Estrella | Es más simple de consultar y de explicar. No hay jerarquías que justifiquen un copo de nieve. |
| Staging | `raw` (solo agrega), `clean` (MERGE) y una vista lista para cargar | Guardo lo original tal como llegó y dejo trazabilidad de lo que se limpió. |
| Herramienta del ETL | Python y SQL Server | El proyecto es pequeño. Airflow agregaría complejidad sin dar un beneficio real. |
| SCD tipo 2 en clientes | Categoría, grupo de compra y ubicación | Me permite analizar las ventas con la categoría que el cliente tenía en ese momento. |
| Fecha de cambio del SCD | `ValidFrom` de la tabla temporal de la fuente | Es la fecha real en que cambió el dato, no la fecha en que corrí el ETL. |
| Nulos en Brand, Size y BuyingGroup | `Sin marca`, `N/A` y `No aplica` | En estos campos un nulo significa "no aplica", no cero ni error. |
| Huérfanos en hechos | Miembro `-1 Desconocido` | No pierdo la venta, y queda visible en la reconciliación. |
| Líneas sin factura | Cuarentena (`audit.rejected_rows`) | No se puede resolver su fecha ni su cliente, así que no tiene sentido cargarlas. |
| Idempotencia | MERGE con comparación `EXCEPT` y `UNIQUE(InvoiceLineID)` | Volver a ejecutar la carga no duplica filas ni cuenta cambios que no existen. |
| Watermark | Se guarda solo cuando la carga termina bien, con 24 horas de solapamiento | Si una corrida falla no se pierde nada, y los registros que llegan tarde se recogen en la siguiente. |
| "Tiempo real" | No. Se actualiza cuando corre el ETL | Es un proceso por lotes. Lo digo claramente para no venderlo como tiempo real. |

## Limitaciones conocidas

- Las eliminaciones en la fuente no se propagan al Data Warehouse. WideWorldImporters no borra facturas, así que no afecta estos datos, pero lo dejo documentado.
- Los datos llegan hasta mayo de 2016. Por eso "último trimestre" en el dashboard y en el asistente se calcula respecto a la última fecha con datos, no respecto a hoy.
- Las alertas se entregan en el dashboard, no por correo.
