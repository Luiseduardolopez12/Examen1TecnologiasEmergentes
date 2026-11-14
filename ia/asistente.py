"""Asistente de IA sobre el Data Warehouse.

Flujo en tres pasos, para que la IA nunca invente cifras ni toque la base directamente:
  1. PLANIFICAR: Gemini elige, de un catálogo fijo, qué consultas hacen falta (en JSON).
  2. EJECUTAR:   nuestro código valida esa elección y corre las consultas parametrizadas.
  3. REDACTAR:   Gemini explica la respuesta usando SOLO los datos devueltos.
Si ninguna consulta del catálogo sirve, se responde "no tengo ese dato" sin llamar a la IA.
"""
import json
import re
import time

from api import consultas
from ia import herramientas
from ia.gemini import ErrorIA, generar

SIN_DATO = ("No tengo ese dato en el Data Warehouse. Puedo ayudarte con ventas netas, ganancia, "
            "margen, facturas y clientes; top de productos y clientes; ventas por territorio, grupo "
            "de producto y vendedor; tendencia mensual; y la predicción de los próximos meses.")

SISTEMA_PLAN = """Eres el planificador de un asistente de analítica de ventas (WideWorldImporters).
Tu único trabajo es elegir qué consultas del catálogo hacen falta para responder la pregunta.
Respondes SOLO con JSON, sin texto extra, con esta forma exacta:
{{"consultas": [{{"herramienta": "nombre", "parametros": {{"desde": "AAAA-MM-DD", "hasta": "AAAA-MM-DD", "grupo": "...", "territorio": "...", "limite": 5}}}}]}}
Reglas:
- Usa solo herramientas del catálogo. Todos los parámetros son opcionales; omite los que no apliquen.
- Máximo 3 consultas. Para comparar dos periodos usa dos consultas con distintas fechas.
- Si la pregunta NO se puede responder con el catálogo (otro tema, datos que no existen como
  inventario, empleados, costos de envío, o saludos), responde {{"consultas": []}}.
- Los datos van de {inicio} a {fin}. Si dicen "el último mes" o "este año", refiérete al final de ese rango.
- "grupo" solo puede ser uno de: {grupos}
- "territorio" solo puede ser uno de: {territorios}

Catálogo:
{catalogo}"""

SISTEMA_RESPUESTA = """Eres el asistente de analítica de ventas de WideWorldImporters.
Responde en español, claro y breve (máximo 5 líneas), usando EXCLUSIVAMENTE los datos que se te entregan.
- No inventes cifras ni uses conocimiento externo. Si los datos no alcanzan, dilo y di qué falta.
- Indica siempre el periodo y los filtros a los que corresponde la cifra.
- Montos en dólares con separador de miles. Los datos llegan sin impuestos (ventas netas).
- Si usas el pronóstico, aclara que es una PREDICCIÓN, no un dato real.
- Si en los datos hay un campo 'errores', explica al usuario qué no se pudo consultar."""


def _leer_plan(texto):
    texto = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.MULTILINE).strip()
    try:
        plan = json.loads(texto)
        lista = plan["consultas"]
    except (ValueError, KeyError, TypeError):
        raise ErrorIA("El planificador no devolvió un JSON válido")
    if not isinstance(lista, list):
        raise ErrorIA("El planificador no devolvió una lista de consultas")
    return [c for c in lista if isinstance(c, dict)][:3]


def responder(pregunta):
    """Devuelve dict con respuesta, respondida, fuentes, modelo y duracion_ms. Puede lanzar ErrorIA."""
    inicio = time.time()
    opciones = consultas.opciones_filtros()
    sistema = SISTEMA_PLAN.format(
        inicio=opciones["rango"]["desde"], fin=opciones["rango"]["hasta"],
        grupos=opciones["grupos"], territorios=opciones["territorios"],
        catalogo=herramientas.describir_catalogo())

    texto_plan, modelo = generar(pregunta, sistema, como_json=True)
    plan = _leer_plan(texto_plan)

    datos, fuentes, errores = [], [], []
    for c in plan:
        nombre, params = str(c.get("herramienta", "")), c.get("parametros") or {}
        try:
            resultado, usados = herramientas.ejecutar(nombre, params if isinstance(params, dict) else {})
        except ValueError as e:
            errores.append(str(e))
            continue
        if isinstance(resultado, dict):
            resultado.pop("historial", None)       # el historial ya lo cubre ventas_mensuales
        datos.append({"herramienta": nombre, "filtros": usados, "resultado": resultado})
        fuentes.append({"herramienta": nombre, "filtros": usados})

    if not datos:
        mensaje = ("No pude hacer esa consulta: " + " ".join(errores)) if errores else SIN_DATO
        return {"respuesta": mensaje, "respondida": False, "fuentes": [], "modelo": modelo,
                "duracion_ms": int((time.time() - inicio) * 1000)}

    paquete = {"datos": datos}
    if errores:
        paquete["errores"] = errores
    prompt = f"Pregunta: {pregunta}\n\nDatos:\n{json.dumps(paquete, ensure_ascii=False, default=str)}"
    texto, modelo = generar(prompt, SISTEMA_RESPUESTA)
    return {"respuesta": texto, "respondida": True, "fuentes": fuentes, "modelo": modelo,
            "duracion_ms": int((time.time() - inicio) * 1000)}
