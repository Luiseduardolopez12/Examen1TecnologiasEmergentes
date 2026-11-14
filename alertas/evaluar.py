"""Evalúa las reglas de alerta y guarda las nuevas en audit.alertas.

    python -m alertas.evaluar                       # último mes completo del Data Warehouse
    python -m alertas.evaluar --mes 2013-02         # un mes concreto (para probar o revisar)
    python -m alertas.evaluar --historico           # todos los meses de la historia
    python -m alertas.evaluar --umbral 10           # cambia el umbral (por defecto 15 %)

Se puede correr las veces que quieras: una alerta (regla + periodo) nunca se duplica.
También corre sola al final de python -m etl.run_pipeline.
"""
import argparse
import os

import pandas as pd
from sqlalchemy import text

from alertas.reglas import UMBRAL_DEFECTO, comprobar, ultimo_mes_completo
from etl.auditoria import ejecucion
from etl.config import dw_engine


def leer_serie():
    eng = dw_engine()
    df = pd.read_sql(text("""
        SELECT d.YearMonth AS mes, SUM(f.NetSales) AS ventas
        FROM dw.FactSales f JOIN dw.DimDate d ON d.DateKey = f.DateKey
        GROUP BY d.YearMonth ORDER BY d.YearMonth"""), eng)
    hasta = pd.read_sql(text(
        "SELECT MAX(d.FullDate) AS f FROM dw.FactSales f JOIN dw.DimDate d ON d.DateKey = f.DateKey"),
        eng)["f"].iloc[0]
    return {r.mes: float(r.ventas) for r in df.itertuples()}, pd.Timestamp(hasta).date()


def sin_duplicar(alertas, existentes):
    """Separa las alertas nuevas de las que ya estaban guardadas (misma regla, periodo y ámbito)."""
    nuevas = [a for a in alertas if (a["regla"], a["periodo"], a["ambito"]) not in existentes]
    return nuevas, len(alertas) - len(nuevas)


def _claves_guardadas():
    with dw_engine().connect() as cn:
        filas = cn.execute(text("SELECT regla, periodo, ambito FROM audit.alertas")).all()
    return {tuple(f) for f in filas}


def _guardar(alertas, execution_id):
    with dw_engine().begin() as cn:
        for a in alertas:
            cn.execute(text("""
                INSERT audit.alertas (regla, periodo, ambito, valor_actual, valor_referencia, variacion_pct,
                                      umbral_pct, severidad, mensaje, execution_id)
                VALUES (:regla, :periodo, :ambito, :valor_actual, :valor_referencia, :variacion_pct,
                        :umbral_pct, :severidad, :mensaje, :ex)"""),
                {**{k: a[k] for k in ("regla", "periodo", "ambito", "valor_actual", "valor_referencia",
                                      "variacion_pct", "umbral_pct", "severidad", "mensaje")},
                 "ex": execution_id})


def ejecutar(mes=None, historico=False, umbral=None):
    umbral = umbral if umbral is not None else float(os.getenv("ALERTA_UMBRAL_PCT", UMBRAL_DEFECTO))
    serie, datos_hasta = leer_serie()

    if historico:
        meses = sorted(serie)
    else:
        elegido = mes or ultimo_mes_completo(list(serie), datos_hasta)
        if elegido is None:
            print("No hay ningún mes completo para evaluar.")
            return []
        meses = [elegido]

    with ejecucion("alertas", "dw.FactSales", "audit.alertas") as run:
        comprobaciones = [c for m in meses for c in comprobar(serie, m, umbral)]
        run.rows_read = len(meses)
        disparadas = [c for c in comprobaciones if c["dispara"]]
        nuevas, repetidas = sin_duplicar(disparadas, _claves_guardadas())
        if nuevas:
            _guardar(nuevas, run.id)
        run.rows_inserted = len(nuevas)

    if not historico:
        for c in comprobaciones:
            estado = "ALERTA" if c["dispara"] else "ok"
            print(f"  {c['periodo']} {c['regla']:17} {c['variacion_pct']:+7.1f} %  (umbral -{umbral:g} %)  -> {estado}")
        if not comprobaciones:
            print(f"  {meses[0]}: no hay mes de referencia para comparar, no se evaluó.")
    print(f"Meses evaluados: {len(meses)} | alertas nuevas: {len(nuevas)} | ya registradas: {repetidas}")
    for a in nuevas:
        print(f"  [{a['severidad']}] {a['mensaje']}")
    return nuevas


def main():
    ap = argparse.ArgumentParser(description="Evalúa las reglas de alerta de ventas")
    ap.add_argument("--mes", help="mes a evaluar, AAAA-MM (por defecto el último completo)")
    ap.add_argument("--historico", action="store_true", help="evaluar todos los meses")
    ap.add_argument("--umbral", type=float, help="caída mínima en %% para alertar (por defecto 15)")
    args = ap.parse_args()
    ejecutar(args.mes, args.historico, args.umbral)


if __name__ == "__main__":
    main()