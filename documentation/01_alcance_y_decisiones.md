# Alcance y decisiones de diseño

## Proceso elegido

**Ventas** de WideWorldImporters. Es el proceso con más historia (2013 a mayo 2016), varias dimensiones y volumen suficiente (unas 228 mil líneas de factura) para que el dashboard y el modelo tengan sentido.

## Preguntas analíticas

1. ¿Cómo han evolucionado las ventas netas y la ganancia mes a mes?
2. ¿Qué categorías de producto y qué productos concentran las ventas?
3. ¿Qué clientes y qué regiones (territorio de ventas) generan más ingresos?
4. ¿Qué vendedores tienen mejor desempeño?
5. ¿Cuánto venderemos en los próximos meses? (modelo predictivo)
6. ¿Qué meses o categorías caen de forma anormal frente al período anterior? (alertas)

## Grano

Una fila de `FactSales` = **una línea de factura** (`Sales.InvoiceLines`).

## Medidas

| Medida | Tipo | Definición |
|--------|------|-----------|
| Quantity | aditiva | unidades vendidas |
| NetSales | aditiva | `ExtendedPrice - TaxAmount` (venta sin impuesto) |
| ExtendedPrice | aditiva | total de la línea con impuesto |
| TaxAmount | aditiva | impuesto |
| LineProfit | aditiva | ganancia de la línea |
| UnitPrice | no aditiva | precio unitario; se promedia ponderado por cantidad, nunca se suma |

## Dimensiones

`DimDate`, `DimCustomer` (SCD tipo 2), `DimProduct` (tipo 1), `DimSalesperson` (tipo 1). Todas con miembro `-1 Desconocido`.

## Decisiones

| Decisión | Elegido | Por qué |
|----------|---------|---------|
| Extracción | Batch, incremental por `LastEditedWhen` | La fuente no tiene eventos; las facturas son inmutables salvo correcciones. |
| Esquema | Estrella | Más simple de consultar y de explicar; no hay jerarquías que justifiquen copo de nieve. |
| Staging | raw (solo agrega) + clean (MERGE) + vista ready | Conserva lo original y deja trazabilidad. |
| Herramienta ETL | Python + SQL Server | El proyecto es pequeño; Airflow agregaría complejidad sin beneficio. |
| SCD tipo 2 en clientes | Categoría, grupo de compra y ubicación | Permite analizar ventas por la categoría que el cliente tenía en ese momento. |
| Fecha de cambio SCD | `ValidFrom` de la tabla temporal de la fuente | Es la fecha real en que cambió el dato. |
| Nulos en Brand/Size/BuyingGroup | `Sin marca`, `N/A`, `No aplica` | Un nulo aquí significa "no aplica", no cero ni error. |
| Huérfanos en hechos | Miembro `-1 Desconocido` | No se pierde la venta y queda visible en reconciliación. |
| Líneas sin factura | Cuarentena (`audit.rejected_rows`) | No se puede resolver la fecha ni el cliente. |
| Idempotencia | MERGE con comparación `EXCEPT` y `UNIQUE(InvoiceLineID)` | Reejecutar no duplica ni cuenta cambios falsos. |
| Watermark | Se guarda solo tras terminar bien; solapamiento de 24 h | Evita perder registros tardíos si una corrida falla. |
| "Tiempo real" | No. Se refresca cuando corre el ETL (por demanda en la demo) | Un batch no es tiempo real; las alertas simuladas se identificarán como tal. |

## Limitaciones conocidas

- Eliminaciones en la fuente no se propagan (WWI no borra facturas; se documenta como limitación).
- Los datos llegan hasta mayo de 2016: "último trimestre" en el dashboard y el asistente se calcula respecto a la última fecha con datos, no respecto a hoy.
