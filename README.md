# Plataforma de Ingeniería de Datos y Analítica Inteligente

Proyecto de Tecnologías Emergentes. Toma las ventas de **WideWorldImporters** (SQL Server),
las limpia en un área de staging, las carga en un Data Warehouse dimensional y encima de eso
construye un dashboard, un modelo de predicción, un asistente con IA y alertas.

## Flujo

```
WideWorldImporters -> ETL (Python) -> stg.raw -> stg.clean -> DW_Ventas (estrella)
                                                                 |-> API (FastAPI) -> Dashboard (Angular)
                                                                 |-> Modelo de pronóstico (scikit-learn)
                                                                 |-> Asistente de IA (Gemini)
                                                                 '-> Alertas
```

Todo vive en la base `DW_Ventas` con tres esquemas: `stg` (staging), `dw` (modelo dimensional)
y `audit` (ejecuciones, watermarks y filas rechazadas).

## Estado

| Fase | Estado |
|------|--------|
| 1-2 Descubrimiento y diseño | listo |
| 3 ETL y calidad | listo |
| 4 Data Warehouse | listo |
| 5 API y dashboard | listo |
| 6 Pronóstico y asistente de IA | listo |
| 7 Alertas y monitoreo | listo |
| 8 Integración, documentación y video | documentación lista; falta el video |

## Documentación

Todo está en `documentation/`:

| Documento | Contenido |
|-----------|-----------|
| [01 Alcance y decisiones](documentation/01_alcance_y_decisiones.md) | Proceso, preguntas, grano, medidas y decisiones |
| [02 Modelo de predicción](documentation/02_modelo_prediccion.md) | Problema, experimentos, métricas y límites |
| [03 Requerimientos](documentation/03_requerimientos.md) | Funcionales y no funcionales |
| [04 Arquitectura](documentation/04_arquitectura.md) | Diagrama general, componentes y seguridad |
| [05 Fuente y ERD](documentation/05_fuente_erd_y_diccionario.md) | ERD de WideWorldImporters y diccionario |
| [06 Modelo dimensional](documentation/06_modelo_dimensional.md) | Estrella, grano y diccionario del DW |
| [07 ETL y calidad](documentation/07_etl_y_calidad.md) | Diagramas, reglas de calidad y resultados de carga |
| [08 API](documentation/08_api.md) | Endpoints y contratos de datos |
| [09 Asistente de IA](documentation/09_asistente_ia.md) | Arquitectura, controles y pruebas |
| [10 Alertas](documentation/10_alertas.md) | Reglas, registro, entrega y pruebas |
| [11 Pruebas](documentation/11_pruebas.md) | Plan y resultados |
| [12 Manuales](documentation/12_manuales.md) | Instalación, operación y usuario |

Las capturas y salidas de prueba están en `documentation/evidencias/`.

## Requisitos

- SQL Server (Express o Developer) + SSMS
- Base `WideWorldImporters` restaurada
- Python 3.11+
- ODBC Driver 17 o 18 for SQL Server
- Node.js 24.15 o más nuevo (para el dashboard de Angular)
- Una clave gratis de Gemini (solo para el asistente): https://aistudio.google.com
- Git / GitHub Desktop

## Cómo ejecutarlo

Resumen; los pasos completos y la solución de problemas están en [12 Manuales](documentation/12_manuales.md).

1. Clona el repo y crea el entorno de Python:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copia `.env.example` a `.env` y complétalo (instancia de SQL Server, usuario y clave de la API, clave de Gemini).
3. En SSMS, ejecuta en orden los scripts de `database/`: 01 al 05, y luego 07, 08 y 09 (el 06 es de consulta).
4. Primera carga completa (también evalúa las alertas):
   ```
   python -m etl.run_pipeline --modo full
   ```
5. Valida con `database/06_reconciliacion.sql`.
6. Entrena el pronóstico:
   ```
   python -m ml.entrenar
   ```
7. Pruebas automáticas (64):
   ```
   python -m pytest
   ```
8. API (déjala abierta):
   ```
   uvicorn api.main:app --reload --port 8000
   ```
9. Dashboard, en otra terminal:
   ```
   cd dashboard
   npm install
   npx ng serve --port 4200
   ```
   Abre http://localhost:4200 e inicia sesión con el usuario y la clave de tu `.env`.

## Carga incremental

```
python -m etl.run_pipeline --modo incremental
```

Usa un watermark por tabla (`audit.watermarks`) con 24 horas de solapamiento. Para probarla,
corre `tests/sql/simular_cambios_origen.sql` (modifica WideWorldImporters) y vuelve a ejecutar.

## Alertas y asistente

```
python -m alertas.evaluar                 # último mes completo
python -m alertas.evaluar --mes 2013-02   # un mes concreto
python -m ia.preguntas_prueba             # las 10 preguntas de prueba del asistente
```

## Perfilado de datos

```
python -m etl.profiling
```

## Estructura

```
database/        scripts SQL en orden de ejecución
etl/             extracción, transformación, carga y orquestación
api/             API de solo lectura (FastAPI)
dashboard/       interfaz (Angular)
ml/              modelo de pronóstico
ia/              asistente de IA
alertas/         reglas de alerta
tests/           pruebas automáticas y scripts de simulación
documentation/   documentos, diagramas y evidencias
```

## Reiniciar el ambiente

Borra la base `DW_Ventas` en SSMS y repite desde el paso 3. La fuente no se toca
(salvo que hayas corrido el script de simulación).
