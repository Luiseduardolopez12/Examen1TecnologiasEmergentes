"""Entrena el modelo de pronóstico y guarda resultados.

    python -m ml.entrenar

Lee las ventas mensuales del Data Warehouse, compara los modelos contra el baseline,
guarda el modelo ganador en ml/artefactos/ y escribe el pronóstico y las métricas en SQL Server
(dw.PronosticoVentas y audit.ml_metricas). Cada corrida queda registrada en audit.etl_runs.
"""
import json
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import text

from etl.auditoria import ejecucion
from etl.config import dw_engine
from ml.modelos import entrenar_y_pronosticar, preparar_serie

ARTEFACTOS = Path("ml/artefactos")


def leer_serie():
    eng = dw_engine()
    df = pd.read_sql(text("""
        SELECT d.YearMonth AS mes, SUM(f.NetSales) AS ventas
        FROM dw.FactSales f JOIN dw.DimDate d ON d.DateKey = f.DateKey
        GROUP BY d.YearMonth ORDER BY d.YearMonth"""), eng)
    fecha_max = pd.read_sql(text(
        "SELECT MAX(d.FullDate) AS f FROM dw.FactSales f JOIN dw.DimDate d ON d.DateKey = f.DateKey"),
        eng)["f"].iloc[0]
    return preparar_serie(df, fecha_max)


def resumen_datos(y):
    print(f"\nSerie: {len(y)} meses, de {y.index[0]} a {y.index[-1]}")
    print(f"  promedio {y.mean():,.0f} | mínimo {y.min():,.0f} ({y.idxmin()}) | máximo {y.max():,.0f} ({y.idxmax()})")
    print(f"  variación (desv/promedio): {y.std() / y.mean() * 100:.1f} %")
    por_mes = y.groupby(y.index.month).mean()
    print(f"  mes más fuerte: {int(por_mes.idxmax())} | más flojo: {int(por_mes.idxmin())} "
          f"(diferencia {(por_mes.max() / por_mes.min() - 1) * 100:.0f} %)")


def imprimir_resultados(r):
    print(f"\nEntrenamiento: {r['meses_entrenamiento']} meses | prueba: {r['meses_prueba']} meses | "
          f"pliegues de validación: {r['pliegues']}")
    print(f"{'modelo':26}{'MAE valid.':>14}{'MAE prueba':>14}{'MAPE prueba':>13}")
    for m in r["metricas"]:
        marca = "  <- ELEGIDO" if m["ganador"] else ("  (baseline)" if m["es_baseline"] else "")
        print(f"{m['modelo']:26}{m['mae_validacion']:>14,.0f}{m['mae_prueba']:>14,.0f}"
              f"{m['mape_prueba']:>12.1f}%{marca}")
    base = next(m for m in r["metricas"] if m["es_baseline"])
    elegido = next(m for m in r["metricas"] if m["ganador"])
    if elegido is base:
        print("\nEl baseline fue el mejor: los modelos más complejos no aportaron mejora.")
    else:
        mejora = (1 - elegido["mae_prueba"] / base["mae_prueba"]) * 100
        print(f"\nEn la prueba, {elegido['modelo']} tiene {abs(mejora):.0f} % "
              f"{'menos' if mejora >= 0 else 'más'} error (MAE) que el baseline.")
    print("\nPronóstico:")
    for p in r["pronostico"]:
        print(f"  {p['mes']}: {p['valor']:>12,.0f}   (rango 80 %: {p['inferior']:,.0f} a {p['superior']:,.0f})")


def guardar(r, run_id, version):
    ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    joblib.dump(r["modelo_final"], ARTEFACTOS / f"modelo_{version}.joblib")
    ficha = {"version": version, "entrenado_en": datetime.now().isoformat(timespec="seconds"),
             "modelo": r["ganador"], "parametros": r["modelo_final"].parametros(),
             "base_hasta": r["base_hasta"], "horizonte_meses": r["horizonte"],
             "meses_entrenamiento": r["meses_entrenamiento"], "meses_prueba": r["meses_prueba"],
             "metricas": r["metricas"]}
    (ARTEFACTOS / f"modelo_{version}.json").write_text(
        json.dumps(ficha, indent=2, ensure_ascii=False), encoding="utf-8")

    with dw_engine().begin() as cn:
        cn.execute(text("""
            INSERT audit.ml_metricas (ml_run_id, version, modelo, es_baseline, ganador,
                mae_validacion, rmse_validacion, mape_validacion, mae_prueba, rmse_prueba, mape_prueba, parametros)
            VALUES (:run, :version, :modelo, :es_baseline, :ganador,
                :mae_validacion, :rmse_validacion, :mape_validacion, :mae_prueba, :rmse_prueba, :mape_prueba, :parametros)"""),
            [{"run": run_id, "version": version, **{k: m[k] for k in (
                "modelo", "es_baseline", "ganador", "mae_validacion", "rmse_validacion", "mape_validacion",
                "mae_prueba", "rmse_prueba", "mape_prueba")},
              "parametros": json.dumps(m["parametros"])} for m in r["metricas"]])
        cn.execute(text("""
            INSERT dw.PronosticoVentas (ml_run_id, version, modelo, mes, horizonte_mes, valor, inferior, superior, base_hasta)
            VALUES (:run, :version, :modelo, :mes, :h, :valor, :inferior, :superior, :base)"""),
            [{"run": run_id, "version": version, "modelo": r["ganador"], "mes": p["mes"], "h": p["horizonte_mes"],
              "valor": round(p["valor"], 2), "inferior": round(p["inferior"], 2),
              "superior": round(p["superior"], 2), "base": r["base_hasta"]} for p in r["pronostico"]])


def main():
    with ejecucion("ml_pronostico", "dw.FactSales", "dw.PronosticoVentas") as run:
        y = leer_serie()
        resumen_datos(y)
        r = entrenar_y_pronosticar(y)
        imprimir_resultados(r)
        version = f"v{datetime.now():%Y%m%d%H%M}"
        guardar(r, run.id, version)
        run.rows_read = len(y)
        run.rows_inserted = len(r["pronostico"])
        print(f"\nModelo guardado como {version} en ml/artefactos/")


if __name__ == "__main__":
    main()
