"""Las únicas consultas que el asistente puede pedir.

La IA NO escribe SQL: solo elige una de estas herramientas y sus filtros. Cada herramienta
llama a una función de api/consultas.py, que ya usa parámetros. Todo lo que pide la IA se
valida aquí antes de tocar la base.
"""
from datetime import date

from api import consultas

# nombre -> (descripción para el modelo, función, ¿acepta límite?)
CATALOGO = {
    "kpis": ("Totales del periodo: ventas netas, ganancia, margen %, unidades, facturas, clientes, ticket promedio.",
             consultas.kpis, False),
    "ventas_mensuales": ("Ventas netas y ganancia mes a mes (sirve para tendencias y comparar meses).",
                         consultas.ventas_mensuales, False),
    "top_productos": ("Productos con más ventas netas.", consultas.top_productos, True),
    "top_clientes": ("Clientes con más ventas netas.", consultas.top_clientes, True),
    "ventas_por_territorio": ("Ventas netas por territorio de ventas.", consultas.ventas_por_territorio, False),
    "ventas_por_grupo": ("Ventas netas por grupo de producto.", consultas.ventas_por_grupo, False),
    "vendedores": ("Ventas netas y ganancia por vendedor.", consultas.vendedores, False),
    "pronostico": ("Predicción de ventas netas de los próximos 6 meses, con métricas del modelo. "
                   "Es una PREDICCIÓN, no datos reales.", None, False),
}


def describir_catalogo():
    return "\n".join(f"- {n}: {d}" for n, (d, _, _) in CATALOGO.items())


def _fecha(valor, nombre):
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise ValueError(f"'{nombre}' debe tener formato AAAA-MM-DD, llegó: {valor!r}")


def ejecutar(herramienta, parametros):
    """Valida y ejecuta una herramienta. Devuelve (datos, parametros_usados).
    Si algo no es válido lanza ValueError con un mensaje claro."""
    if herramienta not in CATALOGO:
        raise ValueError(f"La herramienta '{herramienta}' no existe")
    parametros = parametros or {}
    _, funcion, usa_limite = CATALOGO[herramienta]

    if herramienta == "pronostico":
        return consultas.pronostico(), {}

    usados = {}
    for campo in ("desde", "hasta"):
        if parametros.get(campo):
            usados[campo] = _fecha(parametros[campo], campo)
    if usados.get("desde") and usados.get("hasta") and usados["desde"] > usados["hasta"]:
        raise ValueError("La fecha 'desde' no puede ser posterior a 'hasta'")

    opciones = consultas.opciones_filtros()
    if parametros.get("grupo"):
        if parametros["grupo"] not in opciones["grupos"]:
            raise ValueError(f"El grupo '{parametros['grupo']}' no existe. Grupos válidos: {', '.join(opciones['grupos'])}")
        usados["grupo"] = parametros["grupo"]
    if parametros.get("territorio"):
        if parametros["territorio"] not in opciones["territorios"]:
            raise ValueError(f"El territorio '{parametros['territorio']}' no existe. "
                             f"Territorios válidos: {', '.join(opciones['territorios'])}")
        usados["territorio"] = parametros["territorio"]

    if usa_limite:
        try:
            limite = int(parametros.get("limite", 5))
        except (TypeError, ValueError):
            raise ValueError("'limite' debe ser un número")
        datos = funcion(max(1, min(limite, 20)), **usados)
    else:
        datos = funcion(**usados)
    return datos, {k: str(v) for k, v in usados.items()}
