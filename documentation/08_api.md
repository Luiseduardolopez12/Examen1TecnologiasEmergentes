# API y contratos de datos

API de solo lectura hecha con FastAPI (`api/`). El navegador nunca habla con SQL Server: el dashboard llama a esta API y la API consulta el Data Warehouse.

```
uvicorn api.main:app --reload --port 8000
```

Documentación interactiva (Swagger): http://localhost:8000/docs. Ahí se usa el botón **Authorize** con el token del login.

## Seguridad

- `POST /auth/login` recibe usuario y clave (definidos en `.env`) y devuelve un token firmado con HMAC que vence. Todo lo demás exige `Authorization: Bearer <token>`.
- Sin token, token alterado o vencido: **401**.
- Cada filtro viaja como **parámetro SQL** (`:desde`, `:grupo`...), nunca pegado al texto de la consulta. Hay una prueba que intenta inyectar `x'; DROP TABLE dw.FactSales;--` y comprueba que no aparece en el SQL.
- CORS limitado a `http://localhost:4200`.
- La API solo lee. Escribe en dos lugares acotados: la bitácora del asistente y el estado de una alerta.

## Filtros comunes

Los endpoints de ventas aceptan, todos opcionales:

| Parámetro | Tipo | Ejemplo | Efecto |
|---|---|---|---|
| `desde` | fecha | `2015-01-01` | Ventas desde esa fecha |
| `hasta` | fecha | `2015-12-31` | Ventas hasta esa fecha |
| `grupo` | texto | `Novelty Items` | Grupo de producto |
| `territorio` | texto | `Southeast` | Territorio de ventas del cliente |

Si `desde` es posterior a `hasta`: **400**. Límites fuera de rango (`limite`, `tamano`): **422**.

## Endpoints

| Método y ruta | Devuelve | Notas |
|---|---|---|
| `POST /auth/login` | `{ "token": "..." }` | Sin token |
| `GET /salud` | `{ "estado": "ok" }` | Sin token |
| `GET /api/filtros` | `{ grupos[], territorios[], rango{desde,hasta} }` | Alimenta los filtros |
| `GET /api/ultima-actualizacion` | `{ ultima_carga, rows_inserted, rows_updated, datos_hasta }` | Encabezado del dashboard |
| `GET /api/kpis` | `{ ventas_netas, ganancia, unidades, facturas, clientes, margen_pct, ticket_promedio }` | Ratios calculados sobre totales |
| `GET /api/ventas-mensuales` | `[ { mes, ventas_netas, ganancia } ]` | Orden cronológico |
| `GET /api/top-productos?limite=10` | `[ { producto, grupo, ventas_netas, unidades } ]` | `limite` 1 a 50 |
| `GET /api/top-clientes?limite=10` | `[ { cliente, ventas_netas, facturas } ]` | `limite` 1 a 50 |
| `GET /api/ventas-por-territorio` | `[ { territorio, ventas_netas } ]` | |
| `GET /api/ventas-por-grupo` | `[ { grupo, ventas_netas } ]` | |
| `GET /api/vendedores` | `[ { vendedor, ventas_netas, ganancia } ]` | |
| `GET /api/detalle?pagina=1&tamano=20` | `{ pagina, tamano, total, filas[] }` | `tamano` 1 a 100; lo más reciente primero |
| `GET /api/pronostico` | `{ disponible, modelo, version, base_hasta, generado_en, pronostico[], metricas[], historial[] }` | `{ "disponible": false }` si no se ha entrenado |
| `GET /api/alertas?estado=NUEVA` | `[ { alerta_id, regla, periodo, variacion_pct, severidad, estado, ... } ]` | `estado`: `NUEVA` o `REVISADA` |
| `POST /api/alertas/{id}/revisar` | `{ alerta_id, estado: "REVISADA" }` | **404** si no existe |
| `POST /api/asistente` | `{ respuesta, respondida, fuentes[], modelo, duracion_ms }` | Pregunta de 3 a 500 caracteres; **503** si la IA no responde |
| `GET /api/etl/ejecuciones?limite=30` | `[ { execution_id, pipeline_name, status, rows_*, start_time, end_time, error_detail } ]` | Monitoreo del ETL |

## Contratos que conviene tener claros

- **Venta neta** (`ventas_netas`): `ExtendedPrice − TaxAmount`, o sea sin impuesto. Todos los endpoints usan la misma definición.
- **Margen** = ganancia / ventas netas, y **ticket promedio** = ventas netas / facturas. Se calculan sobre los totales, nunca promediando promedios.
- **Pronóstico:** `pronostico[]` trae `{ mes, horizonte_mes, valor, inferior, superior }`; es una predicción, el dashboard la rotula así. `historial[]` sí es dato real del DW.
- **Fechas** en formato ISO (`AAAA-MM-DD`); `mes` en `AAAA-MM`.

## Pruebas

`tests/test_api.py` usa una base falsa (no necesita SQL Server) y comprueba: login correcto e incorrecto, rutas sin token, token alterado, token pegado con comillas, ratios de los KPI, filtros como parámetros, rango de fechas inválido, paginación y límites, y los casos del pronóstico.
