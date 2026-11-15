# Manuales: instalación, operación y usuario

## 1. Instalación

### Requisitos

| Qué | Versión probada | Nota |
|---|---|---|
| Windows | 10 / 11 | Los comandos son de PowerShell |
| SQL Server | 2022 Express (instancia `localhost\SQLEXPRESS`) | Autenticación de Windows |
| SSMS | cualquiera reciente | Para ejecutar los scripts |
| WideWorldImporters | `WideWorldImporters-Full.bak` | Restaurar en SQL Server (base `WideWorldImporters`) |
| Python | 3.11 o más nuevo (probado con 3.14) | |
| ODBC Driver | 17 o 18 para SQL Server | El nombre va en `SQL_DRIVER` |
| Node.js | **24.15 o más nuevo** (probado con 26) | Lo exige Angular 22 |
| Git | cualquiera | |
| Clave de Gemini | gratis en https://aistudio.google.com | Solo para el asistente |

### Pasos

1. **Clonar:** `git clone https://github.com/Luiseduardolopez12/Examen1TecnologiasEmergentes.git` y entrar a la carpeta.
2. **Entorno de Python:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   Si PowerShell no deja activar el entorno: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
3. **Configuración:** copia `.env.example` a `.env` y completa:

   | Variable | Qué poner |
   |---|---|
   | `SQL_SERVER` | `localhost\SQLEXPRESS` (tu instancia) |
   | `SQL_DRIVER` | `ODBC Driver 17 for SQL Server` (o 18) |
   | `SQL_USER` / `SQL_PASSWORD` | Vacíos para usar autenticación de Windows |
   | `SOURCE_DB`, `DW_DB` | `WideWorldImporters` y `DW_Ventas` |
   | `OVERLAP_HOURS` | `24` |
   | `API_USER`, `API_PASSWORD` | El usuario y la clave del dashboard (inventa una clave tuya) |
   | `API_SECRET` | Un texto largo y raro (firma los tokens) |
   | `GEMINI_API_KEY` | Tu clave de AI Studio |
   | `GEMINI_MODEL`, `GEMINI_MODEL_RESPALDO` | Modelos disponibles para tu clave (probar con `python ia/probar_clave.py <modelo>`) |
   | `ALERTA_UMBRAL_PCT` | `15` |

   `.env` está en `.gitignore`: nunca se sube al repositorio.
4. **Base de datos:** en SSMS ejecuta en orden los scripts de `database/`: `01` a `05` (base, auditoría, staging, DW y procedimientos de carga), luego `07_ml.sql`, `08_asistente.sql` y `09_alertas.sql`. El `06_reconciliacion.sql` es de consulta, no de creación.
5. **Primera carga:** `python -m etl.run_pipeline --modo full`. Al final evalúa las alertas.
6. **Pronóstico:** `python -m ml.entrenar`.
7. **Pruebas:** `python -m pytest` (deben pasar las 64).
8. **API:** `uvicorn api.main:app --reload --port 8000` (dejar abierta). Swagger en http://localhost:8000/docs.
9. **Dashboard** (otra terminal):
   ```powershell
   cd dashboard
   npm install
   npx ng serve --port 4200
   ```
   Abrir http://localhost:4200 e iniciar sesión con `API_USER` y `API_PASSWORD`.

### Reiniciar desde cero

Borra la base `DW_Ventas` en SSMS y repite desde el paso 4. La fuente no se modifica (salvo que hayas corrido `simular_cambios_origen.sql`).

## 2. Operación

### Rutina de actualización

| Cuándo | Comando | Qué hace |
|---|---|---|
| Cada vez que haya datos nuevos | `python -m etl.run_pipeline --modo incremental` | Carga lo nuevo, actualiza el DW y evalúa alertas |
| Cuando se complete un mes | `python -m ml.entrenar` | Reentrena y guarda el nuevo pronóstico |
| Cuando se quiera revisar alertas | `python -m alertas.evaluar` (`--mes AAAA-MM`, `--historico`) | Evalúa y registra sin duplicar |

Se puede programar el incremental con el **Programador de tareas de Windows** (acción: ejecutar `.venv\Scripts\python.exe` con argumentos `-m etl.run_pipeline --modo incremental`, carpeta de inicio la del proyecto).

### Monitoreo

- Pestaña **Monitoreo ETL** del dashboard: todas las corridas (ETL, modelo, alertas) con estado, conteos y error.
- En SSMS: `audit.etl_runs`, `audit.rejected_rows` (filas rechazadas), `audit.alertas`, `audit.asistente_consultas` y `audit.ml_metricas`.
- `database/06_reconciliacion.sql` compara origen, staging y DW.

### Respaldo y recuperación

- Respaldo: `BACKUP DATABASE DW_Ventas TO DISK = 'C:\respaldos\DW_Ventas.bak';` (SSMS o T-SQL).
- Si una carga falla, queda como `FAILED` con el error y el watermark no avanza: se corrige la causa y se vuelve a correr el mismo comando; el `MERGE` evita duplicados.
- El DW se puede reconstruir completo desde la fuente con `--modo full`.

### Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `uvicorn` o `httpx` no se reconoce / `ModuleNotFoundError` | La terminal no tiene el entorno activo. Ejecuta `.venv\Scripts\activate` (debe aparecer `(.venv)`) |
| `ng` falla por la versión de Node | Angular 22 pide Node 24.15 o más nuevo. Actualiza Node |
| Error de ODBC / "Data source name not found" | El nombre en `SQL_DRIVER` no coincide con el instalado. Revisa los drivers en el Administrador de orígenes de datos ODBC |
| 401 "Token inválido" | El token venció o se pegó mal; vuelve a iniciar sesión. Tras cambiar `API_SECRET` hay que iniciar sesión de nuevo |
| Dashboard con "Cargando…" o vacío | La API no está encendida. Revisa la terminal de `uvicorn` |
| Asistente: "no está disponible" (503) | Gemini saturado o clave/modelo inválidos. Prueba `python ia/probar_clave.py <modelo>` y cambia `GEMINI_MODEL` |
| Error 404 con el modelo de Gemini | El modelo ya no está disponible para tu cuenta; elige otro de la lista que imprime el script |
| `python -m pytest`: "import file mismatch" | Hay una carpeta duplicada con los mismos archivos de prueba. Deja una sola copia del proyecto |

## 3. Manual de usuario

1. **Entrar:** usuario y clave definidos en `.env`. *Salir* cierra la sesión.
2. **Encabezado:** "Datos hasta" indica la última fecha con ventas; "Última carga" cuándo corrió el ETL.
3. **Resumen:**
   - Filtros por fecha, grupo de producto y territorio; afectan a todas las tarjetas y gráficos.
   - Tarjetas: ventas netas (sin impuesto), ganancia, margen, facturas, ticket promedio y clientes.
   - Gráfico mensual de ventas y ganancia.
   - **Predicción de ventas:** panel marcado *PREDICCIÓN · no es dato histórico*. La línea discontinua es lo predicho, la banda es el rango probable del 80 %, y la tabla compara los modelos contra el baseline. Úsala como referencia, no como cifra exacta.
   - Gráficos por producto, grupo, territorio y vendedor, top de clientes y tabla de detalle paginada.
4. **Asistente:** escribe una pregunta o toca un ejemplo. Debajo de cada respuesta se ve la consulta y los filtros usados ("Datos del DW"). "Sin dato" significa que no puede responder con lo que hay en el Data Warehouse. *Limpiar* borra la conversación.
5. **Alertas:** el número rojo del menú y el aviso superior indican alertas nuevas. En la pestaña se ven periodo, regla, severidad, variación y montos; *Marcar revisada* la quita del contador.
6. **Monitoreo ETL:** estado de cada corrida del ETL, del modelo y de las alertas, con conteos y errores.
