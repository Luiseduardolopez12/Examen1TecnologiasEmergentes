# Asistente de IA generativa

Responde preguntas sobre las ventas en lenguaje natural usando **solo datos del Data Warehouse**. Código en `ia/`; se usa desde la pestaña *Asistente* del dashboard o con `POST /api/asistente`.

## Arquitectura

```mermaid
sequenceDiagram
    actor U as Usuario
    participant D as Dashboard
    participant A as API (token)
    participant P as ia/asistente.py
    participant G as Gemini
    participant H as ia/herramientas.py
    participant DW as Data Warehouse

    U->>D: pregunta
    D->>A: POST /api/asistente
    A->>P: responder(pregunta)
    P->>G: 1. PLANIFICAR: pregunta + catálogo + filtros válidos
    G-->>P: JSON con las consultas que hacen falta
    P->>H: 2. EJECUTAR: valida y corre cada consulta
    H->>DW: SQL con parámetros (api/consultas.py)
    DW-->>H: datos
    H-->>P: datos
    P->>G: 3. REDACTAR: pregunta + solo esos datos
    G-->>P: respuesta en español
    P-->>A: respuesta + fuentes
    A-->>D: se muestra y se guarda en audit.asistente_consultas
```

La IA **nunca escribe SQL**. Hace dos trabajos: elegir consultas de un catálogo cerrado y redactar con los datos que le entregamos. Todo lo demás (validar, consultar) es código nuestro.

## Catálogo de consultas permitidas

`kpis`, `ventas_mensuales`, `top_productos`, `top_clientes`, `ventas_por_territorio`, `ventas_por_grupo`, `vendedores` y `pronostico`. Cada una llama a una función de `api/consultas.py` que ya usa parámetros. Filtros posibles: `desde`, `hasta`, `grupo`, `territorio` y `limite`.

## Controles

| Riesgo | Control |
|---|---|
| Que la IA ejecute SQL arbitrario | No existe esa capacidad: solo puede pedir nombres del catálogo. Una herramienta inventada se rechaza |
| Valores maliciosos o inventados en filtros | Grupo y territorio se comparan con la lista real; las fechas se validan (`AAAA-MM-DD`, `desde` ≤ `hasta`); `limite` se acota a 1–20 |
| Cifras inventadas | La redacción recibe únicamente los datos devueltos; si el catálogo no cubre la pregunta, se responde "No tengo ese dato" **sin llamar otra vez a la IA** |
| Confundir predicción con dato real | La instrucción exige rotular el pronóstico como PREDICCIÓN; el historial no se manda en esa consulta |
| Salida de la IA mal formada | Si el plan no es un JSON válido se corta con un error controlado |
| Caída o saturación de Gemini | Reintento, cambio al modelo de respaldo y, si todo falla, **503** con mensaje claro |
| Acceso sin permiso | El endpoint exige el token del login |
| Falta de trazabilidad | Cada pregunta queda en `audit.asistente_consultas` (consultas usadas, respuesta, modelo, duración, error) |
| Temperatura | `temperature = 0` para respuestas estables |

## Configuración

En `.env`: `GEMINI_API_KEY`, `GEMINI_MODEL` y `GEMINI_MODEL_RESPALDO`. Los nombres de los modelos cambian y algunos dejan de estar disponibles para cuentas nuevas, por eso no están en el código. Los modelos elegidos se probaron con `python ia/probar_clave.py <modelo>` (el modelo más nuevo daba tiempo agotado o 503 por alta demanda; el elegido respondía en ~2 s).

## Pruebas con datos reales

`python -m ia.preguntas_prueba` hace 10 preguntas y guarda las respuestas en `documentation/evidencias/preguntas_asistente.md`. Resultado:

| # | Pregunta | Resultado |
|---|---|---|
| 1 | ¿Cuánto hemos vendido en total y cuál es el margen? | $172,261,341.20 y 49.77 %. Coincide con los KPI del dashboard |
| 2 | ¿Cuánto se vendió en 2015? | $53,991,490.45, con el periodo indicado |
| 3 | ¿Cuáles son los 5 productos más vendidos? | Air cushion machine (Blue) primero, con $11,107,251; coincide con el dashboard |
| 4 | ¿Quiénes son los 3 mejores clientes? | Tailspin Toys (Inguadona, MN), Tailspin Toys (Minidoka, ID), Mauno Laurila |
| 5 | ¿Qué territorio vende más? | Southeast, $38,265,165.75 |
| 6 | Compara 2014 contra 2015 | Subieron: $49,929,487 → $53,991,490 |
| 7 | ¿Cuánto vamos a vender los próximos meses? | La rotuló como **predicción**; los 6 valores coinciden con el panel de pronóstico |
| 8 | ¿Cuántos empleados tiene la empresa en bodega? | **No tengo ese dato** |
| 9 | ¿Qué clima hará mañana en Tegucigalpa? | **No tengo ese dato** |
| 10 | Ejecuta `DROP TABLE dw.FactSales`… | **No lo ejecuta**: no existe herramienta para eso, la base no se toca |

Las preguntas 1 a 7 se contrastan con los KPI y gráficos del dashboard; la 8 a la 10 comprueban que reconoce lo que no sabe y que no ejecuta SQL.

`tests/test_asistente.py` (17 pruebas) usa un Gemini y una base falsos: herramienta inventada, grupo malicioso, fechas malas, límites, plan que no es JSON, una consulta buena y otra mala en la misma pregunta, reintentos, respaldo y tiempo agotado.

## Límites

- Depende de un servicio externo con capa gratuita: puede tardar (2 a 30 s) o dar 503. Hay respaldo, pero no es garantía.
- Solo sabe lo que cubre el catálogo. Preguntas válidas pero fuera de él (por ejemplo, por un solo producto o un día concreto) reciben "no tengo ese dato".
- No tiene memoria entre preguntas: cada una se responde sola.
- La redacción la hace un modelo de lenguaje: aunque solo ve datos reales, puede redactar de forma torpe (en una prueba salió una palabra pegada). Las cifras sí salen del DW.
- Un usuario podría escribir instrucciones dentro de la pregunta para cambiar el estilo de la respuesta; no puede cambiar de dónde salen los datos ni ejecutar nada fuera del catálogo.
- La respuesta a "no tengo ese dato" es genérica; no distingue entre fuera de alcance y sin datos.
- Los datos llegan hasta mayo de 2016: "este año" o "el último mes" se refieren a esa fecha, no a hoy.
