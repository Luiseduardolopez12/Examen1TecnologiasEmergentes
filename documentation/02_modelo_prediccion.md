# Modelo de predicción de ventas

> Borrador base. Complétalo con los números de TU corrida (`python -m ml.entrenar`) y reescríbelo con tus palabras.

## Problema
- **Qué se predice:** ventas netas mensuales (`NetSales` = total de la línea menos impuesto) de los próximos 6 meses.
- **Quién lo usa:** gerencia comercial y compras.
- **Decisión que apoya:** cuánto inventario comprar y qué meta de ventas fijar.
- **Tipo:** series de tiempo / regresión. Métricas: MAE, RMSE y MAPE.

## Datos
- Origen: `dw.FactSales` agrupada por mes con `dw.DimDate` (dato del Data Warehouse, no de la base operativa).
- Serie: 41 meses (2013-01 a 2016-05). _Completa: promedio, mínimo, máximo y variación que imprime el script._
- Se descarta el último mes si está incompleto, y si falta un mes en medio el script se detiene: no se inventan datos.
- Pocos datos: 3 años. Por eso se pronostican 6 meses y no más, y el script se niega a entrenar si hay menos de 30 meses.

## Separación en el tiempo (sin data leakage)
1. **Prueba:** los últimos 6 meses. No se usan para decidir nada hasta el final.
2. **Validación hacia adelante** con los meses restantes: se entrena con los primeros _n_ meses y se predicen los 6 siguientes, moviendo _n_ de a un mes (12 pliegues). Nunca se entrena con meses posteriores a los que se predicen.
3. Se elige el modelo con menor MAE en validación; recién entonces se mide en la prueba, una sola vez.
4. El ganador se reentrena con todos los datos para predecir los próximos 6 meses.
No hay variables que usen información del futuro: las únicas entradas son el número de mes y el mes del año.

## Modelos comparados
| Modelo | Qué hace | Rol |
|---|---|---|
| Repetir el último mes | el próximo mes vale lo del último | **baseline** |
| Promedio de 3 meses | promedio reciente | candidato simple |
| Mismo mes del año pasado | repite la estacionalidad | candidato simple |
| Tendencia lineal | regresión lineal sobre el tiempo | candidato |
| Tendencia + estacionalidad | regresión Ridge con tendencia y efecto por mes (alpha fijo 0.1) | candidato |

El `alpha` no se ajustó con los datos (hay muy pocos): se fijó razonando que cada mes aparece unas 3 veces y que Ridge encoge su efecto por n / (n + alpha).

## Resultados
_Pega aquí la tabla que imprime `python -m ml.entrenar` (MAE de validación, MAE de prueba, MAPE de prueba) y el modelo elegido._

_Escribe una conclusión honesta: ¿el modelo elegido le gana al baseline en la prueba? ¿por cuánto? Si el baseline gana o empata, dilo: es un resultado válido._

## Intervalo del pronóstico
Rango del 80 %: pronóstico ± 1.28 × RMSE de validación del modelo elegido. Es una aproximación (supone errores parecidos a una normal e independientes entre meses).

## Limitaciones
- Solo 41 meses: 3 ciclos anuales completos. La estacionalidad se estima con unos 3 puntos por mes.
- La serie es de una base de ejemplo (WideWorldImporters); su comportamiento puede ser más regular que el de un negocio real.
- No hay variables externas (promociones, precios, feriados).
- El modelo no sabe de eventos únicos; si cambia el negocio, hay que reentrenar.
- El error en pliegues y prueba se mide con muy pocos puntos, por lo que es una estimación con incertidumbre.

## Versionado y reentrenamiento
- Cada entrenamiento guarda `ml/artefactos/modelo_<versión>.joblib` y `.json` (parámetros, fechas, métricas), y escribe en `dw.PronosticoVentas` y `audit.ml_metricas` con la versión y el `execution_id` de `audit.etl_runs`.
- Reentrenar cada vez que se carguen datos nuevos de un mes completo: `python -m ml.entrenar`.
- Monitoreo: comparar cada mes lo predicho contra lo real y reentrenar si el error se dispara.
