# Modelo de predicción de ventas

## Problema
- **Qué se predice:** ventas netas mensuales (`NetSales` = total de la línea menos impuesto) de los próximos 6 meses.
- **Quién lo usa:** gerencia comercial y compras.
- **Decisión que apoya:** cuánto inventario comprar y qué meta de ventas fijar.
- **Tipo:** series de tiempo / regresión. Métricas: MAE, RMSE y MAPE.

## Datos
- Origen: `dw.FactSales` agrupada por mes con `dw.DimDate` (dato del Data Warehouse, no de la base operativa).
- Serie: 41 meses (2013-01 a 2016-05). Promedio mensual $4,201,496; mínimo $2,776,786 (2013-02); máximo $5,155,672 (2015-07). La variación (desviación / promedio) es de 11.1 %: una serie bastante estable.
- Estacionalidad: el mes más fuerte es julio y el más flojo febrero, con 32 % de diferencia entre sus promedios.
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
Corrida `v202611140124` (`execution_id` 20). Entrenamiento: 35 meses; prueba: 6 meses; 12 pliegues de validación.

| Modelo | MAE validación | MAE prueba | MAPE prueba | |
|---|---:|---:|---:|---|
| Repetir el último mes | 375,239 | 453,987 | 9.8 % | baseline |
| Promedio de 3 meses | 322,762 | 237,046 | 5.2 % | |
| Mismo mes del año pasado | 471,501 | 241,093 | 5.2 % | |
| **Tendencia lineal** | **252,800** | **260,197** | **6.0 %** | **elegido** |
| Tendencia + estacionalidad | 298,044 | 236,048 | 5.2 % | |

**Conclusión.** El modelo elegido, tendencia lineal, tuvo el menor error en la validación y en la prueba tiene **43 % menos error (MAE) que el baseline**: $260,197 contra $453,987, o 6.0 % contra 9.8 % de MAPE.

Una observación honesta: en la prueba otros tres modelos salieron un poco mejor que el elegido (MAPE de 5.2 % contra 6.0 %). No se cambió de modelo por eso, porque elegir mirando la prueba la convertiría en validación y ya no mediría nada independiente. Además, con solo 6 meses de prueba, las diferencias entre los candidatos (de $236 mil a $260 mil de MAE) caben dentro del ruido; lo que sí es claro es que todos le ganan al baseline.

Pronóstico generado (rango del 80 %):

| Mes | Pronóstico | Rango |
|---|---:|---|
| 2016-06 | $4,708,901 | $4,266,653 a $5,151,149 |
| 2016-07 | $4,733,063 | $4,290,815 a $5,175,311 |
| 2016-08 | $4,757,225 | $4,314,977 a $5,199,473 |
| 2016-09 | $4,781,387 | $4,339,139 a $5,223,635 |
| 2016-10 | $4,805,550 | $4,363,302 a $5,247,798 |
| 2016-11 | $4,829,712 | $4,387,464 a $5,271,960 |

La tendencia lineal sube unos $24 mil por mes y no reproduce el patrón estacional (por ejemplo, la caída típica de febrero). Es el costo de tener pocos meses: el modelo con estacionalidad estimaba cada mes con unos 3 puntos y salió peor en la validación.

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
