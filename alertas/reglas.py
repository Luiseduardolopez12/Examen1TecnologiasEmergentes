"""Reglas de alerta sobre las ventas netas mensuales.

Son funciones puras (no tocan la base) para poder probarlas con números inventados.
Una alerta se dispara cuando la caída es MAYOR que el umbral (15 % exacto no dispara).
"""
import calendar
from datetime import date

UMBRAL_DEFECTO = 15.0
SEVERIDAD_ALTA = 30.0      # caídas de 30 % o más se marcan ALTA

REGLAS = {
    "caida_mensual": ("al mes anterior", 1),
    "caida_interanual": ("al mismo mes del año anterior", 12),
}


def desplazar_mes(mes, atras):
    """'2016-03' retrocedido 5 meses -> '2015-10'."""
    anio, m = int(mes[:4]), int(mes[5:7])
    total = anio * 12 + (m - 1) - atras
    return f"{total // 12}-{total % 12 + 1:02d}"


def variacion_pct(actual, referencia):
    """Cambio porcentual, o None si no hay con qué comparar."""
    if referencia is None or referencia <= 0:
        return None
    return (actual - referencia) / referencia * 100


def comprobar(serie, mes, umbral=UMBRAL_DEFECTO):
    """Evalúa todas las reglas para un mes. `serie` es {'AAAA-MM': ventas_netas}.

    Devuelve una comprobación por regla que se pudo evaluar (haya o no alerta);
    si falta el mes o su referencia, esa regla se omite en vez de inventar un dato."""
    resultado = []
    if mes not in serie:
        return resultado
    actual = serie[mes]
    for regla, (texto, atras) in REGLAS.items():
        ref_mes = desplazar_mes(mes, atras)
        referencia = serie.get(ref_mes)
        cambio = variacion_pct(actual, referencia)
        if cambio is None:
            continue
        caida = -cambio
        c = {"regla": regla, "periodo": mes, "ambito": "Global", "referencia_mes": ref_mes,
             "valor_actual": round(actual, 2), "valor_referencia": round(referencia, 2),
             "variacion_pct": round(cambio, 2), "umbral_pct": umbral, "dispara": caida > umbral}
        if c["dispara"]:
            c["severidad"] = "ALTA" if caida >= SEVERIDAD_ALTA else "MEDIA"
            c["mensaje"] = (f"Las ventas netas de {mes} (${actual:,.0f}) cayeron {caida:.1f} % frente "
                            f"{texto} ({ref_mes}: ${referencia:,.0f}). Umbral: {umbral:g} %.")
        resultado.append(c)
    return resultado


def ultimo_mes_completo(meses, datos_hasta):
    """El último mes de la serie, pero solo si los datos llegan a su último día.
    Evita alertar por un mes a medias que siempre se vería como caída."""
    if not meses:
        return None
    ultimo = sorted(meses)[-1]
    anio, m = int(ultimo[:4]), int(ultimo[5:7])
    if datos_hasta >= date(anio, m, calendar.monthrange(anio, m)[1]):
        return ultimo
    anterior = desplazar_mes(ultimo, 1)
    return anterior if anterior in meses else None